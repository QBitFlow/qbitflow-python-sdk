"""
Webhook request handlers.

This module provides API-side webhook signature verification. For verification without a
network round-trip see :mod:`qbitflow.webhooks`.
"""

import json
from typing import Any

from qbitflow.exceptions.exceptions import ValidationError
from qbitflow.webhooks import (
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    HEADER_WEBHOOK_ID,
    TEST_WEBHOOK_ID,
    normalise_payload,
)

from .base_request import BaseRequest

__all__ = [
    "WebhookRequests",
    "HEADER_SIGNATURE",
    "HEADER_TIMESTAMP",
    "HEADER_WEBHOOK_ID",
    "TEST_WEBHOOK_ID",
]


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

    def verify(self, payload: Any, signature: str, timestamp: str) -> bool:
        """
        Verify the authenticity of a webhook request through the QBitFlow API.

        The API answers 200 when the signature is valid and 400 when it is not, so only a
        400 returns False. Every other failure — an unreachable API, a 5xx, an expired API
        key (401), an insufficient role (403) — is raised.

        That distinction matters: reporting a failure as "not verified" would make an
        outage indistinguishable from a forged signature, and a handler that drops
        unverified events would silently discard real payments for as long as the outage
        lasted. Let these raise, answer non-200, and QBitFlow retries the delivery.

        Args:
            payload: The raw request body (``bytes``/``bytearray``/``str``, parsed as JSON) or
                an already-decoded JSON value (``dict``, ``list``, …). ``{}`` and ``[]`` are
                preserved as sent.
            signature: The value of the ``X-Webhook-Signature-256`` header.
            timestamp: The value of the ``X-Webhook-Timestamp`` header.

        Returns:
            True if the signature is valid, False if the API rejected it.

        Raises:
            ValidationError: ``payload`` is not valid JSON (or contains ``NaN`` /
                ``Infinity``), or a header value is empty.
            AuthenticationError: The API key is invalid or expired (401).
            ForbiddenException: The API key's role is below ``user`` (403).
            NetworkError: The API could not be reached.
            ServerError: The API failed to answer the verification request (5xx).

        Example:
            >>> # In your webhook handler
            >>> from qbitflow import QBitFlow, extract_webhook_headers
            >>> client = QBitFlow(api_key="your_api_key_here")
            >>>
            >>> async def webhook_handler(request: Request):
            ...     body = await request.body()
            ...     headers = extract_webhook_headers(request.headers)
            ...     if not client.webhooks.verify(body, headers["signature"], headers["timestamp"]):
            ...         raise HTTPException(status_code=400, detail="Invalid webhook signature")
            ...     # Process the webhook event
        """
        self._require_identifier(signature, "signature")
        self._require_identifier(timestamp, "timestamp")

        if isinstance(payload, (bytes, bytearray, str)):
            try:
                decoded = json.loads(payload, parse_constant=_reject_constant)
            except (ValueError, TypeError) as exc:
                raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
        elif payload is None:
            raise ValidationError("webhook payload is required")
        else:
            decoded = payload

        # A lone surrogate escape (e.g. \ud800) is decoded by the API as U+FFFD; do the same
        # so the body can be encoded as valid UTF-8.
        decoded = normalise_payload(decoded)

        try:
            # NaN / Infinity in an already-decoded payload are rejected when the body is
            # encoded (as the SDK's ValidationError).
            self._make_request(
                f"{self.BASE_ROUTE}/verify",
                "POST",
                data={
                    "payload": decoded,
                    "receivedSignature": signature,
                    "receivedTimestamp": timestamp,
                },
            )
            return True
        except ValidationError as exc:
            if exc.status_code == 400:
                # The API rejects a bad signature with a 400 — a verification result rather
                # than an error the caller has to handle. A 401/403 raises its own type and
                # propagates, so a credentials problem is never reported as a forged signature.
                return False
            raise


def _reject_constant(name: str) -> Any:
    """Refuse ``NaN`` / ``Infinity``: JSON has no such literals and the API rejects them."""
    raise ValidationError(f"webhook payload contains a non-JSON number literal: {name}")
