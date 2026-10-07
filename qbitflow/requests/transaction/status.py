"""Transaction status request handlers."""

from typing import Union

from qbitflow.dto.transaction.status import TransactionStatus, TransactionType
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest


class TransactionStatusRequests(BaseRequest):
    """
    Check where a transaction stands (``GET /transaction/status``).

    To learn that a payment or subscription settled, use webhooks (recommended — QBitFlow
    notifies your endpoint, see :mod:`qbitflow.webhooks`), or poll :meth:`get`.
    """

    BASE_ROUTE = "/transaction/status"

    def get(self, transaction_uuid: str, transaction_type: TransactionType) -> TransactionStatus:
        """
        Get the status of a transaction.

        Args:
            transaction_uuid: UUID of the transaction (``pay@…``/``sub@…`` prefixed or bare).
            transaction_type: Type of the transaction.

        Returns:
            Current transaction status.

        Raises:
            ValidationError: If ``transaction_uuid`` is empty or ``transaction_type`` is not
                a :class:`TransactionType`.
            NotFoundException: If the transaction is unknown, or exists but has not been
                processed yet (checkout created, customer has not paid).

        Example:
            >>> status = client.transaction_status.get(
            ...     "uuid",
            ...     TransactionType.ONE_TIME_PAYMENT
            ... )
            >>> if status.status == TransactionStatusValue.COMPLETED:
            ...     print("Transaction completed!")
        """
        self._require_identifier(transaction_uuid, "transaction_uuid")
        tx_type = self._require_transaction_type(transaction_type)

        params = {"txUUID": transaction_uuid, "txType": tx_type}

        return self._request_model(TransactionStatus, self.BASE_ROUTE, params=params)

    @staticmethod
    def _require_transaction_type(transaction_type: Union[TransactionType, str]) -> str:
        """Accept a :class:`TransactionType` (or one of its exact string values)."""
        if isinstance(transaction_type, TransactionType):
            return transaction_type.value
        try:
            return TransactionType(transaction_type).value
        except ValueError:
            raise ValidationError(
                "transaction_type must be a TransactionType, e.g. TransactionType.ONE_TIME_PAYMENT"
            ) from None
