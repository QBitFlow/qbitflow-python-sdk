"""
Webhook request handlers.

This module provides methods for managing Webhooks via the QBitFlow API.
"""

import json

from qbitflow.exceptions.exceptions import APIError, InvalidRequestError

from .base_request import BaseRequest

# Frontend test webhook ID for testing purposes and ensure that the webhook can be reached
TEST_WEBHOOK_ID = "test-webhook-id"


# HMAC headers
HEADER_SIGNATURE = "X-Webhook-Signature-256"
HEADER_TIMESTAMP = "X-Webhook-Timestamp"
HEADER_WEBHOOK_ID = "X-Webhook-ID"


class WebhookRequests(BaseRequest):
    """Handler for Webhook-related API requests."""

    BASE_ROUTE = "/webhooks"

    def get_signature_header(self) -> str:
        """Return the name of the header used for webhook signatures."""
        return HEADER_SIGNATURE

    def get_timestamp_header(self) -> str:
        """Return the name of the header used for webhook timestamps."""
        return HEADER_TIMESTAMP

    def get_webhook_id_header(self) -> str:
        """Return the name of the header used for webhook IDs."""
        return HEADER_WEBHOOK_ID

    def verify(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """
        Verify the authenticity of a webhook request.

        Args:
            payload: The raw request body (bytes).
            signature: The signature from the 'X-QBitFlow-Signature' header.
            timestamp: The timestamp from the 'X-QBitFlow-Timestamp' header.

        Returns:
            True if the webhook is valid, False otherwise.

        Example:
            >>> # In your webhook handler
            >>> from qbitflow import QBitFlow
            >>> client = QBitFlow(api_key="your_api_key_here")
            >>>
            >>> def webhook_handler(
            ...     request: Request,
            ...     x_webhook_signature_256: Annotated[str, Header()],
            ...     x_webhook_timestamp: Annotated[str, Header()]
            ... ):
            ...     # Read raw request body for signature verification
            ...     body = await request.body()
            ...
            ...     # Verify the authenticity of the webhook request
            ...     if not qbitflow_client.webhooks.verify(
            ...         payload=body,
            ...         signature=x_webhook_signature_256,
            ...         timestamp=x_webhook_timestamp
            ...     ):
            ...         print("❌ Invalid webhook signature")
            ...         raise HTTPException(status_code=400, detail="Invalid webhook signature")
            ...
            ...     # Process the webhook event
            ...     # ...
        """

        try:
            self._make_request(
                f"{self.BASE_ROUTE}/verify",
                "POST",
                data={
                    "payload": json.loads(payload),  # Parse bytes to dict for sending to API
                    "receivedSignature": signature,
                    "receivedTimestamp": timestamp,
                },
            )
            return True
        except InvalidRequestError:
            # QBitFlow returns 400 for invalid webhooks, raised as InvalidRequestError.
            return False
        except Exception as e:
            raise APIError(f"Error verifying webhook: {str(e)}")
