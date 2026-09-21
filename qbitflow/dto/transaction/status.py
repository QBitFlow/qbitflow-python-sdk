"""
Transaction status-related data models.

This module contains data models for tracking transaction statuses.
"""

import enum
from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import BaseModel

from .metadata import PaymentMetadata


class TransactionType(str, enum.Enum):
    """
    Enumeration of transaction types.

    Defines the different types of transactions that can occur in the system.

    Attributes:
        ONE_TIME_PAYMENT: A single one-time payment.
        TRANSFER: A native-currency transfer.
        TOKEN_TRANSFER: A token transfer.
        CREATE_SUBSCRIPTION: Creating a new recurring subscription.
        CANCEL_SUBSCRIPTION: Cancelling an existing subscription.
        EXECUTE_SUBSCRIPTION_PAYMENT: Executing a scheduled subscription payment.
        CREATE_PAYG_SUBSCRIPTION: Creating a pay-as-you-go subscription.
        CANCEL_PAYG_SUBSCRIPTION: Cancelling a pay-as-you-go subscription.
        INCREASE_ALLOWANCE: Increasing the allowance for a subscription.
        UPDATE_MAX_AMOUNT: Updating the maximum amount for a subscription.
        REFUND: A refund transaction.
        FAUCET: A test-network faucet funding transaction.
        CLAIM_FUNDS: A claim-funds transaction.
    """

    ONE_TIME_PAYMENT = "payment"
    TRANSFER = "transfer"
    TOKEN_TRANSFER = "tokenTransfer"
    CREATE_SUBSCRIPTION = "createSubscription"
    CANCEL_SUBSCRIPTION = "cancelSubscription"
    EXECUTE_SUBSCRIPTION_PAYMENT = "executeSubscription"
    CREATE_PAYG_SUBSCRIPTION = "createPAYGSubscription"
    CANCEL_PAYG_SUBSCRIPTION = "cancelPAYGSubscription"
    INCREASE_ALLOWANCE = "increaseAllowance"
    UPDATE_MAX_AMOUNT = "updateMaxAmount"
    REFUND = "refund"
    FAUCET = "faucet"
    CLAIM_FUNDS = "claimFunds"


class TransactionShortType(str, enum.Enum):
    """
    Enumeration of short transaction categories.

    This is the short category encoded in a transaction UUID prefix, used to
    identify the kind of transaction on a session checkout or record.

    Attributes:
        PAYMENT: A one-time payment.
        SUBSCRIPTION: A recurring subscription.
        PAY_AS_YOU_GO: A pay-as-you-go subscription.
        SUBSCRIPTION_HISTORY: A single subscription billing-cycle record.
        REFUND: A refund.
        TRANSFER: A transfer.
    """

    PAYMENT = "payment"
    SUBSCRIPTION = "subscription"
    PAY_AS_YOU_GO = "payAsYouGo"
    SUBSCRIPTION_HISTORY = "subscriptionHistory"
    REFUND = "refund"
    TRANSFER = "transfer"


class TransactionStatusValue(str, enum.Enum):
    """
    Enumeration of transaction status values.

    Defines the possible states a transaction can be in.

    Attributes:
        CREATED: Transaction has been created but not yet processed.
        WAITING_CONFIRMATION: Waiting for blockchain confirmation.
        PENDING: Transaction is pending processing.
        COMPLETED: Transaction has been successfully completed.
        FAILED: Transaction has failed.
        CANCELLED: Transaction has been cancelled.
        EXPIRED: Transaction has expired.
    """

    CREATED = "created"
    WAITING_CONFIRMATION = "waitingConfirmation"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TransactionStatus(BaseModel):
    """
    Represents the status of a transaction.

    This model provides detailed information about the current state
    of a transaction.

    Attributes:
        type: The type of transaction.
        status: The current status of the transaction.
        tx_hash: Optional blockchain transaction hash.
        message: Optional status message or error description.

    Example:
        >>> status = client.transaction_status.get("uuid", TransactionType.ONE_TIME_PAYMENT)
        >>> if status.status == TransactionStatusValue.COMPLETED:
        ...     print(f"Transaction completed! Hash: {status.tx_hash}")
        >>> elif status.status == TransactionStatusValue.FAILED:
        ...     print(f"Transaction failed: {status.message}")
    """

    status: TransactionStatusValue = Field(..., description="Current status")
    tx_hash: str = Field(..., description="Blockchain transaction hash")
    message: Optional[str] = Field(default=None, description="Status message or error description")
    settlement_details: Optional[PaymentMetadata] = Field(
        default=None,
        description="Settlement details for finalized, successful transactions",
    )


class StatusResponseError(BaseModel):
    """
    Represents an error response when checking transaction status.

    Attributes:
        error: Error type or code.
        status: HTTP status code.
        message: Human-readable error message.
    """

    error: str = Field(..., description="Error type or code")
    status: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Error message")


class StatusResponse(BaseModel):
    """
    Response containing transaction status information.

    Attributes:
        transaction_uuid: UUID of the transaction.
        status: Detailed transaction status information.

    Example:
        >>> response = client.subscriptions.execute_test_billing_cycle("sub-uuid")
        >>> print(f"Transaction: {response.transaction_uuid}")
        >>> print(f"Status: {response.status.status.value}")
    """

    transaction_uuid: str = Field(..., description="Transaction UUID")
    status: TransactionStatus = Field(..., description="Transaction status")
