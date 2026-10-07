"""
API key request handlers.

This module provides read-only access to API keys via the QBitFlow API.

API-key creation and deletion are JWT-only operations on the API and cannot be
performed with an API key, so they are not exposed by the SDK. Manage keys from
the QBitFlow dashboard instead.
"""

from typing import List

from qbitflow.dto import api_key as dto

from .base_request import BaseRequest


class ApiKeyRequests(BaseRequest):
    """Handler for read-only API key requests."""

    BASE_ROUTE = "/api-key"

    def get_all(self) -> List[dto.ApiKey]:
        """
        Get the caller's API keys.

        A ``user``-role key sees only its own keys; an admin/owner (and an organization-level
        key) sees every key in the organization.
        """
        return self._request_list(dto.ApiKey, f"{self.BASE_ROUTE}/")

    def get_for_user(self, user_id: int) -> List[dto.ApiKey]:
        """
        Get all API keys for a specific user of your organization (admin only).

        Raises:
            ValidationError: If ``user_id`` is not a positive integer.
            ForbiddenException: If the caller is not an admin.
            NotFoundException: If the user is not in the caller's organization.
        """
        self._require_positive_id(user_id, "user_id")

        return self._request_list(dto.ApiKey, f"{self.BASE_ROUTE}/user/{user_id}")
