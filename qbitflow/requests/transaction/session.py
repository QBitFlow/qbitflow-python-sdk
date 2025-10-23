"""Session request handlers for transactions."""

from qbitflow.requests.base_request import BaseRequest
from qbitflow.dto.transaction import session as dto
from qbitflow.exceptions import ValidationError


class SessionRequests(BaseRequest):
    """Handler for transaction session requests."""
    
    BASE_ROUTE = "/transaction/session-checkout"
    
    def create(self, data: dto.CreateSessionDto) -> dto.LinkResponse:
        """Create a new transaction session."""
        data.check()  # Validate before sending
        res = self._make_request(f"{self.BASE_ROUTE}/", "POST", data.model_dump())
        return dto.LinkResponse(**res)
    
    def get(self, session_uuid: str) -> dto.Session:
        """Get a transaction session by UUID."""
        if not session_uuid:
            raise ValidationError("Session UUID cannot be empty")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/{session_uuid}?closeToExpireError=false",
            "GET"
        )
        return dto.Session(**res)
