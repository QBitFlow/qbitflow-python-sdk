"""Transaction status request handlers."""

from qbitflow.requests.base_request import BaseRequest
from qbitflow.dto.transaction.status import TransactionStatus, TransactionType
from qbitflow.exceptions import ValidationError


class TransactionStatusRequests(BaseRequest):
    """Handler for transaction status requests."""

    BASE_ROUTE = "/transaction/status"

    def get(self, transaction_uuid: str, transaction_type: TransactionType) -> TransactionStatus:
        """
        Get the status of a transaction.

        Args:
            transaction_uuid: UUID of the transaction.
            transaction_type: Type of the transaction.

        Returns:
            Current transaction status.

        Example:
            >>> status = client.transaction_status.get(
            ...     "uuid",
            ...     TransactionType.ONE_TIME_PAYMENT
            ... )
            >>> if status.status == TransactionStatusValue.COMPLETED:
            ...     print("Transaction completed!")
        """
        if not transaction_uuid:
            raise ValidationError("Transaction UUID cannot be empty")

        params = {
            "txUUID": transaction_uuid,
            "txType": transaction_type.value,
        }

        res = self._make_request(self.BASE_ROUTE, "GET", params=params)
        return TransactionStatus(**res)
