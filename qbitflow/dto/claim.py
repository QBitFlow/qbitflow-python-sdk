"""Claim-related data models."""

from qbitflow.dto.base_model import GO_ZERO_TIME, Bool, Float, Int, ResponseModel, Str, Timestamp


class Organization(ResponseModel):
    """
    Represents a QBitFlow organization.

    Attributes:
        id: Organization ID.
        name: Organization name.
        fee_percentage: Default payment fee percentage.
        created_at: Creation timestamp.
    """

    id: Int = 0
    name: Str = ""
    fee_percentage: Float = 0.0
    created_at: Timestamp = GO_ZERO_TIME


class CreateClaimRequestResponse(ResponseModel):
    """
    Response returned when creating (or fetching) a claim request.

    Attributes:
        message: Confirmation message.
        link: The claim link to send to the user.
    """

    message: Str = ""
    link: Str = ""


class ClaimFund(ResponseModel):
    """
    Funds the organization owes to one of its provisioned users.

    The organization temporarily holds what a provisioned user earns; a claim fund entry
    tracks the amount to transfer once the user has claimed their account and connected a
    wallet.

    Attributes:
        user_id: ID of the user owed funds.
        total_amount_owed: Total USD amount owed.
        funded: Whether the transfer has been signed/sent.
        test: Whether this is a test entry.
        created_at: Creation timestamp.

    Example:
        >>> funds = client.claims.get_funds()
        >>> for fund in funds:
        ...     print(f"User {fund.user_id}: ${fund.total_amount_owed} (funded={fund.funded})")
    """

    user_id: Int = 0
    total_amount_owed: Float = 0.0
    funded: Bool = False
    test: Bool = False
    created_at: Timestamp = GO_ZERO_TIME
