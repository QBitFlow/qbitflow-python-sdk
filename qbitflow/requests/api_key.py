"""
API key request handlers.

This module provides read-only access to API keys via the QBitFlow API.

API-key creation and deletion are JWT-only operations on the API and cannot be
performed with an API key, so they are not exposed by the SDK. Manage keys from
the QBitFlow dashboard instead.
"""

from typing import List

from qbitflow.dto import api_key as dto
from qbitflow.exceptions import ValidationError

from .base_request import BaseRequest


class ApiKeyRequests(BaseRequest):
    """Handler for read-only API key requests."""

    BASE_ROUTE = "/api-key"

    def get_all(self) -> List[dto.ApiKey]:
        """Get all API keys for the current user."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "GET")
        return [dto.ApiKey(**item) for item in res]

    def get_for_user(self, user_id: int) -> List[dto.ApiKey]:
        """Get all API keys for a specific user (admin only)."""
        if user_id <= 0:
            raise ValidationError("User ID must be positive")

        res = self._make_request(f"{self.BASE_ROUTE}/user/{user_id}", "GET")
        return [dto.ApiKey(**item) for item in res]
