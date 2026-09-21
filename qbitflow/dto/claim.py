"""Claim-related data models."""

from datetime import datetime

from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class Organization(BaseModel):
    """
    Represents a QBitFlow organization.

    Attributes:
        id: Organization ID.
        name: Organization name.
        fee_percentage: Default payment fee percentage.
        created_at: Creation timestamp.
    """

    id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    fee_percentage: float = Field(..., description="Default fee percentage")
    created_at: datetime = Field(..., description="Creation timestamp")


class ClaimRequest(BaseModel):
    """
    Represents a pending account claim request.

    A claim request is created by an organization admin to invite an unclaimed
    user to set up their wallet and receive their owed funds.

    Attributes:
        uuid: Unique identifier for the claim request.
        user_id: ID of the user being invited.
        created_at: Timestamp when the request was created.
    """

    uuid: str = Field(..., description="Claim request UUID")
    user_id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateClaimRequestResponse(BaseModel):
    """
    Response returned when creating a new claim request.

    Attributes:
        message: Confirmation message.
        link: The claim link to send to the user.
    """

    message: str = Field(..., description="Confirmation message")
    link: str = Field(..., description="Claim link for the user")


class ClaimFund(BaseModel):
    """
    Represents funds the organization owes to a user who has claimed their account.

    Once a user claims their account (sets up their wallet), the organization must
    sign and send the owed funds. This model tracks those pending transfers.

    Attributes:
        user_id: ID of the user owed funds.
        total_amount_owed: Total USD amount owed.
        funded: Whether the transfer has been signed/sent.
        test: Whether this is a test entry.
        created_at: Creation timestamp.

    Example:
        >>> funds = client.claim.get_funds()
        >>> for fund in funds:
        ...     print(f"User {fund.user_id}: ${fund.total_amount_owed} (funded={fund.funded})")
    """

    user_id: int = Field(..., description="User ID")
    total_amount_owed: float = Field(..., description="Total USD amount owed")
    funded: bool = Field(..., description="Whether the transfer has been executed")
    test: bool = Field(..., description="Test mode flag")
    created_at: datetime = Field(..., description="Creation timestamp")
