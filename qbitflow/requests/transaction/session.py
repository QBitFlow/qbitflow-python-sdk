"""Session request handlers for transactions."""

from typing import Any, Dict, Optional, Type, TypeVar

import pydantic

from qbitflow.dto.transaction import session as dto
from qbitflow.exceptions import ServerError
from qbitflow.requests.base_request import BaseRequest

DtoT = TypeVar("DtoT", bound=dto.CreatePaymentSessionDto)


def build_session_dto(model: Type[DtoT], **kwargs: Any) -> DtoT:
    """
    Construct a session DTO from keyword arguments.

    A rejected value — including "no product selected" — raises the SDK's
    :class:`~qbitflow.exceptions.ValidationError` (with ``fields``), so one
    ``except ValidationError`` covers a value rejected locally and the same value rejected by
    the API.
    """
    return model(**kwargs)


class SessionRequests(BaseRequest):
    """Internal handler for session retrieval (shared by payment and subscription handlers)."""

    BASE_ROUTE = "/transaction/session-checkout"

    def get(
        self,
        session_uuid: str,
        close_to_expire_error: Optional[bool] = None,
    ) -> dto.AnySession:
        """
        Retrieve a session checkout by UUID.

        Args:
            session_uuid: UUID of the session (``pay@…`` or ``sub@…``).
            close_to_expire_error: When True, the API returns an error if the session
                is close to expiry. ``None`` leaves the API default (true) in place.

        Returns:
            The appropriate session type — OneTimePaymentSession or SubscriptionSession —
            resolved from the payload's ``txType``.

        Raises:
            ValidationError: If ``session_uuid`` is empty.
            NotFoundException: If the session is unknown or expired.
            ServerError: If the payload does not match the session shape.
        """
        self._require_identifier(session_uuid, "session_uuid")

        params: Dict[str, Any] = {}
        if close_to_expire_error is not None:
            params["closeToExpireError"] = str(bool(close_to_expire_error)).lower()

        response = self._send(
            f"{self.BASE_ROUTE}/{self._escape_path(session_uuid)}",
            "GET",
            None,
            params or None,
            retriable=None,
        )
        res = self._decode_json(response)
        if not isinstance(res, dict):
            raise ServerError(
                "API response did not match the expected session shape: a JSON object was "
                f"expected, got {type(res).__name__}",
                status_code=response.status_code,
                response={"raw": res},
            )
        try:
            return dto._discriminate_session(res)
        except pydantic.ValidationError as exc:
            raise ServerError(
                "API response did not match the expected session shape: "
                f"{exc.error_count()} field(s) could not be decoded",
                status_code=response.status_code,
                response={"raw": res},
            ) from exc
