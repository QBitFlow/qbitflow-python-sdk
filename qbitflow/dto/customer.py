"""
Customer-related data models.

This module contains data models for customer management operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from .base_model import BaseModel


class Customer(BaseModel):
    """
    Represents a customer in the QBitFlow system.

    Customers are individuals or entities that make payments through your platform.
    Each customer has a unique UUID and contact information.

    Attributes:
        uuid: Unique identifier for the customer.
        name: Customer's first name.
        last_name: Customer's last name.
        email: Customer's email address.
        phone_number: Optional phone number.
        address: Optional physical address.
        reference: Optional external reference ID for your records.
        created_at: Timestamp when the customer was created.

    Example:
        >>> customer = client.customers.get("customer-uuid")
        >>> print(f"{customer.name} {customer.last_name}")
        >>> print(f"Email: {customer.email}")
    """

    uuid: str = Field(..., description="Unique identifier for the customer")
    name: str = Field(..., description="Customer's first name")
    last_name: str = Field(..., description="Customer's last name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
    reference: Optional[str] = Field(default=None, description="External reference ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    test: bool = Field(
        default=False,
        description="Whether this is a test-mode customer (test and live are isolated)",
    )
    organization_id: Optional[int] = Field(
        default=None, description="Organization ID (returned only when authenticated)"
    )
    user_id: Optional[int] = Field(
        default=None, description="User ID (returned only when authenticated)"
    )


class CreateCustomerDto(BaseModel):
    """
    Data transfer object for creating a new customer.

    Use this model to provide customer information when creating a new customer.

    Attributes:
        name: Customer's first name (required).
        last_name: Customer's last name (required).
        email: Customer's email address (required).
        phone_number: Optional phone number.
        address: Optional physical address.
        reference: Optional external reference ID for your records.

    Example:
        >>> new_customer = CreateCustomerDto(
        ...     name="John",
        ...     last_name="Doe",
        ...     email="john@example.com",
        ...     phone_number="+1234567890",
        ...     reference="CRM-12345"
        ... )
        >>> customer = client.customers.create(new_customer)
    """

    name: str = Field(..., min_length=1, description="Customer's first name")
    last_name: str = Field(..., min_length=1, description="Customer's last name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
    reference: Optional[str] = Field(default=None, description="External reference ID")


class UpdateCustomerDto(BaseModel):
    """
    Data transfer object for updating an existing customer.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields are excluded from the request entirely. An empty
    ``UpdateCustomerDto()`` is a valid no-op.

    ``reference`` is deliberately absent: a customer reference is immutable and the API
    ignores it on update.

    Attributes:
        name: New first name, 2-100 characters.
        last_name: New last name, 2-100 characters.
        email: New email address, unique per organization/user.
        phone_number: New phone number.
        address: New physical address.

    Example:
        >>> # change only the email; every other field is untouched
        >>> customer = client.customers.update(
        ...     "customer-uuid", UpdateCustomerDto(email="newemail@example.com")
        ... )
    """

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = Field(default=None, description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
