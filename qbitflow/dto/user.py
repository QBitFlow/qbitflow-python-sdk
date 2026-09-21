"""
User-related data models.

This module contains data models for user management operations.
"""

import enum
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from .base_model import BaseModel


class UserRole(str, enum.Enum):
    """
    User role enumeration.

    Defines the available roles for users in the system.

    Attributes:
        ADMIN: Administrator with full access.
        USER: Regular user with limited access.
    """

    ADMIN = "admin"
    USER = "user"
    OWNER = "owner"


class User(BaseModel):
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
        role: User's role (ADMIN or USER).
        organization_fee_bps: Organization fee in basis points (1 bps = 0.01%).

    Example:
        >>> user = client.users.get(1)
        >>> print(f"{user.name} {user.last_name} - {user.role.value}")
    """

    id: int = Field(..., description="Unique identifier for the user")
    name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    organization_id: int = Field(..., description="Organization ID")
    role: UserRole = Field(..., description="User's role")
    organization_fee_bps: int = Field(..., ge=0, description="Organization fee in basis points")
    claimed_at: Optional[datetime] = Field(
        default=None,
        description="Set once an invited user has claimed their account (e.g. set a password)",
    )


class CreateUserDto(BaseModel):
    """
    Data transfer object for creating a new user.

    Attributes:
        name: User's first name (required).
        last_name: User's last name (required).
        email: User's email address (required).
        role: User's role (required).
        organization_fee_bps: Organization fee in basis points (required, must be non-negative).

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

    name: str = Field(..., min_length=1, description="User's first name")
    last_name: str = Field(..., min_length=1, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User's role")
    organization_fee_bps: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="Organization fee in basis points, for example 100 = 1%",
    )


class UpdateUserDto(BaseModel):
    """
    Data transfer object for updating an existing user.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields are excluded from the request entirely. An empty
    ``UpdateUserDto()`` is a valid no-op.

    ``password`` is deliberately absent. Changing a password is a JWT-only, self-service
    operation on the API - it cannot be done with an API key, which is the only credential
    this SDK uses. A password sent with an API key is silently ignored by the API (the
    request still returns 200), so exposing it here would be misleading. Change passwords
    from the QBitFlow dashboard instead.

    Attributes:
        name: New first name, 2-100 characters.
        last_name: New last name, 2-100 characters.
        email: New email address, unique within the organization.
        organization_fee_bps: New organization fee in basis points (0-5000). Requires admin
            authority - an admin/owner key, or an organization-level key acting via
            ``on_behalf_of``. A non-admin caller that sends this field is rejected with 403.

    Example:
        >>> # change only the name; the fee and every other field are untouched
        >>> user = client.users.update(1, UpdateUserDto(name="Jane"))
    """

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = Field(default=None, description="User's email address")
    organization_fee_bps: Optional[int] = Field(
        default=None,
        ge=0,
        le=5000,
        description="Organization fee in basis points, for example 100 = 1%. Admin only.",
    )
