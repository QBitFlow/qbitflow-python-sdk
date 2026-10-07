"""Pages and iterators (Go pagination_test.go)."""

from __future__ import annotations

from typing import List, Optional

import httpx
import pytest

from qbitflow import Customer, Page, ValidationError
from qbitflow._services._base import iterate_pages
from qbitflow._transport import Response, decode

from .conftest import make_client, reply

PAGES = {
    "": '{"items":[{"uuid":"c0"},{"uuid":"c1"}],"nextCursor":"c1"}',
    "c1": '{"items":[{"uuid":"c2"},{"uuid":"c3"}],"nextCursor":"c3"}',
    "c3": '{"items":[{"uuid":"c4"}],"nextCursor":null}',
}


def paged(fail_on: str = ""):
    """/customer/all in pages of 2 over 5 customers (c0…c4), keyed by cursor."""

    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        cursor = req.url.params.get("cursor", "")
        if fail_on and cursor == fail_on:
            return reply(
                400,
                (
                    '{"error":"bad cursor","code":"validation_failed","details":{'
                    '"errors":[{"field":"cursor","message":"cursor is unknown"}]}'
                    "}"
                ),
            )
        return reply(200, PAGES[cursor])

    return handler


def test_iterate_all_pages() -> None:
    client, server, _ = make_client(paged())
    got = [c.uuid for c in client.customers.iterate(limit=2, email="a@b.co")]
    assert got == ["c0", "c1", "c2", "c3", "c4"]
    assert [r.query for r in server.requests] == [
        "email=a%40b.co&limit=2",
        "cursor=c1&email=a%40b.co&limit=2",
        "cursor=c3&email=a%40b.co&limit=2",
    ]


def test_iterate_from_cursor() -> None:
    client, server, _ = make_client(paged())
    assert [c.uuid for c in client.customers.iterate(cursor="c3")] == ["c4"]
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
    client, _, _ = make_client(paged(fail_on="c3"))
    got = []
    with pytest.raises(ValidationError) as info:
        for c in client.customers.iterate():
            got.append(c.uuid)
    assert got == ["c0", "c1", "c2", "c3"]
    assert info.value.field_errors[0].field == "cursor" and info.value.status == 400


def test_iterate_stops_on_empty_or_stuck_page() -> None:
    calls = 0

    def fetch(cursor: Optional[str]) -> Page[int]:
        nonlocal calls
        calls += 1
        items: List[int] = [] if calls == 2 else [calls]
        return Page[int](items=items, nextCursor=f"n{calls}")

    assert list(iterate_pages(fetch, None)) == [1] and calls == 2

    stuck = 0

    def same(cursor: Optional[str]) -> Page[int]:
        nonlocal stuck
        stuck += 1
        return Page[int](items=[1], nextCursor="same")

    list(iterate_pages(same, "same"))
    assert stuck == 1


def test_page_has_more() -> None:
    assert Page[int](items=[], nextCursor="x").has_more
    assert not Page[int](items=[]).has_more
    page = decode(
        Page[Customer], Response(200, httpx.Headers(), b'{"items":null,"nextCursor":null}')
    )
    assert page.items == [] and not page.has_more
