import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakePlatform:
    """Answers POSTs with scripted responses, in order, and records every request."""

    def __init__(self):
        self.url = ""
        self.responses = []
        self.requests = []

    def reply(self, status, body=None, headers=None, delay=0.0):
        self.responses.append((status, {} if body is None else body, headers or {}, delay))


@pytest.fixture
def platform():
    fake = FakePlatform()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            with lock:
                fake.requests.append({"path": self.path, "headers": self.headers, "body": body})
                if fake.responses:
                    status, payload, headers, delay = fake.responses.pop(0)
                else:
                    status, payload, headers, delay = 500, {"detail": "no response scripted"}, {}, 0.0
            time.sleep(delay)
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass  # the client hung up first (the timeout tests do that on purpose)

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()
