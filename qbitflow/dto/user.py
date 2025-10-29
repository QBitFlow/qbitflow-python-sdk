
"""
User-related data models.

This module contains data models for user management operations.
"""

from datetime import datetime
import enum
from typing import Optional
from pydantic import Field, EmailStr

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


class CreateUserDto(BaseModel):
    """
    Data transfer object for creating a new user.
    
    Attributes:
        name: User's first name (required).
        last_name: User's last name (required).
        email: User's email address (required).
        password: User's password (required).
        role: User's role (required).
        organization_fee_bps: Organization fee in basis points (required, must be non-negative).
    
    Example:
        >>> new_user = CreateUserDto(
        ...     name="Jane",
        ...     last_name="Smith",
        ...     email="jane@example.com",
        ...     password="securepassword123",
        ...     role=UserRole.USER,
        ...     organization_fee_bps=100
        ... )
        >>> user = client.users.create(new_user)
    """
    
    name: str = Field(..., min_length=1, description="User's first name")
    last_name: str = Field(..., min_length=1, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    role: UserRole = Field(..., description="User's role")
    organization_fee_bps: int = Field(default=0, ge=0, le=1000, description="Organization fee in basis points, for example 100 = 1%")


class UpdateUserDto(BaseModel):
    """
    Data transfer object for updating an existing user.
    
    Attributes:
        name: New first name (required).
        last_name: New last name (required).
        email: New email address (required).
        password: New password (required).
        organization_fee_bps: New organization fee in basis points (required, must be non-negative).
    
    Example:
        >>> update_data = UpdateUserDto(
        ...     name="Jane",
        ...     last_name="Doe",
        ...     email="jane.doe@example.com",
        ...     password="newpassword123",
        ...     organization_fee_bps=150
        ... )
        >>> user = client.users.update(1, update_data)
    """
    
    name: str = Field(..., min_length=1, description="User's first name")
    last_name: str = Field(..., min_length=1, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    password: Optional[str] = Field(default=None, min_length=8, description="User's password")
    organization_fee_bps: int = Field(default=0, ge=0, le=1000, description="Organization fee in basis points, for example 100 = 1%")
