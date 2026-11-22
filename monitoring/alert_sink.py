"""Tiny local webhook receiver used only to verify Alertmanager routing."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading

_lock = threading.Lock()
_received = 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps({"status": "ok", "received": _received}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global _received
        if self.path != "/alerts":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict) or "alerts" not in payload:
            self.send_error(400, "Expected Alertmanager webhook payload")
            return
        with _lock:
            _received += len(payload["alerts"])
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
