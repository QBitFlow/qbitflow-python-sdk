"""Refund-related data models."""

import enum
from typing import Optional, Union

from pydantic import Field

from qbitflow.dto.base_model import GO_ZERO_TIME, Bool, Int, ResponseModel, Str, Timestamp

from .metadata import TxMetadata


class RefundStatus(str, enum.Enum):
    """Possible states of a refund entry."""

    PENDING = "pending"
    APPROVED = "approved"
    REFUSED = "refused"
    FAILED = "failed"


class RefundEntry(ResponseModel):
    """
    Represents a refund entry.

    Attributes:
        uuid: Unique identifier for the refund (``refund@``-prefixed).
        tx_id: Transaction ID associated with the refund (e.g. "pay@<uuid>").
        test: Whether this is a test refund.
        reason: Reason for the refund.
        status: Current status of the refund (a value this SDK does not know yet is kept
            as a plain string).
        created_at: Timestamp when the refund was created.
        merchant_message: Message from the merchant (``""`` until answered).
        responded_at: When the merchant responded, or ``None`` while pending.
        user_id: User that owns the refund (``0`` for organization-level refunds).
        organization_id: Organization that owns the refund.
        tx_hash: On-chain transaction hash of the refund (``""`` until processed).
        amount_min_units: Refund amount in smallest currency units (decimal string).
        metadata: On-chain transaction metadata for the refund, or ``None``.

    Example:
        >>> refunds = client.refunds.get_all()
        >>> for refund in refunds:
        ...     print(f"{refund.uuid}: {refund.status}")
    """

    uuid: Str = ""
    tx_id: Str = ""
    test: Bool = False
    reason: Str = ""
    status: Union[RefundStatus, str] = Field(default="", union_mode="left_to_right")
    created_at: Timestamp = GO_ZERO_TIME
    merchant_message: Str = ""
    responded_at: Optional[Timestamp] = None
    user_id: Int = 0
    organization_id: Int = 0
    tx_hash: Str = ""
    amount_min_units: Str = ""
    metadata: Optional[TxMetadata] = None
