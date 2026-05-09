"""Shared pytest fixtures for x402-norway-patent-search."""
import os
import sys

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def main_module():
    os.environ.setdefault("EVM_ADDRESS", "0xTEST0000000000000000000000000000000000")
    # Default: API key SET so tests exercise the happy path. Tests that need
    # the missing-key path use monkeypatch.delenv directly.
    os.environ.setdefault("PATENTSTYRET_API_KEY", "test-subscription-key")
    os.chdir(REPO_ROOT)
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import main
    return main


@pytest.fixture
def parsers_module(main_module):
    import parsers
    return parsers


@pytest.fixture
def ps_module(main_module):
    import patentstyret_client
    return patentstyret_client


@pytest.fixture
def nice_module(main_module):
    import nice_classes
    return nice_classes


@pytest.fixture(autouse=True)
def reset_cache(main_module):
    import cache
    cache.reset()
    yield


class FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


class FakePS:
    """Stub for httpx.AsyncClient — Patentstyret uses GET only."""

    def __init__(self):
        self.responses: dict[str, FakeResponse] = {}
        self.calls: list[tuple[str, dict, dict]] = []  # (url, params, headers)

    def stub(self, url_contains, status, json_data=None):
        self.responses[url_contains] = FakeResponse(status, json_data)

    async def get(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        for needle, r in self.responses.items():
            if needle in url:
                return r
        return FakeResponse(404, {"error": f"unstubbed {url}"})

    async def aclose(self):
        pass


@pytest.fixture
def fake_ps(main_module, monkeypatch):
    f = FakePS()
    monkeypatch.setattr(main_module, "_http", f)
    return f
