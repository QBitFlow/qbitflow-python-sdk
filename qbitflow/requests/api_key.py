"""
API key request handlers.

This module provides methods for managing API keys via the QBitFlow API.
"""

from typing import List

from .base_request import BaseRequest, SuccessResponse
from qbitflow.dto import api_key as dto
from qbitflow.exceptions import ValidationError


class ApiKeyRequests(BaseRequest):
    """Handler for API key-related API requests."""
    
    BASE_ROUTE = "/api-key"
    
    def create(self, data: dto.CreateApiKeyDto) -> dto.CreatedKeyResponse:
        """
        Create a new API key.
        
        Returns the created key information. Note: The actual key value
        is only returned once during creation.
        """
        res = self._make_request(f"{self.BASE_ROUTE}/", "POST", data.model_dump())
        return dto.CreatedKeyResponse(**res)
    
    def get_all(self) -> List[dto.ApiKey]:
        """Get all API keys for the current user."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "GET")
        return [dto.ApiKey(**item) for item in res]
    
    def get_for_user(self, user_id: int) -> List[dto.ApiKey]:
        """Get all API keys for a specific user."""
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
        
        res = self._make_request(f"{self.BASE_ROUTE}/user/{user_id}", "GET")
        return [dto.ApiKey(**item) for item in res]
    
    def delete(self, api_key_id: int) -> SuccessResponse:
        """Delete an API key."""
        if api_key_id <= 0:
            raise ValidationError("API key ID must be positive")
        
        endpoint = f"{self.BASE_ROUTE}/{api_key_id}"
        res = self._make_request(endpoint, "DELETE")
        return SuccessResponse(**res)
