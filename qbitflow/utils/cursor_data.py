
"""
Cursor-based pagination utility.

This module provides a generic CursorData class for handling paginated API responses.
"""

from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, ConfigDict, Field


T = TypeVar('T')  # Type of items in the list
V = TypeVar('V')  # Type of cursor value


class CursorData(BaseModel, Generic[T, V]):
    """
    Generic container for cursor-based paginated data.
    
    This class represents a page of results with a cursor for fetching the next page.
    
    Type Parameters:
        T: The type of items in the list.
        V: The type of the cursor value (typically str or int).
    
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
    
    items: List[T] = Field(
        default_factory=list,
        description="List of items in the current page"
    )
    next_cursor: Optional[V] = Field(
        default=None,
        description="Cursor for fetching the next page (None if last page)",
        alias="nextCursor"
    )
    

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
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

