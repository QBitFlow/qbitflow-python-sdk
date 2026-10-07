"""Refund request handlers."""

from typing import List, Optional

from qbitflow.dto.transaction.refund import RefundEntry
from qbitflow.requests.base_request import BaseRequest
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder


class RefundRequests(BaseRequest):
    """
    Handler for refund-related requests.

    Refunds are created by your customers from the checkout/management pages, not through
    the API, so these methods are read-only.

    Example:
        >>> refunds = client.refunds.get_all()
        >>> for refund in refunds:
        ...     print(f"{refund.uuid}: {refund.status}")
    """

    BASE_ROUTE = "/transaction/refunds"

    def get_by_transaction(self, transaction_uuid: str) -> RefundEntry:
        """
        Get the refund associated with a transaction.

        The route is public, but the API honours the SDK's API key, so the result carries the
        same fields as the authenticated feeds.

        Args:
            transaction_uuid: Prefixed id of the original transaction (``pay@<uuid>``).

        Returns:
            Refund entry.

        Raises:
            ValidationError: If ``transaction_uuid`` is empty.
            NotFoundException: If no refund exists for that transaction.

        Example:
            >>> refund = client.refunds.get_by_transaction("pay@...")
            >>> print(f"Status: {refund.status}")
        """
        self._require_identifier(transaction_uuid, "transaction_uuid")

        return self._request_model(
            RefundEntry, f"{self.BASE_ROUTE}/by-transaction/{self._escape_path(transaction_uuid)}"
        )

    def get_all(self) -> List[RefundEntry]:
        """
        Get all refunds awaiting a merchant response (``responded_at`` is ``None``).

        Returns:
            List of refund entries (plain list, not paginated).

        Example:
            >>> refunds = client.refunds.get_all()
            >>> print(f"Pending refunds: {len(refunds)}")
        """
        return self._request_list(RefundEntry, f"{self.BASE_ROUTE}/all")

    def get_all_inactive(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorData[RefundEntry, str]:
        """
        Get handled refunds (approved/refused/failed) with cursor pagination.

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from a previous response.

        Returns:
            One page of handled refunds.

        Example:
            >>> page = client.refunds.get_all_inactive(limit=10)
            >>> for refund in page.items:
            ...     print(f"{refund.uuid}: {refund.status}")
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        return self._request_model(
            CursorData[RefundEntry, str], f"{self.BASE_ROUTE}/all/inactive", params=params
        )
