"""E2E test fixtures — spin up the real Hub Flask app so Playwright can drive it."""
import socket
import threading

import pytest
from werkzeug.serving import make_server

import app as hub_app


def _pick_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(threading.Thread):
    def __init__(self, flask_app, port: int):
        super().__init__(daemon=True)
        self.srv = make_server("127.0.0.1", port, flask_app, threaded=True)

    def run(self):
        self.srv.serve_forever()

    def stop(self):
        self.srv.shutdown()


@pytest.fixture(scope="session")
def live_server():
    """Start Hub on a random free port for the test session.
    Yields the base URL (e.g. http://127.0.0.1:54321)."""
    port = _pick_free_port()
    srv = _Server(hub_app.app, port)
    srv.start()
    # tiny wait so werkzeug finishes binding
    import time
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    srv.stop()
    srv.join(timeout=2)
