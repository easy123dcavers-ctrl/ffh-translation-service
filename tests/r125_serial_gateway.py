"""R125 disposable, loopback-only single-resident-target readiness gateway.

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


# Experimental extension only; this file is NOT used by production.
class Readiness:
    def __init__(self):
        self.cv = threading.Condition()
        self.ready = False
        self.active = 0
        self.admitted_total = 0
        self.rejected_draining = 0
        self.rejected_busy = 0
        self.transport_errors = 0
        self.selected_target = None
        self.switch_denied = 0

    def choose_target(self, target):
        if target not in ("es","fr","ja","de","ar","tl","ko","vi","zh"):
            raise ValueError("Unsupported single-resident target")
        with self.cv:
            if self.ready or self.active:
                raise RuntimeError("Cannot select model while backend is serving")
            self.selected_target = target

    def current_target(self):
        with self.cv:
            return self.selected_target

    def note_wrong_target(self):
        with self.cv:
            self.switch_denied += 1

    def begin(self):
        """Atomically accept ONE inflight batch or return busy/draining status.

        The slot protects a CPU-constrained, single-resident-model backend.
        Never rely on scheduler sleep or backend flock as sole admission gate.
        """
        with self.cv:
            if not self.ready:
                self.rejected_draining += 1
                return "draining"
            if self.active:
                self.rejected_busy += 1
                return "busy"
            self.active = 1
            self.admitted_total += 1
            return "accepted"

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
                    "rejected_busy": self.rejected_busy,
                    "transport_errors": self.transport_errors,
                    "selected_target": self.selected_target,
                    "switch_denied": self.switch_denied}


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
            admission = readiness.begin()
            if admission == "draining":
                self.answer(503, {"error": "service draining",
                                  "retryable": True, "retry_after_seconds": 2},
                            retry_after=2)
                return
            if admission == "busy":
                self.answer(429, {"error": "translator busy",
                                  "retryable": True, "retry_after_seconds": 2},
                            retry_after=2)
                return
            assert admission == "accepted"
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
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeError):
                    self.answer(400, {"error": "invalid json"})
                    return
                if not isinstance(payload, dict) or not isinstance(payload.get("target"), str):
                    self.answer(400, {"error": "target language required"})
                    return
                if payload["target"] != readiness.current_target():
                    readiness.note_wrong_target()
                    self.answer(503, {"error": "target model not resident",
                                      "retryable": True, "retry_after_seconds": 2},
                                retry_after=2)
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


class BoundedListenGateway(ThreadingHTTPServer):
    # The base server's five-slot listen backlog can reset short bursts before
    # atomic 429 admission. Bound the *queued sockets* at 64 in this synthetic
    # loopback-only test; never use this to bypass production rate limits.
    request_queue_size = 64


def start_gateway(readiness, *, backend_port, stage_token, port=0):
    server = BoundedListenGateway(
        ("127.0.0.1", port), make_handler(readiness, backend_port, stage_token))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
