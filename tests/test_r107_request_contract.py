"""R107 offline-only regression tests for request-shape hardening.

Runs with Python standard library only; does not import Flask/Argos,
reach network endpoints, or access FFH member information.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "app.py"


def parse_module():
    return ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))


def isolated_body_parser(payload):
    tree = parse_module()
    funcs = [x for x in tree.body if isinstance(x, ast.FunctionDef)
             and x.name == "validated_json_body"]
    if len(funcs) != 1:
        raise AssertionError("Expected one validated_json_body helper")
    calls = []

    class RequestStub:
        def get_json(self, silent=False):
            calls.append(silent)
            return payload

    namespace = {"request": RequestStub()}
    isolated_ast = ast.Module(body=funcs, type_ignores=[])
    exec(compile(ast.fix_missing_locations(isolated_ast), str(SOURCE), "exec"), namespace)
    result = namespace["validated_json_body"]()
    return result, calls


class RequestShapeContract(unittest.TestCase):
    def test_json_object_is_accepted(self):
        data = {"q": "invented text", "source": "en", "target": "es"}
        observed, calls = isolated_body_parser(data)
        self.assertIs(observed, data)
        self.assertEqual(calls, [True])

    def test_empty_object_is_parsed_as_object(self):
        observed, calls = isolated_body_parser({})
        self.assertEqual(observed, {})
        self.assertEqual(calls, [True])

    def test_array_is_rejected(self):
        self.assertIsNone(isolated_body_parser(["invented"])[0])

    def test_string_is_rejected(self):
        self.assertIsNone(isolated_body_parser("invented")[0])

    def test_integer_is_rejected(self):
        self.assertIsNone(isolated_body_parser(123)[0])

    def test_null_is_rejected(self):
        self.assertIsNone(isolated_body_parser(None)[0])

    def test_boolean_is_rejected(self):
        self.assertIsNone(isolated_body_parser(True)[0])

    def test_both_routes_call_helper_and_guard_invalid_json(self):
        module = parse_module()
        for route in ("translate", "translate_batch"):
            with self.subTest(route=route):
                funcs = [x for x in module.body if isinstance(x, ast.FunctionDef)
                         and x.name == route]
                self.assertEqual(len(funcs), 1)
                body = funcs[0].body
                parsed = [x for x in ast.walk(funcs[0])
                          if isinstance(x, ast.Call) and
                          isinstance(x.func, ast.Name) and
                          x.func.id == "validated_json_body"]
                self.assertEqual(len(parsed), 1)
                invalid_body_guards = [
                    x for x in ast.walk(funcs[0])
                    if isinstance(x, ast.Constant)
                    and x.value == "request body must be a JSON object"
                ]
                self.assertEqual(len(invalid_body_guards), 1)
                # Verify at least one guard explicitly returns 400.
                guards_400 = [
                    x for x in ast.walk(funcs[0])
                    if isinstance(x, ast.Return)
                    and isinstance(x.value, ast.Tuple)
                    and any(isinstance(z, ast.Constant) and z.value == 400
                            for z in x.value.elts)
                ]
                self.assertGreaterEqual(len(guards_400), 1)


if __name__ == "__main__":
    unittest.main()
