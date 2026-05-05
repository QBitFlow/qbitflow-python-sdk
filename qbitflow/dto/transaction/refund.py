"""Refund-related data models."""

import enum
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class RefundStatus(str, enum.Enum):
    """Possible states of a refund entry."""
    PENDING = "pending"
    APPROVED = "approved"
    REFUSED = "refused"
    FAILED = "failed"


class RefundEntry(BaseModel):
    """
    Represents a refund entry.

    Attributes:
        uuid: Unique identifier for the refund.
        tx_id: Transaction ID associated with the refund (e.g. "pay@<uuid>").
        test: Whether this is a test refund.
        reason: Reason for the refund.
        status: Current status of the refund.
        created_at: Timestamp when the refund was created.
        merchant_message: Optional message from the merchant.
        responded_at: Timestamp when the refund was processed (null if pending).
        organization_id: ID of the organization that issued the refund.
        tx_hash: On-chain transaction hash of the refund (null if not yet processed).
        amount_min_units: Refund amount in smallest currency units (decimal string).
        metadata: Optional additional metadata.

    Example:
        >>> refunds = client.refunds.get_all()
        >>> for refund in refunds:
        ...     print(f"{refund.uuid}: {refund.status.value}")
    """

    uuid: str = Field(..., description="Refund UUID")
    tx_id: str = Field(..., description="Transaction ID (e.g. pay@<uuid>)")
    test: bool = Field(..., description="Test mode flag")
    reason: str = Field(..., description="Reason for the refund")
    status: RefundStatus = Field(..., description="Current refund status")
    created_at: datetime = Field(..., description="Creation timestamp")
    merchant_message: Optional[str] = Field(default=None, description="Optional merchant message")
    responded_at: Optional[datetime] = Field(default=None, description="Processing timestamp")
    organization_id: int = Field(..., description="Organization ID")
    tx_hash: Optional[str] = Field(default=None, description="On-chain transaction hash")
    amount_min_units: Optional[str] = Field(default=None, description="Refund amount in smallest units")  # noqa: E501
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
