"""Pages, iterators and bounded lists (Go pagination_test.go)."""

from __future__ import annotations

from typing import Callable, List, Optional
from urllib.parse import parse_qs

import httpx
import pytest

from qbitflow import Customer, Page, ServerError, ValidationError
from qbitflow._services._base import iterate_pages
from qbitflow._transport import Response, decode

from .conftest import make_client, reply

#: /customers in pages of 2 over 5 customers (c0…c4), keyed by an opaque cursor; the last page
#: answers hasMore false (a full last page never adds an empty one).
PAGES = {
    "": '{"items":[{"uuid":"c0"},{"uuid":"c1"}],"hasMore":true,"nextCursor":"djF8YzE"}',
    "djF8YzE": '{"items":[{"uuid":"c2"},{"uuid":"c3"}],"hasMore":true,"nextCursor":"djF8YzM"}',
    "djF8YzM": '{"items":[{"uuid":"c4"}],"hasMore":false}',
}


def paged(fail_on: str = "") -> Callable[[httpx.Request, int], httpx.Response]:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        cursor = req.url.params.get("cursor", "")
        if fail_on and cursor == fail_on:
            return reply(
                400,
                '{"error":"bad cursor","code":"validation_failed","details":{'
                '"errors":[{"field":"cursor","message":"cursor is unknown"}]}}',
            )
        return reply(200, PAGES[cursor])

    return handler


def test_iterate_all_pages() -> None:
    client, server, _ = make_client(paged())
    got = [c.uuid for c in client.customers.iterate(limit=2, email="a@b.co")]
    assert got == ["c0", "c1", "c2", "c3", "c4"]
    # Filters and limit kept on every page; the first page never re-requested.
    assert [r.path for r in server.requests] == ["/customers"] * 3
    assert [r.query for r in server.requests] == [
        "email=a%40b.co&limit=2",
        "cursor=djF8YzE&email=a%40b.co&limit=2",
        "cursor=djF8YzM&email=a%40b.co&limit=2",
    ]


def test_iterate_from_cursor() -> None:
    client, server, _ = make_client(paged())
    assert [c.uuid for c in client.customers.iterate(cursor="djF8YzM")] == ["c4"]
    assert len(server.requests) == 1
    assert len(list(client.customers.iterate())) == 5


def test_iterate_is_lazy_and_stops_early() -> None:
    client, server, _ = make_client(paged())
    it = client.customers.iterate()
    assert server.requests == []  # nothing is fetched before the first item is asked for
    got = []
    for c in it:
        got.append(c.uuid)
        if c.uuid == "c2":
            break
    assert got == ["c0", "c1", "c2"] and len(server.requests) == 2


def test_iterate_error_propagation() -> None:
    client, _, _ = make_client(paged(fail_on="djF8YzM"))
    got = []
    with pytest.raises(ValidationError) as info:
        for c in client.customers.iterate():
            got.append(c.uuid)
    assert got == ["c0", "c1", "c2", "c3"]
    assert info.value.field_errors[0].field == "cursor" and info.value.status == 400


def _walk(pages: Callable[[int], Page[int]], cursor: Optional[str] = None) -> tuple:
    calls: List[Optional[str]] = []

    def fetch(c: Optional[str]) -> Page[int]:
        calls.append(c)
        return pages(len(calls))

    return list(iterate_pages(fetch, cursor)), calls


def test_iterate_stop_rules() -> None:
    def walk(n: int) -> Page[int]:
        if n > 3:
            raise AssertionError("requested a page past hasMore false")
        return Page[int](items=[n], has_more=n < 3, next_cursor="abc"[n - 1] if n < 3 else None)

    items, calls = _walk(walk)
    assert items == [1, 2, 3] and calls == [None, "a", "b"]

    # hasMore false stops even with a cursor present (the API never sends one then).
    items, calls = _walk(lambda n: Page[int](items=[1], has_more=False, next_cursor="x"))
    assert items == [1] and len(calls) == 1

    # hasMore true without a nextCursor: defensive stop.
    items, calls = _walk(lambda n: Page[int](items=[1], has_more=True))
    assert len(calls) == 1

    # An empty page that claims more, with cursors that keep changing: defensive stop.
    items, calls = _walk(lambda n: Page[int](items=[], has_more=True, next_cursor="ab"[n % 2]))
    assert items == [] and len(calls) == 1

    # A cursor that does not move: defensive stop.
    items, calls = _walk(
        lambda n: Page[int](items=[1], has_more=True, next_cursor="same"), cursor="same"
    )
    assert len(calls) == 1


def test_page_decoding() -> None:
    def page(body: bytes) -> Page[Customer]:
        return decode(Page[Customer], Response(200, httpx.Headers(), body))

    p = page(b'{"items":[{"uuid":"c0"}],"hasMore":true,"nextCursor":"djF8eA"}')
    assert p.has_more is True and p.next_cursor == "djF8eA" and len(p.items) == 1
    p = page(b'{"items":[],"hasMore":false}')
    assert p.has_more is False and p.next_cursor is None and p.items == []
    # Lenient on absence and null: zero values.
    p = page(b'{"items":null}')
    assert p.items == [] and p.has_more is False
    # has_more is a field (the wire's hasMore), not derived from the cursor.
    assert Page[int](items=[], next_cursor="x").has_more is False
    assert Page[int].model_validate({"hasMore": True}).has_more is True
    # Strict on type.
    for body in (
        b'{"items":[],"hasMore":"true"}',
        b'{"items":{},"hasMore":false}',
        b'{"items":[],"nextCursor":5}',
        b"[]",
        b"null",
    ):
        with pytest.raises(ServerError):
            page(body)


def test_bounded_lists_unwrap_items() -> None:
    client, server, _ = make_client(
        lambda req, n: reply(
            200, '{"items":[{"id":8,"code":"BASE:USDC"},{"id":1,"code":"ETH"}],"hasMore":false}'
        )
    )
    currencies = client.currencies.list(main=True)
    assert [c.code for c in currencies] == ["BASE:USDC", "ETH"] and len(server.requests) == 1
    client, _, _ = make_client(lambda req, n: reply(200, '{"items":[],"hasMore":false}'))
    assert client.wallets.list() == []
    # A bare JSON array is no page.
    client, _, _ = make_client(lambda req, n: reply(200, "[]"))
    with pytest.raises(ServerError):
        client.currencies.list()


def test_bounded_list_follows_has_more() -> None:
    """A bounded list answering hasMore true (never expected) is followed with its nextCursor,
    the filters kept, under the iterators' guards: never cut short silently."""
    pages = {
        "": '{"items":[{"id":1}],"hasMore":true,"nextCursor":"djF8Mg"}',
        "djF8Mg": '{"items":[{"id":2}],"hasMore":false}',
    }
    client, server, _ = make_client(
        lambda req, n: reply(200, pages[req.url.params.get("cursor", "")])
    )
    assert [c.id for c in client.currencies.list(test=True)] == [1, 2]
    assert [parse_qs(r.query) for r in server.requests] == [
        {"test": ["true"]},
        {"test": ["true"], "cursor": ["djF8Mg"]},
    ]

    # Guards: a cursor that does not move, or an empty page that claims more, stops the walk.
    stuck = '{"items":[{"id":1}],"hasMore":true,"nextCursor":"same"}'
    client, server, _ = make_client(lambda req, n: reply(200, stuck))
    assert [c.id for c in client.wallets.list_accepted_currencies()] == [1, 1]
    assert len(server.requests) == 2
    client, server, _ = make_client(
        lambda req, n: reply(200, '{"items":[],"hasMore":true,"nextCursor":"c' + str(n) + '"}')
    )
    assert client.members.list_held_funds() == [] and len(server.requests) == 1
    client, server, _ = make_client(
        lambda req, n: reply(200, '{"items":[{"id":3}],"hasMore":true}')
    )
    assert len(client.currencies.list()) == 1 and len(server.requests) == 1
