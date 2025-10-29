
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
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    role: UserRole = Field(..., description="Role associated with the key")
    test: bool = Field(..., description="Whether this is a test mode key")


class CreateApiKeyDto(BaseModel):
    """
    Data transfer object for creating a new API key.
    
    Attributes:
        name: Descriptive name for the API key (required).
        user_id: ID of the user creating the key (required).
        expires_at: Optional expiration timestamp.
        role: Role to associate with the key (required).
        test: Whether this should be a test mode key (required).
    
    Example:
        >>> new_key = CreateApiKeyDto(
        ...     name="Production API Key",
        ...     user_id=1,
        ...     role=UserRole.ADMIN,
        ...     test=False
        ... )
        >>> api_key = client.api_keys.create(new_key)
    """
    
    name: str = Field(..., min_length=1, description="Descriptive name for the API key")
    user_id: int = Field(..., gt=0, description="User ID creating the key")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    test: bool = Field(..., description="Whether this is a test mode key")


class CreatedKeyResponse(BaseModel):
    """
        Response when a new API key is created.
        
        This contains the actual API key value which is only shown once during creation.
        
        Attributes:
            data: The created API key information.
            key: The actual API key value (only shown once).
        
        Example:
            >>> response = client.api_keys.create(new_key_dto)
            >>> print(f"Save this key: {response.key}")
            >>> print(f"Key ID: {response.data.id}")
        """
    
    data: ApiKey = Field(..., description="Created API key information")
    key: str = Field(..., description="The actual API key value (only shown once)")
