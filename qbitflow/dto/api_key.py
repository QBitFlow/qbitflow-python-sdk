"""
API key-related data models.

This module contains data models for API key management operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from .base_model import BaseModel
from .user import UserRole


class ApiKey(BaseModel):
    """
    Represents an API key in the QBitFlow system.

    API keys are used to authenticate requests to the QBitFlow API.

    Attributes:
        id: Unique identifier for the API key.
        name: Descriptive name for the API key.
        organization_id: ID of the organization this key belongs to.
        user_id: ID of the user who created this key.
        created_at: Timestamp when the key was created.
        expires_at: Optional expiration timestamp.
        role: Role associated with this API key.
        test: Whether this is a test mode API key.

    Example:
        >>> api_key = client.api_keys.get(1)
        >>> print(f"{api_key.name} - Test: {api_key.test}")
    """

    id: int = Field(..., description="Unique identifier for the API key")
    name: str = Field(..., description="Descriptive name for the API key")
    organization_id: int = Field(..., description="Organization ID")
    user_id: int = Field(..., description="User ID who created the key")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(
        default=None, description="Expiration timestamp (null when the key never expires)"
    )
    role: UserRole = Field(..., description="Role associated with the key")
    test: bool = Field(..., description="Whether this is a test mode key")
