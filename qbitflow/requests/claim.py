"""Claim request handlers."""

import warnings
from typing import List

from qbitflow.dto.claim import ClaimFund, CreateClaimRequestResponse
from qbitflow.requests.base_request import BaseRequest, SuccessResponse


class ClaimRequests(BaseRequest):
    """
    Handler for account claim and fund transfer operations (``client.claims``).

    QBitFlow allows organizations to create users whose payments are initially
    held by the organization. When ready, the organization can create a claim
    request so the user can set up their own wallet and receive their funds.

    Example:
        >>> # Create a claim request for a user
        >>> result = client.claims.create_request(user_id=42)
        >>> print(f"Send this link to the user: {result.link}")
        >>>
        >>> # Check pending fund transfers
        >>> funds = client.claims.get_funds()
        >>> for fund in funds:
        ...     print(f"User {fund.user_id}: ${fund.total_amount_owed}")
    """

    BASE_ROUTE = "/user/claim"

    def get_request_by_user(self, user_id: int) -> CreateClaimRequestResponse:
        """
        Get the existing claim request link for a user (admin only).

        Returns the same claim link as :meth:`create_request` if an active one exists for
        this user, without creating a new one.

        Args:
            user_id: ID of the user to look up.

        Returns:
            Response containing the existing claim link for the user.

        Raises:
            ValidationError: If ``user_id`` is not a positive integer.
            NotFoundException: If the user has no active claim request (or is not in your
                organization).

        Example:
            >>> result = client.claims.get_request_by_user(user_id=42)
            >>> print(result.link)
        """
        self._require_positive_id(user_id, "user_id")

        return self._request_model(
            CreateClaimRequestResponse, f"{self.BASE_ROUTE}/request/{user_id}"
        )

    def get_request(self, user_id: int) -> CreateClaimRequestResponse:
        """
        Deprecated alias of :meth:`get_request_by_user`.

        .. deprecated:: 2.5.0
            Use ``client.claims.get_request_by_user(user_id)``.
        """
        warnings.warn(
            "ClaimRequests.get_request() is deprecated; use get_request_by_user() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_request_by_user(user_id)

    def create_request(self, user_id: int) -> CreateClaimRequestResponse:
        """
        Create a claim request for a user (admin only).

        Generates a one-time link that the user can follow to set up their
        wallet and claim their owed funds. A user may have only one active request;
        creating a second one raises :class:`~qbitflow.exceptions.ValidationError` (400) —
        use :meth:`get_request_by_user` to fetch the existing link.

        Args:
            user_id: ID of the user to invite.

        Returns:
            Response containing the claim link to send to the user.

        Raises:
            ValidationError: If ``user_id`` is not a positive integer, or the user already
                has an active claim request.

        Example:
            >>> result = client.claims.create_request(user_id=42)
            >>> send_email(user_email, claim_link=result.link)
        """
        self._require_positive_id(user_id, "user_id")

        return self._request_model(
            CreateClaimRequestResponse,
            f"{self.BASE_ROUTE}/request",
            "POST",
            data={"userId": user_id},
        )

    def get_funds(self) -> List[ClaimFund]:
        """
        Get the organization's active claim fund entries.

        Returns the amounts the organization owes its provisioned users.

        Returns:
            List of claim fund entries (empty when there are none).

        Example:
            >>> funds = client.claims.get_funds()
            >>> for fund in funds:
            ...     if not fund.funded:
            ...         print(f"Pending transfer: ${fund.total_amount_owed} to user {fund.user_id}")
        """
        return self._request_list(ClaimFund, f"{self.BASE_ROUTE}/funds")

    def trigger_test_claim_funds(self, user_id: int) -> SuccessResponse:
        """
        Manually trigger claim fund computation for a user (test mode only, admin only).

        In production, ledger entries are aggregated automatically every hour.
        Use this in test mode to trigger the process manually and verify the
        full claim flow without waiting. In live mode the API answers 400. The request is
        an action, so it is never retried automatically.

        Args:
            user_id: ID of the user to compute claim funds for.

        Returns:
            Confirmation message.

        Raises:
            ValidationError: If ``user_id`` is not a positive integer, or the key is not
                a test-mode key.

        Example:
            >>> client.claims.trigger_test_claim_funds(user_id=42)
        """
        self._require_positive_id(user_id, "user_id")

        # An action, not a read: never retried even though the route is a GET.
        return self._request_model(
            SuccessResponse,
            f"{self.BASE_ROUTE}/funds/test-trigger/{user_id}",
            retriable=False,
        )
