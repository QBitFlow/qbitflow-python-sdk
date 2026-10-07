"""
User request handlers.

This module provides methods for managing users via the QBitFlow API.
"""

from typing import List

from qbitflow.dto import user as dto

from .base_request import BaseRequest, SuccessResponse


class UserRequests(BaseRequest):
    """Handler for user-related API requests."""

    BASE_ROUTE = "/user"

    def create(self, user: dto.CreateUserDto) -> dto.User:
        """
        Create a new user in your organization (admin only).

        The created user is *unclaimed*: they cannot log in until they follow a claim
        request link (see ``client.claims``).
        """
        body = self._body(dto.CreateUserDto, user)
        return self._request_model(dto.User, f"{self.BASE_ROUTE}/", "POST", body)

    def get_all(self) -> List[dto.User]:
        """Get all users of your organization (admin only)."""
        return self._request_list(dto.User, f"{self.BASE_ROUTE}/all")

    def get(self) -> dto.User:
        """Get the current user (the API key's user, or the acted-for user with on_behalf_of)."""
        return self._request_model(dto.User, f"{self.BASE_ROUTE}/")

    def get_by_id(self, user_id: int) -> dto.User:
        """Get a user by their ID.

        Requires an admin, and the user must be in the same organization.

        Raises:
            ValidationError: If ``user_id`` is not a positive integer.
        """
        self._require_positive_id(user_id, "user_id")

        return self._request_model(dto.User, f"{self.BASE_ROUTE}/id/{user_id}")

    def get_by_email(self, email: str) -> dto.User:
        """Get a user by their email.

        Requires an admin, and the user must be in the same organization.

        Raises:
            ValidationError: If ``email`` is not a valid address.
        """
        self._require_email(email)

        return self._request_model(dto.User, f"{self.BASE_ROUTE}/email/{self._escape_path(email)}")

    def update(self, user_id: int, user: dto.UpdateUserDto) -> dto.User:
        """
        Update an existing user (partial update).

        A ``user``-role key may update only itself; admins may update any user of the
        organization except the owner.

        Raises:
            ValidationError: If ``user_id`` is not a positive integer or the API rejects the
                data.
            ForbiddenException: If the caller may not modify that user (or sent
                ``organization_fee_bps`` without admin authority).
        """
        self._require_positive_id(user_id, "user_id")

        # Partial update: unset fields must be omitted, not sent as null. In particular
        # organization_fee_bps must never be transmitted unless the caller set it.
        body = self._body(dto.UpdateUserDto, user)
        return self._request_model(dto.User, f"{self.BASE_ROUTE}/{user_id}", "PUT", body)

    def delete(self, user_id: int) -> SuccessResponse:
        """
        Delete a user (admin only, soft delete; cascades to their API keys and wallets).

        Raises:
            ValidationError: If ``user_id`` is not a positive integer.
        """
        self._require_positive_id(user_id, "user_id")

        return self._request_model(SuccessResponse, f"{self.BASE_ROUTE}/{user_id}", "DELETE")
