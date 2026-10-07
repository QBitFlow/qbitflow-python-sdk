"""
API key-related data models.

This module contains data models for API key management operations.
"""

from typing import Optional, Union

from pydantic import Field

from .base_model import GO_ZERO_TIME, Bool, Int, ResponseModel, Str, Timestamp
from .user import UserRole


class ApiKey(ResponseModel):
    """
    Represents an API key in the QBitFlow system.

    API keys are used to authenticate requests to the QBitFlow API. The hashed key
    material is never returned; the plaintext key is shown once, at creation, in the
    dashboard.

    Attributes:
        id: Unique identifier for the API key.
        name: Descriptive name for the API key.
        organization_id: ID of the organization this key belongs to.
        user_id: ID of the user this key is bound to (``0`` for an organization-level key).
        created_at: Timestamp when the key was created.
        expires_at: Expiration timestamp, or ``None`` when the key never expires.
        role: Role the key carries (``user`` or ``admin``; a value this SDK does not know
            yet is kept as a plain string).
        test: Whether this is a test mode API key.

    Example:
        >>> for api_key in client.api_keys.get_all():
        ...     print(f"{api_key.name} - role {api_key.role} - test: {api_key.test}")
    """

    id: Int = 0
    name: Str = ""
    organization_id: Int = 0
    user_id: Int = 0
    created_at: Timestamp = GO_ZERO_TIME
    expires_at: Optional[Timestamp] = None
    role: Union[UserRole, str] = Field(default="", union_mode="left_to_right")
    test: Bool = False
