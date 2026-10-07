"""Shared test helpers: a recording stub HTTP server (httpx.MockTransport) and client factory."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import pytest

from qbitflow import QBitFlow

TEST_API_KEY = "sk_test_key_123"
BASE = "https://api.test"
FIXTURES = Path(__file__).parent / "fixtures"

MEMBER_UUID = "019eca82-5680-7b00-8000-0000000000b1"


@dataclass
class Recorded:
    """One request the stub server received."""

    method: str
    path: str  # escaped path, as sent
    query: str  # raw query, as sent
    headers: httpx.Headers
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


Handler = Callable[[httpx.Request, int], httpx.Response]


class StubServer:
    """A scripted handler that records every request (``n`` = its 0-based index)."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: List[Recorded] = []
        self._lock = threading.Lock()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raw = request.url.raw_path.decode("ascii")
        path, _, query = raw.partition("?")
        with self._lock:
            n = len(self.requests)
            self.requests.append(
                Recorded(request.method, path, query, request.headers, request.read())
            )
        return self.handler(request, n)


def reply(status: int, body: Any = "", headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """A JSON answer (``body`` a str is sent as is)."""
    content = body if isinstance(body, (str, bytes)) else json.dumps(body)
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return httpx.Response(status, content=content, headers=h)


def static(status: int, body: Any = "{}") -> Handler:
    """Answer every request with the same status and body."""
    return lambda _req, _n: reply(status, body)


def sequence(*replies: Tuple[int, str]) -> Handler:
    """Answer the scripted (status, body) pairs in order, then repeat the last one."""
    return lambda _req, n: reply(*replies[min(n, len(replies) - 1)])


def make_client(handler: Handler, **kwargs: Any) -> Tuple[QBitFlow, StubServer, List[float]]:
    """A client on a stub server, with a recording sleep (no real waits)."""
    server = StubServer(handler)
    http = httpx.Client(transport=httpx.MockTransport(server))
    kwargs.setdefault("base_url", BASE)
    client = QBitFlow(TEST_API_KEY, http_client=http, **kwargs)
    sleeps: List[float] = []
    client._transport.sleep = sleeps.append
    return client, server, sleeps


@pytest.fixture
def load_fixture() -> Callable[[str], str]:
    return lambda name: (FIXTURES / name).read_text()
