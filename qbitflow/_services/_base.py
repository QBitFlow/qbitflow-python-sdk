"""What every service shares: a reference to its client, the call helpers (bounded lists, the
``get_by_reference`` lookups), the iterator, and the body helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
)

from .._transport import Endpoint, Query, RequestOptions, Response, decode
from .._validation import Validator, money_text
from ..errors import CODE_NOT_FOUND, NotFoundError
from ..models.common import Duration, Page

if TYPE_CHECKING:  # pragma: no cover
    from .._client import QBitFlow

T = TypeVar("T")


class NotGiven:
    """The type of :data:`NOT_GIVEN`: a parameter left out (distinct from ``None`` and ``""``)."""

    _instance: Optional["NotGiven"] = None

    def __new__(cls) -> "NotGiven":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


#: The default of the clearable update fields: left out, so the value is unchanged. Pass ``""``
#: (or ``None``) to clear the field instead.
NOT_GIVEN = NotGiven()


class Service:
    """Base of every service: reached through a client's attributes, never built directly."""

    def __init__(self, client: "QBitFlow") -> None:
        self._client = client

    def _send(self, endpoint: Endpoint, options: Optional[RequestOptions]) -> Response:
        return self._client._send(endpoint, options)

    def _call(self, tp: Type[T], endpoint: Endpoint, options: Optional[RequestOptions]) -> T:
        return decode(tp, self._send(endpoint, options))

    def _call_items(
        self, tp: Type[T], endpoint: Endpoint, options: Optional[RequestOptions]
    ) -> List[T]:
        """A bounded list (one page, ``hasMore`` false: currencies, wallets, held funds, the
        accounting export): its ``items``, never ``None``. Defensively, a page that claims more
        is followed with its ``nextCursor`` (the filters kept) until ``hasMore`` is false, so a
        list the server ever splits is never cut short silently; the walk stops on the
        iterators' guards (no next cursor, a cursor that did not move, an empty page)."""
        items: List[T] = []
        cursor: Optional[str] = None
        while True:
            page = decode(Page[tp], self._send(endpoint, options))  # type: ignore[valid-type]
            items.extend(page.items)
            if _last_page(page, cursor):
                return items
            cursor = page.next_cursor
            query = Query(dict(endpoint.query.items) if endpoint.query is not None else {})
            endpoint = replace(endpoint, query=query.string("cursor", cursor))

    def _get_by_reference(
        self,
        tp: Type[T],
        path: str,
        what: str,
        reference: Any,
        reference_of: Callable[[T], Optional[str]],
        options: Optional[RequestOptions],
    ) -> T:
        """Run a list's ``?reference=`` filter (a page of 0 or 1 item) and return the item whose
        reference is **exactly** the one asked for. No such item is a :class:`NotFoundError`,
        like a 404 (status 404, code ``not_found``), carrying the list answer's request id:
        checking the reference means a server that ignored the filter can never hand back another
        resource. ``what`` names the resource in the error's message (``"product"``)."""
        v = Validator()
        if v.required("reference", reference):
            v.reference("reference", reference)
        v.check()
        resp = self._send(Endpoint("GET", path, Query().string("reference", reference)), options)
        page = decode(Page[tp], resp)  # type: ignore[valid-type]
        for item in page.items:
            if reference_of(item) == reference:
                return item
        raise NotFoundError(
            f"no {what} with this reference",
            status=404,
            code=CODE_NOT_FOUND,
            request_id=resp.headers.get("X-Request-Id", ""),
            raw_body=resp.body,
        )


def _last_page(page: Page[Any], cursor: Optional[str]) -> bool:
    """Whether a walk stops after ``page`` (fetched with ``cursor``): ``has_more`` false, and
    defensively a page claiming more without a ``next_cursor``, one whose ``next_cursor`` is the
    cursor just requested (it would loop on the same page forever), or an empty page that claims
    more (the API never answers one: a server fault, which could otherwise cycle between
    cursors)."""
    return not page.has_more or not page.next_cursor or page.next_cursor == cursor or not page.items


def iterate_pages(fetch: Callable[[Optional[str]], Page[T]], cursor: Optional[str]) -> Iterator[T]:
    """Walk a cursor-paginated list lazily, one request per page, from ``cursor`` (``None`` = the
    first page). ``fetch`` requests one page with the given cursor, keeping the caller's filters
    and page size. It stops after the last page (``has_more`` false; a full last page answers
    false, there is never an extra empty page), on the defensive guards of :func:`_last_page`,
    or when the caller stops; an error is raised to the caller."""
    while True:
        page = fetch(cursor)
        yield from page.items
        if _last_page(page, cursor):
            return
        cursor = page.next_cursor


def duration_body(value: Duration) -> Dict[str, Any]:
    """A Duration's wire form (``unit`` left out when unset)."""
    body: Dict[str, Any] = {"value": value.value}
    if value.unit:
        body["unit"] = str(value.unit.value if hasattr(value.unit, "value") else value.unit)
    return body


def compact(**pairs: Any) -> Dict[str, Any]:
    """A body without its unset (``None``) and empty-string values."""
    return {key: value for key, value in pairs.items() if value is not None and value != ""}


def money(value: Any) -> Optional[str]:
    """A validated money input's wire form (``Decimal`` → ``str(value)``), ``None`` when unset."""
    return None if value is None else money_text(value)


def metadata_body(body: Dict[str, Any], metadata: Optional[Mapping[str, str]]) -> None:
    """Add ``metadata`` to ``body`` when it has keys (an empty map is left out, as unset). Keys
    with ``""`` are sent as is: on an update they delete the key."""
    if metadata:
        body["metadata"] = dict(metadata)
