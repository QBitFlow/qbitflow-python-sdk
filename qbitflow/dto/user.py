"""
User-related data models.

This module contains data models for user management operations.
"""

import enum
from typing import Any, Optional, Union

from pydantic import Field, field_validator

from qbitflow.utils.helpers import is_valid_email, validate_alphanumspace, validate_integer

from .base_model import GO_ZERO_TIME, Int, RequestModel, ResponseModel, Str, Timestamp


class UserRole(str, enum.Enum):
    """
    User role enumeration.

    Defines the available roles for users in the system.

    The hierarchy is ``handle < user < admin < owner``.

    Attributes:
        HANDLE: Lowest authenticated tier — a special case of a user, backing the
            second frontend app. Cannot be assigned on create.
        USER: Regular user with limited access.
        ADMIN: Administrator with full access.
        OWNER: Organization owner. Read-only — cannot be assigned on create.
    """

    HANDLE = "handle"
    ADMIN = "admin"
    USER = "user"
    OWNER = "owner"


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


def _check_fee_bps(value: Any) -> Any:
    """The organization fee is an integer from 0 to 5000 basis points."""
    if value is None:
        return value
    problem = validate_integer(value, 0, 5000)
    if problem is not None:
        raise ValueError(f"organization_fee_bps {problem}")
    return value


class User(ResponseModel):
    """
    Represents a user in the QBitFlow system.

    Users are members of your organization who can access the QBitFlow platform
    and manage various aspects of your account.

    Attributes:
        id: Unique identifier for the user.
        name: User's first name.
        last_name: User's last name.
        email: User's email address.
        created_at: Timestamp when the user was created.
        updated_at: Timestamp when the user was last updated.
        organization_id: ID of the organization this user belongs to.
        role: User's role (``handle``, ``user``, ``admin`` or ``owner``). A role this SDK
            does not know yet is kept as a plain string rather than rejected.
        organization_fee_bps: Organization fee in basis points (1 bps = 0.01%).
        claimed_at: When an invited user claimed their account, or ``None`` if not yet.

    Example:
        >>> user = client.users.get()
        >>> print(f"{user.name} {user.last_name} - {user.role}")
    """

    id: Int = 0
    name: Str = ""
    last_name: Str = ""
    email: Str = ""
    created_at: Timestamp = GO_ZERO_TIME
    updated_at: Timestamp = GO_ZERO_TIME
    organization_id: Int = 0
    role: Union[UserRole, str] = Field(default="", union_mode="left_to_right")
    organization_fee_bps: Int = 0
    claimed_at: Optional[Timestamp] = None


class CreateUserDto(RequestModel):
    """
    Data transfer object for creating a new user.

    Attributes:
        name: User's first name (required; letters, digits, spaces, ``-_'.``; 2-100 chars).
        last_name: User's last name (required; same rule).
        email: User's email address (required; kept exactly as given).
        role: User's role (required; ``admin`` or ``user`` only).
        organization_fee_bps: Organization fee in basis points (integer 0-5000, default 0).

    Raises:
        ValidationError: (the SDK's) if a value breaks the API's rules.

    Example:
        >>> new_user = CreateUserDto(
        ...     name="Jane",
        ...     last_name="Smith",
        ...     email="jane@example.com",
        ...     role=UserRole.USER,
        ...     organization_fee_bps=100
        ... )
        >>> user = client.users.create(new_user)
    """

    name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: str = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User's role (admin or user only)")
    organization_fee_bps: int = Field(
        default=0, description="Organization fee in basis points, for example 100 = 1%"
    )

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

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: UserRole) -> UserRole:
        # The API binds this as `oneof=admin user`; `owner` and `handle` exist as read
        # values but cannot be assigned on create, so reject them before the round-trip.
        if v not in (UserRole.ADMIN, UserRole.USER):
            raise ValueError("role must be 'admin' or 'user' when creating a user")
        return v

    @field_validator("organization_fee_bps", mode="before")
    @classmethod
    def validate_fee(cls, v: Any) -> Any:
        return _check_fee_bps(v)


class UpdateUserDto(RequestModel):
    """
    Data transfer object for updating an existing user.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields — and ``""`` for ``name`` / ``last_name`` / ``email``, which
    the API treats as "not provided" — are excluded from the request entirely. An empty
    ``UpdateUserDto()`` is a valid no-op.

    ``password`` is deliberately absent. Changing a password is a JWT-only, self-service
    operation on the API - it cannot be done with an API key, which is the only credential
    this SDK uses. A password sent with an API key is silently ignored by the API (the
    request still returns 200), so exposing it here would be misleading. Change passwords
    from the QBitFlow dashboard instead.

    Attributes:
        name: New first name (letters, digits, spaces, ``-_'.``; 2-100 characters).
        last_name: New last name (same rule).
        email: New email address, unique within the organization.
        organization_fee_bps: New organization fee in basis points (integer 0-5000; an
            explicit 0 is sent). Requires admin authority - an admin/owner key, or an
            organization-level key acting via ``on_behalf_of``. A non-admin caller that sends
            this field is rejected with 403.

    Example:
        >>> # change only the name; the fee and every other field are untouched
        >>> user = client.users.update(1, UpdateUserDto(name="Jane"))
    """

    name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = Field(default=None, description="User's email address")
    organization_fee_bps: Optional[int] = Field(
        default=None,
        description="Organization fee in basis points, for example 100 = 1%. Admin only.",
    )

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

    @field_validator("organization_fee_bps", mode="before")
    @classmethod
    def validate_fee(cls, v: Any) -> Any:
        return _check_fee_bps(v)
