"""Claim request handlers."""

from typing import List

from qbitflow.dto.claim import (
    ClaimFund,
    CreateClaimRequestResponse,
)
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest, SuccessResponse


class ClaimRequests(BaseRequest):
    """
    Handler for account claim and fund transfer operations.

    QBitFlow allows organizations to create users whose payments are initially
    held by the organization. When ready, the organization can create a claim
    request so the user can set up their own wallet and receive their funds.

    Example:
        >>> # Create a claim request for a user
        >>> result = client.claim.create_request(user_id=42)
        >>> print(f"Send this link to the user: {result.link}")
        >>>
        >>> # Check pending fund transfers
        >>> funds = client.claim.get_funds()
        >>> for fund in funds:
        ...     print(f"User {fund.user_id}: ${fund.total_amount_owed}")
    """

    BASE_ROUTE = "/user/claim"

    def get_request(self, user_id: int) -> CreateClaimRequestResponse:
        """
        Get the existing claim request link for a user.

        Returns the same claim link as :meth:`create_request` if one already
        exists for this user, without creating a new one.

        Args:
            user_id: ID of the user to look up.

        Returns:
            Response containing the existing claim link for the user.

        Example:
            >>> result = client.claim.get_request(user_id=42)
            >>> print(result.link)
        """
        if not user_id or user_id <= 0:
            raise ValidationError("User ID must be positive")

        res = self._make_request(
            f"{self.BASE_ROUTE}/request/{user_id}",
            "GET",
        )
        return CreateClaimRequestResponse(**res)

    def create_request(self, user_id: int) -> CreateClaimRequestResponse:
        """
        Create a claim request for a user (admin only).

        Generates a one-time link that the user can follow to set up their
        wallet and claim their owed funds.

        Args:
            user_id: ID of the user to invite.

        Returns:
            Response containing the claim link to send to the user.

        Example:
            >>> result = client.claim.create_request(user_id=42)
            >>> send_email(user_email, claim_link=result.link)
        """
        if not user_id or user_id <= 0:
            raise ValidationError("User ID must be positive")

        res = self._make_request(
            f"{self.BASE_ROUTE}/request",
            "POST",
            data={"userId": user_id},
        )
        return CreateClaimRequestResponse(**res)

    def get_funds(self) -> List[ClaimFund]:
        """
        Get all pending claim fund entries for the organization.

        Returns funds that users have earned and are waiting to be transferred
        after claiming their accounts.

        Returns:
            List of claim fund entries.

        Example:
            >>> funds = client.claim.get_funds()
            >>> for fund in funds:
            ...     if not fund.funded:
            ...         print(f"Pending transfer: ${fund.total_amount_owed} to user {fund.user_id}")
        """
        res = self._make_request(f"{self.BASE_ROUTE}/funds", "GET")
        return [ClaimFund(**item) for item in res]

    def trigger_test_claim_funds(self, user_id: int) -> SuccessResponse:
        """
        Manually trigger claim fund computation for a user (test mode only).

        In production, ledger entries are aggregated automatically every hour.
        Use this in test mode to trigger the process manually and verify the
        full claim flow without waiting.

        Args:
            user_id: ID of the user to compute claim funds for.

        Returns:
            Confirmation message.

        Example:
            >>> client.claim.trigger_test_claim_funds(user_id=42)
        """
        if not user_id or user_id <= 0:
            raise ValidationError("User ID must be positive")

        res = self._make_request(
            f"{self.BASE_ROUTE}/funds/test-trigger/{user_id}",
            "GET",
        )
        return SuccessResponse(**res)
