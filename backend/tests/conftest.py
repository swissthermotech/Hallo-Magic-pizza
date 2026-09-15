"""Legacy test suites (iter 1-7) were written before server-side staff auth existed.
This autouse fixture injects a MANAGER token on requests that carry no Authorization header,
so the functional suites keep testing business behaviour. The security suite is exempt on purpose."""
import os
import pytest
import requests

API = os.environ.get("API_URL", "http://localhost:8001/api")
_TOKEN = {}


def _manager_token():
    if "t" not in _TOKEN:
        r = requests.post(f"{API}/auth/staff/login", json={"pin": os.environ.get("STAFF_PIN_MANAGER", "1234")})
        r.raise_for_status()
        _TOKEN["t"] = r.json()["access_token"]
    return _TOKEN["t"]


@pytest.fixture(autouse=True)
def _inject_manager_token(request, monkeypatch):
    if request.module.__name__.startswith("test_security") or "requires" in request.node.name:
        yield
        return
    _manager_token()  # fetch before patching (avoids recursion)
    original = requests.Session.request

    def patched(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        if "Authorization" not in headers and "Authorization" not in self.headers and "/api/" in url:
            headers["Authorization"] = f"Bearer {_manager_token()}"
            kwargs["headers"] = headers
        return original(self, method, url, **kwargs)

    monkeypatch.setattr(requests.Session, "request", patched)
    yield
