"""
Customer-related data models.

This module contains data models for customer management operations.
"""

from typing import Optional

from pydantic import Field, field_validator

from qbitflow.utils.helpers import is_valid_email, validate_alphanumspace

from .base_model import GO_ZERO_TIME, Bool, Int, RequestModel, ResponseModel, Str, Timestamp


def _check_name(field_name: str, value: Optional[str]) -> Optional[str]:
    """Apply the API's ``alphanumspace,min=2,max=100`` rule to a provided name."""
    if value is None:
        return value
    problem = validate_alphanumspace(value, 2, 100)
    if problem is not None:
        raise ValueError(f"{field_name} {problem}")
    return value


def _check_email(value: Optional[str]) -> Optional[str]:
    """Apply the SDK's single email rule to a provided address (never normalised)."""
    if value is None:
        return value
    if not is_valid_email(value):
        raise ValueError("email is not a valid email address")
    return value


class Customer(ResponseModel):
    """
    Represents a customer in the QBitFlow system.

    Customers are individuals or entities that make payments through your platform.
    Each customer has a unique UUID and contact information.

    Attributes:
        uuid: Unique identifier for the customer (a bare UUID).
        name: Customer's first name.
        last_name: Customer's last name.
        email: Customer's email address.
        phone_number: Phone number (``""`` when none was given).
        address: Physical address (``""`` when none was given).
        reference: Your own reference ID (``""`` when none was given).
        created_at: Timestamp when the customer was created.
        organization_id: Organization the customer belongs to.
        user_id: Owning user ID (``0`` for organization-level customers).
        test: Whether this is a test-mode customer.

    Example:
        >>> customer = client.customers.get("customer-uuid")
        >>> print(f"{customer.name} {customer.last_name}")
        >>> print(f"Email: {customer.email}")
    """

    uuid: Str = ""
    name: Str = ""
    last_name: Str = ""
    email: Str = ""
    phone_number: Str = ""
    address: Str = ""
    reference: Str = ""
    created_at: Timestamp = GO_ZERO_TIME
    organization_id: Int = 0
    user_id: Int = 0
    test: Bool = False


class CreateCustomerDto(RequestModel):
    """
    Data transfer object for creating a new customer.

    Attributes:
        name: Customer's first name (required; letters, digits, spaces, ``-_'.``;
            2-100 characters).
        last_name: Customer's last name (required; same rule).
        email: Customer's email address (required; kept exactly as given).
        phone_number: Optional phone number.
        address: Optional physical address.
        reference: Optional external reference ID for your records (immutable afterwards).

    Raises:
        ValidationError: (the SDK's) if a value breaks the API's rules.

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

    name: str = Field(..., description="Customer's first name")
    last_name: str = Field(..., description="Customer's last name")
    email: str = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
    reference: Optional[str] = Field(default=None, description="External reference ID")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _check_name("name", v) or v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return _check_name("last_name", v) or v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _check_email(v) or v


class UpdateCustomerDto(RequestModel):
    """
    Data transfer object for updating an existing customer.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields — and ``""``, which the API treats as "not provided" — are
    excluded from the request entirely. An empty ``UpdateCustomerDto()`` is a valid no-op.

    ``reference`` is deliberately absent: a customer reference is immutable and the API
    ignores it on update.

    Attributes:
        name: New first name (letters, digits, spaces, ``-_'.``; 2-100 characters).
        last_name: New last name (same rule).
        email: New email address, unique per organization/user.
        phone_number: New phone number.
        address: New physical address.

    Example:
        >>> # change only the email; every other field is untouched
        >>> customer = client.customers.update(
        ...     "customer-uuid", UpdateCustomerDto(email="newemail@example.com")
        ... )
    """

    name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = Field(default=None, description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return _check_name("name", v) if v != "" else v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        return _check_name("last_name", v) if v != "" else v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _check_email(v) if v != "" else v
