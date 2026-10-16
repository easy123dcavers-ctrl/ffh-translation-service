"""R107 dependency-free endpoint behavior tests with fake dependencies.

Executes the actual app.py route function AST with import/decorator side effects
excluded, a simulated request and an isolated translation callback.
No Flask/Argos installation, no network and no production data.
"""
import ast
import copy
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"


class StubLogger:
    def __init__(self):
        self.exceptions = []

    def exception(self, value):
        self.exceptions.append(value)


class StubRequest:
    def __init__(self):
        self.body = None

    def get_json(self, silent=False):
        assert silent is True
        return self.body


def load_routes():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    names = {"validated_json_body", "validate_target", "translate", "translate_batch"}
    code = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = []
            code.append(cloned)
    assert {node.name for node in code} == names
    request = StubRequest()
    logger = StubLogger()
    translated = []
    def translate_text(q, target=None):
        translated.append((q, target))
        if q == "TRIGGER_EXCEPTION":
            raise RuntimeError("synthetic error")
        return "mock translation: " + q
    namespace = {
        "request": request,
        "jsonify": lambda x: x,
        "app": type("StubApp", (), {"logger": logger})(),
        "SOURCE": "en",
        "CONFIGURED_TARGET": "es",
        "MULTILINGUAL": False,
        "MAX_BATCH_ITEMS": 25,
        "supported_targets": lambda: ["es"],
        "configured_model_installed": lambda: True,
        "translate_text": translate_text,
    }
    subset = ast.fix_missing_locations(ast.Module(body=code, type_ignores=[]))
    exec(compile(subset, str(APP), "exec"), namespace)
    return namespace, request, translated, logger


class EndpointContractTests(unittest.TestCase):
    def setUp(self):
        self.routes, self.request, self.calls, self.logger = load_routes()

    def call(self, name, body):
        self.request.body = body
        return self.routes[name]()

    def test_successful_single(self):
        self.assertEqual(self.call("translate", {
            "q": "sample 7", "source": "en", "target": "es"
        }), {"translatedText": "mock translation: sample 7"})
        self.assertEqual(self.calls, [("sample 7", "es")])

    def test_successful_mixed_batch(self):
        result = self.call("translate_batch", {
            "items": ["sample 1", {"id": "xyz", "q": "sample 2"}],
            "source": "en", "target": "es"})
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["target"], "es")
        self.assertEqual(result["results"][0]["id"], "0")
        self.assertEqual(result["results"][1]["id"], "xyz")
        self.assertEqual(self.calls, [("sample 1", "es"), ("sample 2", "es")])

    def test_non_object_json_returns_400_on_both_routes(self):
        for body in ([], ["q"], 14, False, True, "q", None):
            for route in ("translate", "translate_batch"):
                with self.subTest(body=body, route=route):
                    response, status = self.call(route, body)
                    self.assertEqual(status, 400)
                    self.assertIn("JSON object", response["error"])
        self.assertEqual(self.calls, [])

    def test_invalid_or_missing_q_returns_400(self):
        for q in (None, "", "  ", 12, ["text"]):
            result, status = self.call("translate", {
                "q": q, "source": "en", "target": "es"})
            self.assertEqual(status, 400)
        self.assertEqual(self.calls, [])

    def test_missing_target_remains_400_per_documented_contract(self):
        for name, data in (
            ("translate", {"q": "sample 4", "source": "en"}),
            ("translate_batch", {"items": ["sample 4"], "source": "en"}),
        ):
            _, status = self.call(name, data)
            self.assertEqual(status, 400)

    def test_invalid_source_rejected(self):
        result, status = self.call("translate", {
            "q": "sample", "source": "de", "target": "es"})
        self.assertEqual(status, 400)
        self.assertIn("source=en", result["error"])

    def test_invalid_target_rejected(self):
        result, status = self.call("translate_batch", {
            "items": ["sample"], "source": "en", "target": "fr"})
        self.assertEqual(status, 400)
        self.assertIn("unsupported target", result["error"])

    def test_batch_size_remains_one_to_25(self):
        for entries in ([], ["sample"]*26, "sample"):
            _, status = self.call("translate_batch", {
                "items": entries, "source": "en", "target": "es"})
            self.assertEqual(status, 400)

    def test_invalid_batch_entry_isolated(self):
        result = self.call("translate_batch", {
            "items": ["hello", None, {"id": 88, "q": ""}],
            "source": "en", "target": "es"})
        self.assertEqual([v["ok"] for v in result["results"]],
                         [True, False, False])
        self.assertEqual(result["results"][2]["id"], "88")

    def test_single_exception_returns_500_without_leaking_details(self):
        response, status = self.call("translate", {
            "q": "TRIGGER_EXCEPTION", "source": "en", "target": "es"})
        self.assertEqual(status, 500)
        self.assertEqual(response, {"error": "translation failed"})
        self.assertEqual(len(self.logger.exceptions), 1)

    def test_batch_translation_exception_is_local(self):
        result = self.call("translate_batch", {
            "items": ["before", "TRIGGER_EXCEPTION", "after"],
            "source": "en", "target": "es"})
        self.assertEqual([row["ok"] for row in result["results"]],
                         [True, False, True])
        self.assertEqual(result["results"][1]["error"], "translation failed")
        self.assertEqual(len(self.logger.exceptions), 1)


if __name__ == "__main__":
    unittest.main()
