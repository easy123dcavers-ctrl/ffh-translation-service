"""R123 disposable, loopback-only readiness/draining HTTP gateway.

A narrow experimental *transport* proof, not FFH Member authentication.
No production imports, Supabase access, translation model, writes or logging.
Only guarded endpoints reach the backend. When draining, newly arriving
requests get 503 + Retry-After instead of being forwarded to a dying worker.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import threading
import time


MAX_BODY_BYTES = 128 * 1024
MAX_REPLY_BYTES = 256 * 1024
GUARDED = frozenset((
    "/experimental/guarded-translate",
    "/experimental/guarded-translate-batch",
))
LEGACY = frozenset(("/translate", "/translate-batch"))


class Readiness:
    def __init__(self):
        self.cv = threading.Condition()
        self.ready = False
        self.active = 0
        self.admitted_total = 0
        self.rejected_draining = 0
        self.transport_errors = 0

    def begin(self):
        with self.cv:
            if not self.ready:
                self.rejected_draining += 1
                return False
            self.active += 1
            self.admitted_total += 1
            return True

    def finish(self):
        with self.cv:
            assert self.active > 0
            self.active -= 1
            self.cv.notify_all()

    def begin_drain(self, timeout=35):
        deadline = time.monotonic() + timeout
        with self.cv:
            self.ready = False
            while self.active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.cv.wait(timeout=remaining)
            return True

    def mark_unavailable(self):
        with self.cv:
            self.ready = False
            self.transport_errors += 1
            self.cv.notify_all()

    def resume(self):
        with self.cv:
            if self.active:
                raise RuntimeError("Cannot resume while requests are active")
            self.ready = True

    def snapshot(self):
        with self.cv:
            return {"ready": self.ready, "active": self.active,
                    "admitted_total": self.admitted_total,
                    "rejected_draining": self.rejected_draining,
                    "transport_errors": self.transport_errors}


def make_handler(readiness, backend_port, stage_token):
    """One gateway for one local Gunicorn instance; NEVER deploy directly."""
    if len(stage_token) < 32:
        raise ValueError("A strong synthetic staging token is required")

    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            # NEVER log paths, headers, tokens or request/response bodies.
            pass

        def answer(self, status, body, *, retry_after=None):
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, private, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            if retry_after is not None:
                self.send_header("Retry-After", str(retry_after))
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            self.close_connection = True

        def do_GET(self):
            if self.path != "/health":
                self.answer(404, {"error": "not found"})
                return
            state = readiness.snapshot()
            if state["ready"]:
                self.answer(200, {"status": "ready"})
            else:
                self.answer(503, {"error": "service draining"}, retry_after=2)

        def do_POST(self):
            if self.path in LEGACY:
                self.answer(410, {"error": "legacy translation route disabled"})
                return
            if self.path not in GUARDED:
                self.answer(404, {"error": "not found"})
                return
            expected = "Bearer " + stage_token
            if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
                self.answer(401, {"error": "unauthorized"})
                return
            if not readiness.begin():
                self.answer(503, {"error": "service draining",
                                  "retryable": True, "retry_after_seconds": 2},
                            retry_after=2)
                return
            connection = None
            try:
                raw_length = self.headers.get("Content-Length", "")
                if not raw_length.isascii() or not raw_length.isdecimal():
                    self.answer(411, {"error": "content-length required"})
                    return
                length = int(raw_length)
                if length > MAX_BODY_BYTES:
                    self.answer(413, {"error": "request body too large"})
                    return
                if length <= 0:
                    self.answer(400, {"error": "request body required"})
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self.answer(400, {"error": "incomplete request"})
                    return
                connection = http.client.HTTPConnection(
                    "127.0.0.1", backend_port, timeout=105)
                connection.request("POST", self.path, body=body, headers={
                    "Content-Type": "application/json",
                    "Authorization": expected,
                    "Connection": "close",
                })
                response = connection.getresponse()
                upstream_data = response.read(MAX_REPLY_BYTES + 1)
                if len(upstream_data) > MAX_REPLY_BYTES:
                    raise ValueError("Oversize backend reply")
                # Only relay valid JSON from the one trusted local backend.
                parsed = json.loads(upstream_data)
                if not isinstance(parsed, dict):
                    raise ValueError("Unexpected backend reply")
                self.answer(response.status, parsed,
                            retry_after=(2 if response.status == 429 else None))
            except (OSError, http.client.HTTPException, TimeoutError,
                    ValueError, UnicodeError, json.JSONDecodeError):
                # A request that reached the model may have run. NEVER retry it
                # automatically and never claim the result did not happen.
                readiness.mark_unavailable()
                self.answer(502, {"error": "translation outcome unknown",
                                  "retryable": False})
            finally:
                if connection is not None:
                    connection.close()
                readiness.finish()
    return GatewayHandler


def start_gateway(readiness, *, backend_port, stage_token, port=0):
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(readiness, backend_port, stage_token))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
