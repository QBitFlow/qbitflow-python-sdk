"""
QBitFlow Python SDK
===================

A Python SDK for QBitFlow - Next Generation Crypto Payment Processing.

This SDK provides a simple and intuitive interface for:
- Processing one-time cryptocurrency payments
- Managing recurring subscriptions
- Managing customers and products
- Tracking transaction statuses
- Verifying webhooks (locally or through the API)

Basic Usage
-----------
>>> from qbitflow import QBitFlow
>>> client = QBitFlow(api_key="your_api_key_here")
>>>
>>> # Create a one-time payment session
>>> response = client.one_time_payments.create_session(product_id=1)
>>> print(response.link)  # Send this link to your customer

For more examples, see the documentation at https://qbitflow.app/docs
"""

from . import dto, exceptions
from ._version import __version__
from .client import QBitFlow
from .dto.base_model import GO_ZERO_TIME
from .utils.duration import Duration

# Local webhook signature verification (no API round-trip required)
from .webhooks import (
    DEFAULT_MAX_TIMESTAMP_AGE_SECONDS,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    HEADER_WEBHOOK_ID,
    TEST_WEBHOOK_ID,
    WebhookHeaders,
    canonical_json,
    compute_webhook_signature,
    extract_webhook_headers,
    parse_session_webhook,
    parse_subscription_webhook,
    verify_webhook_signature,
)

__author__ = "QBitFlow"
__all__ = [
    "QBitFlow",
    "dto",
    "exceptions",
    "Duration",
    "GO_ZERO_TIME",
    "__version__",
    # Local webhook verification
    "verify_webhook_signature",
    "compute_webhook_signature",
    "canonical_json",
    "extract_webhook_headers",
    "WebhookHeaders",
    # Webhook payload parsing (after verification)
    "parse_session_webhook",
    "parse_subscription_webhook",
    "TEST_WEBHOOK_ID",
    "HEADER_SIGNATURE",
    "HEADER_TIMESTAMP",
    "HEADER_WEBHOOK_ID",
    "DEFAULT_MAX_TIMESTAMP_AGE_SECONDS",
]
