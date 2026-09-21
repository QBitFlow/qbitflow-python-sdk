"""Transaction status request handlers."""

from qbitflow import config
from qbitflow.dto.transaction.status import TransactionStatus, TransactionType
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest


class TransactionStatusRequests(BaseRequest):
    """
    Check where a transaction stands.

    This endpoint is public. The API also exposes a WebSocket at
    ``/transaction/status/ws`` carrying the same query parameters. This SDK does not open
    the socket for you - that would pull in a WebSocket dependency every user pays for, and
    the right client differs between asyncio, threads and a WSGI worker. Use
    :meth:`get_websocket_url` to build the URL and connect with the client of your choice,
    poll :meth:`get`, or rely on webhooks, which are the recommended way to learn that a
    payment settled.
    """

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

    def get_websocket_url(self, transaction_uuid: str, transaction_type: TransactionType) -> str:
        """
        Build the WebSocket URL for real-time status updates on a transaction.

        The SDK does not manage the connection - connect with whichever WebSocket client
        suits your runtime (``websockets`` for asyncio, ``websocket-client`` for threads).
        The scheme is derived from the configured base URL, so an ``https`` API becomes
        ``wss`` and a local ``http`` one becomes ``ws``.

        Args:
            transaction_uuid: UUID of the transaction, with or without its prefix.
            transaction_type: Type of the transaction.

        Returns:
            The full ``ws(s)://`` URL, query parameters included.

        Raises:
            ValidationError: If the transaction UUID is empty.

        Example:
            >>> url = client.transaction_status.get_websocket_url(
            ...     "pay@uuid", TransactionType.ONE_TIME_PAYMENT
            ... )
            >>> # then, with the websockets package:
            >>> # async with websockets.connect(url) as ws: ...
        """
        if not transaction_uuid:
            raise ValidationError("Transaction UUID cannot be empty")

        base = config.get_base_url()
        ws_base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)

        return (
            f"{ws_base}{self.BASE_ROUTE}/ws"
            f"?txUUID={transaction_uuid}&txType={transaction_type.value}"
        )
