"""
Data Transfer Objects (DTOs) for QBitFlow SDK.

This package contains all the data models used throughout the SDK for
representing API requests and responses.
"""

from . import transaction
from .accounting import AccountingEvent
from .api_key import ApiKey
from .base_model import BaseModel
from .claim import (
    ClaimFund,
    ClaimRequest,
    CreateClaimRequestResponse,
    Organization,
)
from .customer import CreateCustomerDto, Customer, UpdateCustomerDto
from .product import CreateProductDto, Product, UpdateProductDto
from .user import CreateUserDto, UpdateUserDto, User, UserRole

__all__ = [
    "BaseModel",
    "transaction",
    "Customer",
    "CreateCustomerDto",
    "UpdateCustomerDto",
    "Product",
    "CreateProductDto",
    "UpdateProductDto",
    "User",
    "UserRole",
    "CreateUserDto",
    "UpdateUserDto",
    "ApiKey",
    "AccountingEvent",
    "ClaimRequest",
    "Organization",
    "CreateClaimRequestResponse",
    "ClaimFund",
]
