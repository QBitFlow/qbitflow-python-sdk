"""
QBitFlow Python SDK
===================

A Python SDK for QBitFlow - Next Generation Crypto Payment Processing.

This SDK provides a simple and intuitive interface for:
- Processing one-time cryptocurrency payments
- Managing recurring subscriptions
- Handling pay-as-you-go subscriptions
- Managing customers and products
- Tracking transaction statuses

Basic Usage
-----------
>>> from qbitflow import QBitFlow
>>> client = QBitFlow(api_key="your_api_key_here")
>>>
>>> # Create a one-time payment session
>>> response = client.one_time_payments.create_session(
...     product_id=1,
...     customer_uuid="customer-uuid-here"
... )
>>> print(response.link)  # Send this link to your customer

For more examples, see the documentation at https://qbitflow.app/docs
"""

from . import dto, exceptions
from .client import QBitFlow
from .utils.duration import Duration

# Local webhook signature verification (no API round-trip required)
from .webhooks import (
    TEST_WEBHOOK_ID,
    canonical_json,
    compute_webhook_signature,
    extract_webhook_headers,
    verify_webhook_signature,
)

__version__ = "2.1.0"

__author__ = "QBitFlow"
__all__ = [
    "QBitFlow",
    "dto",
    "exceptions",
    "Duration",
    # Local webhook verification
    "verify_webhook_signature",
    "compute_webhook_signature",
    "canonical_json",
    "extract_webhook_headers",
    "TEST_WEBHOOK_ID",
]
