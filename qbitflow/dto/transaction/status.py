
"""
Transaction status-related data models.

This module contains data models for tracking transaction statuses.
"""

import enum
from typing import Optional
from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class TransactionType(str, enum.Enum):
    """
    Enumeration of transaction types.
    
    Defines the different types of transactions that can occur in the system.
    
    Attributes:
        ONE_TIME_PAYMENT: A single one-time payment.
        CREATE_SUBSCRIPTION: Creating a new recurring subscription.
        CANCEL_SUBSCRIPTION: Cancelling an existing subscription.
        EXECUTE_SUBSCRIPTION_PAYMENT: Executing a scheduled subscription payment.
        CREATE_PAYG_SUBSCRIPTION: Creating a pay-as-you-go subscription.
        CANCEL_PAYG_SUBSCRIPTION: Cancelling a pay-as-you-go subscription.
        INCREASE_ALLOWANCE: Increasing the allowance for a subscription.
        UPDATE_MAX_AMOUNT: Updating the maximum amount for a subscription.
    """
    ONE_TIME_PAYMENT = "payment"
    CREATE_SUBSCRIPTION = "createSubscription"
    CANCEL_SUBSCRIPTION = "cancelSubscription"
    EXECUTE_SUBSCRIPTION_PAYMENT = "executeSubscription"
    CREATE_PAYG_SUBSCRIPTION = "createPAYGSubscription"
    CANCEL_PAYG_SUBSCRIPTION = "cancelPAYGSubscription"
    INCREASE_ALLOWANCE = "increaseAllowance"
    UPDATE_MAX_AMOUNT = "updateMaxAmount"


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
    
    type: TransactionType = Field(..., description="Transaction type")
    status: TransactionStatusValue = Field(..., description="Current status")
    tx_hash: Optional[str] = Field(default=None, description="Blockchain transaction hash")
    message: Optional[str] = Field(default=None, description="Status message or error description")


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
