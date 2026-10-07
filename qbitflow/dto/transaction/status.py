"""
Transaction status-related data models.

This module contains data models for tracking transaction statuses.
"""

import enum
from typing import Optional, Union

from pydantic import Field

from qbitflow.dto.base_model import ResponseModel, Str

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
        CREATE_PAYG_SUBSCRIPTION: Creating a pay-as-you-go subscription (a transaction record
            can still carry this type although PAYG session creation is disabled).
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
        PAY_AS_YOU_GO: A pay-as-you-go subscription (kept because records can carry it).
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


class TransactionStatus(ResponseModel):
    """
    Represents the status of a transaction.

    This model provides detailed information about the current state
    of a transaction.

    Attributes:
        status: The current status of the transaction. A status value this SDK does not
            know yet is kept as a plain string rather than rejected.
        tx_hash: Blockchain transaction hash (``""`` until the transaction is broadcast).
        message: Status message or error description (``""`` when there is none).
        settlement_details: Settlement details for finalized, successful transactions, or
            ``None``.

    Example:
        >>> status = client.transaction_status.get("pay@...", TransactionType.ONE_TIME_PAYMENT)
        >>> if status.status == TransactionStatusValue.COMPLETED:
        ...     print(f"Transaction completed! Hash: {status.tx_hash}")
        >>> elif status.status == TransactionStatusValue.FAILED:
        ...     print(f"Transaction failed: {status.message}")
    """

    status: Union[TransactionStatusValue, str] = Field(default="", union_mode="left_to_right")
    tx_hash: Str = ""
    message: Str = ""
    settlement_details: Optional[PaymentMetadata] = None
