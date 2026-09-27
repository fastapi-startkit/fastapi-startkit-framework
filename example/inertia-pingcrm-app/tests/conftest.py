import socket
import time
import threading
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    """Start the app on a free port and yield its base URL."""
    import uvicorn
    import httpx
    from bootstrap.application import app

    host = "127.0.0.1"
    port = _find_free_port()

    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://{host}:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            httpx.get(f"{base_url}/login", follow_redirects=False, timeout=1.0)
            break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("Test server did not start within 15 seconds")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(live_server_url):
    """Override pytest-playwright's base_url with the dynamic live server URL."""
    return live_server_url
