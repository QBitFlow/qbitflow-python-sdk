"""
Cursor-based pagination utility.

This module provides a generic CursorData class for handling paginated API responses.
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import Field

from qbitflow.dto.base_model import ResponseModel
from qbitflow.exceptions.exceptions import ValidationError

T = TypeVar("T")  # Type of items in the list
V = TypeVar("V")  # Type of cursor value


class CursorData(ResponseModel, Generic[T, V]):
    """
    Generic container for cursor-based paginated data.

    This class represents a page of results with a cursor for fetching the next page. An
    ``items`` the API sends as ``null`` (or omits) is an empty list.

    Type Parameters:
        T: The type of items in the list.
        V: The type of the cursor value (typically str).

    Attributes:
        items: List of items in the current page.
        next_cursor: Cursor value for fetching the next page, or None if this is the last page.

    Examples:
        >>> # Iterate through all payments
        >>> cursor = None
        >>> while True:
        ...     page = client.one_time_payments.get_all(limit=10, cursor=cursor)
        ...     for payment in page.items:
        ...         print(payment.uuid)
        ...     if page.next_cursor is None:
        ...         break
        ...     cursor = page.next_cursor
    """

    items: List[T] = Field(default_factory=list, description="List of items in the current page")
    next_cursor: Optional[V] = Field(
        default=None,
        description="Cursor for fetching the next page (None if last page)",
        alias="nextCursor",
    )

    def has_more(self) -> bool:
        """
        Check if there are more pages available.

        Returns:
            True if there are more pages, False otherwise.
        """
        return self.next_cursor is not None

    def __len__(self) -> int:
        """Return the number of items in the current page."""
        return len(self.items)


def cursor_query_builder(
    limit: Optional[int] = None, cursor: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Build the query parameters for cursor-based pagination.

    Args:
        limit: Maximum number of results per page (a positive integer).
        cursor: Pagination cursor from a previous response. ``None`` or ``""`` starts from the
            first page.

    Returns:
        A dictionary containing the query parameters for the request.

    Raises:
        ValidationError: If ``limit`` is not a positive integer.
    """
    params: Dict[str, Any] = {}
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        params["limit"] = limit
    if cursor is not None and cursor != "":
        params["cursor"] = cursor

    return params
