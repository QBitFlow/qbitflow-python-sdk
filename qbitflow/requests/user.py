"""
User request handlers.

This module provides methods for managing users via the QBitFlow API.
"""

from typing import List

from .base_request import BaseRequest, SuccessResponse
from qbitflow.dto import user as dto
from qbitflow.exceptions import ValidationError


class UserRequests(BaseRequest):
    """Handler for user-related API requests."""
    
    BASE_ROUTE = "/user"
    
    def create(self, user: dto.CreateUserDto) -> dto.User:
        """Create a new user."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "POST", user.model_dump())
        return dto.User(**res)
    
    def get_all(self) -> List[dto.User]:
        """Get all users."""
        res = self._make_request(f"{self.BASE_ROUTE}/all", "GET")
        return [dto.User(**item) for item in res]
    
    def get(self) -> dto.User:
        """Get the current user (based on API key)."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "GET")
        return dto.User(**res)
    
    def get_by_id(self, user_id: int) -> dto.User:
        """Get a user by their ID. Must be an admin to use this method, and the user must be in the same organization."""
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
        
        res = self._make_request(f"{self.BASE_ROUTE}/id/{user_id}", "GET")
        return dto.User(**res)

    def get_by_email(self, email: str) -> dto.User:
        """Get a user by their email. Must be an admin to use this method, and the user must be in the same organization."""
        if not email:
            raise ValidationError("Email must not be empty")
        
        res = self._make_request(f"{self.BASE_ROUTE}/email/{email}", "GET")
        return dto.User(**res)
    
    def update(self, user_id: int, user: dto.UpdateUserDto) -> dto.User:
        """Update an existing user."""
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
        
        res = self._make_request(f"{self.BASE_ROUTE}/{user_id}", "PUT", user.model_dump())
        return dto.User(**res)
    
    def delete(self, user_id: int) -> SuccessResponse:
        """Delete a user."""
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
        
        res = self._make_request(f"{self.BASE_ROUTE}/{user_id}", "DELETE")
        return SuccessResponse(**res)
