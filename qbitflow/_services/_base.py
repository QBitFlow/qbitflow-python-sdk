"""What every service shares: a reference to its client, the call helpers, the iterator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, Optional, Type, TypeVar

from .._transport import Endpoint, RequestOptions, Response, decode
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


def iterate_pages(fetch: Callable[[Optional[str]], Page[T]], cursor: Optional[str]) -> Iterator[T]:
    """Walk a cursor-paginated list lazily, one request per page, from ``cursor`` (``None`` = the
    first page). It stops on the last page (``next_cursor`` ``None``), on an empty page, on a
    cursor that does not move, or when the caller stops; an error is raised to the caller."""
    while True:
        page = fetch(cursor)
        yield from page.items
        if page.next_cursor is None or not page.items or page.next_cursor == cursor:
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
