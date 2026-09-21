"""Refund request handlers."""

from typing import List, Optional

from qbitflow.dto.transaction.refund import RefundEntry
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder


class RefundRequests(BaseRequest):
    """
    Handler for refund-related requests.

    Example:
        >>> refunds = client.refunds.get_all()
        >>> for refund in refunds:
        ...     print(f"{refund.uuid}: {refund.status.value}")
    """

    BASE_ROUTE = "/transaction/refunds"

    def get_by_transaction(self, transaction_uuid: str) -> RefundEntry:
        """
        Get the refund associated with a transaction.

        This is a public endpoint — no authentication required.

        Args:
            transaction_uuid: UUID of the original transaction.

        Returns:
            Refund entry.

        Example:
            >>> refund = client.refunds.get_by_transaction("tx-uuid")
            >>> print(f"Status: {refund.status.value}")
        """
        if not transaction_uuid:
            raise ValidationError("Transaction UUID cannot be empty")

        res = self._make_request(
            f"{self.BASE_ROUTE}/by-transaction/{transaction_uuid}",
            "GET",
        )
        return RefundEntry(**res)

    def get_all(self) -> List[RefundEntry]:
        """
        Get all active refunds for the authenticated organization.

        Returns:
            List of refund entries.

        Example:
            >>> refunds = client.refunds.get_all()
            >>> print(f"Total refunds: {len(refunds)}")
        """
        res = self._make_request(f"{self.BASE_ROUTE}/all", "GET")
        return [RefundEntry(**item) for item in res]

    def get_all_inactive(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorData[RefundEntry, str]:
        """
        Get all inactive (processed) refunds with cursor pagination.

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from a previous response.

        Returns:
            Paginated inactive refund data.

        Example:
            >>> page = client.refunds.get_all_inactive(limit=10)
            >>> for refund in page.items:
            ...     print(f"{refund.uuid}: {refund.status.value}")
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        res = self._make_request(f"{self.BASE_ROUTE}/all/inactive", "GET", params=params)
        return CursorData[RefundEntry, str](**res)
