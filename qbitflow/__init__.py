
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

from .client import QBitFlow
from . import dto
from . import exceptions
from .utils.duration import Duration

__version__ = "1.3.1"
__author__ = "QBitFlow"
__all__ = ["QBitFlow", "dto", "exceptions", "Duration"]
