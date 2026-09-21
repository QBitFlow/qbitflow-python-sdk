"""Session request handlers for transactions."""

from typing import Optional

from qbitflow.dto.transaction import session as dto
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest


class SessionRequests(BaseRequest):
    """Internal handler for session retrieval (shared by payment and subscription handlers)."""

    BASE_ROUTE = "/transaction/session-checkout"

    def get(
        self,
        session_uuid: str,
        close_to_expire_error: Optional[bool] = False,
    ) -> dto.AnySession:
        """
        Retrieve a session checkout by UUID.

        Args:
            session_uuid: UUID of the session.
            close_to_expire_error: When True, the API returns an error if the session
                is close to expiry.

        Returns:
            The appropriate session type — OneTimePaymentSession, SubscriptionSession,
            or PaygSubscriptionSession — resolved from the response payload.
        """
        if not session_uuid:
            raise ValidationError("Session UUID cannot be empty")

        params = {}
        if close_to_expire_error is not None:
            params["closeToExpireError"] = str(close_to_expire_error).lower()

        res = self._make_request(
            f"{self.BASE_ROUTE}/{session_uuid}",
            "GET",
            params=params if params else None,
        )
        return dto._discriminate_session(res)
