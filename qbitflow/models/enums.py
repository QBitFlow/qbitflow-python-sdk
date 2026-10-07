"""
The API's enumerations.

Every enum is open: a value this SDK does not know yet is kept as the raw ``str``, never
rejected. The members are strings (``StrEnum``), so compare a field with ``==`` whatever it holds:
``subscription.status == SubscriptionStatus.ACTIVE``.
"""

from .._compat import StrEnum

__all__ = [
    "SubscriptionStatus",
    "ActionRequired",
    "CancellationReason",
    "BillingFailureReason",
    "BillingStage",
    "BillingOutcome",
    "CheckoutSessionStatusValue",
    "AttemptStatus",
    "RefundStatus",
    "RefundInitiator",
    "NotRefundableReason",
    "CombinedPaymentSource",
    "FailureKind",
    "FailureCategory",
    "Chain",
    "TransactionType",
    "TransferType",
    "LedgerEntryType",
    "AccountingEventType",
    "InvitationStatus",
    "EventType",
    "WebhookPayloadVersion",
    "EndpointDisabledReason",
    "DurationUnit",
    "Role",
    "Credential",
    "MerchantNotReadyReason",
]


class SubscriptionStatus(StrEnum):
    """A subscription's lifecycle status."""

    TRIAL = "trial"  #: In its free trial.
    TRIAL_EXPIRED = "trialExpired"  #: The trial ended without its customer confirming it.
    ACTIVE = "active"  #: Billed normally.
    PAST_DUE = "pastDue"  #: A bill failed: retried (dunning) until paid or cancelled.
    PAUSED = "paused"  #: Paused by its customer: not billed until resumed.
    STOPPED = "stopped"  #: Stopped: cancelled at the end of the current period.
    CANCELLED = "cancelled"  #: Cancelled. Final.


class ActionRequired(StrEnum):
    """What a subscription's customer must do (``None`` = nothing)."""

    TOP_UP_ALLOWANCE = "topUpAllowance"  #: The allowance is too low for the next bill.
    RAISE_MAXIMUM = "raiseMaximum"  #: The bill is above the customer's maximum per period.
    CONFIRM_TRIAL = "confirmTrial"  #: The trial must be confirmed to be billed.


class CancellationReason(StrEnum):
    """Why a subscription stopped or was cancelled."""

    CUSTOMER = "customer"
    MERCHANT = "merchant"
    BILLING_FAILED = "billingFailed"
    TRIAL_NOT_CONVERTED = "trialNotConverted"
    MERCHANT_CLOSED = "merchantClosed"
    INACTIVE_ON_CHAIN = "inactiveOnChain"


class BillingFailureReason(StrEnum):
    """Why a bill failed (``subscription.billingFailed``)."""

    INSUFFICIENT_BALANCE = "insufficientBalance"
    ALLOWANCE_EXHAUSTED = "allowanceExhausted"
    APPROVAL_REVOKED = "approvalRevoked"
    MAX_AMOUNT_EXCEEDED = "maxAmountExceeded"
    OTHER = "other"


class BillingStage(StrEnum):
    """Where a billing run is (:attr:`BillingState.stage`)."""

    RUNNING = "running"  #: Being planned, charged or recorded.
    WAITING = "waiting"  #: Waiting for its next attempt, its due date, or a trial's grace end.
    PENDING = "pending"  #: Over the customer's maximum: waiting for their new one.
    DONE = "done"


class BillingOutcome(StrEnum):
    """How a finished billing run ended (:attr:`BillingState.outcome`)."""

    PAID = "paid"
    NOT_DUE = "notDue"  #: Nothing to bill: paid already, cancelled, or gone.
    SKIPPED = "skipped"  #: Below the minimum amount: the period moved on without a charge.
    CANCELLED = "cancelled"  #: The subscription was cancelled.
    PAUSED = "paused"  #: Its customer paused the subscription: not charged.


class CheckoutSessionStatusValue(StrEnum):
    """A checkout session's (or a refund approval's) status."""

    CREATED = "created"  #: Waiting for the customer (``last_attempt``: their last one failed).
    WAITING_CONFIRMATION = "waitingConfirmation"  #: Sent: waiting for the network and its record.
    COMPLETED = "completed"  #: Confirmed and recorded. Final.
    EXPIRED = "expired"  #: Expired unpaid. Final.


class AttemptStatus(StrEnum):
    """A failed attempt's status."""

    FAILED = "failed"  #: Not sent, not confirmed, or failed on the network: nothing was paid.


class RefundStatus(StrEnum):
    """A refund's status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RefundInitiator(StrEnum):
    """Who started a refund."""

    CUSTOMER = "customer"  #: Requested by the customer; the merchant answers.
    MERCHANT = "merchant"  #: Sent by the merchant without a request.


class NotRefundableReason(StrEnum):
    """Why a transaction cannot be refunded now."""

    REFUND_EXISTS = "refundExists"
    HELD_FUNDS_RELEASED = "heldFundsReleased"


class CombinedPaymentSource(StrEnum):
    """What a combined feed row is."""

    PAYMENT = "payment"  #: A one-time payment (``pay@…``).
    SUBSCRIPTION_HISTORY = "subscriptionHistory"  #: A subscription's bill (``sub-hist@…``).


class FailureKind(StrEnum):
    """What a failed attempt was paying."""

    PAYMENT = "payment"  #: A one-time payment's attempt (``pay@…``).
    SUBSCRIPTION_CHECKOUT = "subscriptionCheckout"  #: A subscription checkout's (``sub@…``).
    BILL = "bill"  #: A subscription's bill (``sub-hist@…``).


class FailureCategory(StrEnum):
    """What a failure means, from its code."""

    INSUFFICIENT_BALANCE = "insufficientBalance"
    ALLOWANCE_EXHAUSTED = "allowanceExhausted"
    APPROVAL_REVOKED = "approvalRevoked"
    MAX_AMOUNT_EXCEEDED = "maxAmountExceeded"
    REVERTED = "reverted"
    NOT_CONFIRMED = "notConfirmed"
    SIGNATURE_REJECTED = "signatureRejected"
    OTHER = "other"


class Chain(StrEnum):
    """A blockchain (the testnet's in test mode)."""

    ETH = "ETH"  #: Ethereum.
    BASE = "BASE"  #: Base.
    SOL = "SOL"  #: Solana.


class TransactionType(StrEnum):
    """A transaction's kind (``checkout.expired``'s ``txType``: payment or createSubscription)."""

    PAYMENT = "payment"
    TRANSFER = "transfer"
    TOKEN_TRANSFER = "tokenTransfer"
    CREATE_SUBSCRIPTION = "createSubscription"
    CANCEL_SUBSCRIPTION = "cancelSubscription"
    FORCE_CANCEL_SUBSCRIPTION = "forceCancelSubscription"
    EXECUTE_SUBSCRIPTION = "executeSubscription"
    CREATE_PAYG_SUBSCRIPTION = "createPaygSubscription"
    CANCEL_PAYG_SUBSCRIPTION = "cancelPaygSubscription"
    INCREASE_ALLOWANCE = "increaseAllowance"
    UPDATE_MAX_AMOUNT = "updateMaxAmount"
    REFUND = "refund"
    FAUCET = "faucet"
    CLAIM_FUNDS = "claimFunds"
    RELEASE_HELD_FUNDS = "releaseHeldFunds"


class TransferType(StrEnum):
    """A transfer's kind (``heldFunds.released``)."""

    ACCOUNT_CLAIM = "accountClaim"  #: v1: funds held for a user, paid when they claimed.
    HELD_FUNDS_RELEASE = "heldFundsRelease"  #: Funds an organization held for a member, paid out.
    INTERNAL = "internal"
    EXTERNAL = "external"


class LedgerEntryType(StrEnum):
    """A held-funds line's kind."""

    PAYMENT = "payment"
    SUBSCRIPTION_HISTORY = "subscriptionHistory"
    REFUND = "refund"


class AccountingEventType(StrEnum):
    """An accounting export row's kind."""

    PAYMENT = "payment"
    SUBSCRIPTION_HISTORY = "subscriptionHistory"
    REFUND = "refund"
    ORGANIZATION_FEE = "organizationFee"
    REFERRAL_FEE = "referralFee"


class InvitationStatus(StrEnum):
    """An invitation's status (computed when read)."""

    PENDING = "pending"  #: Sent, waiting for the person.
    ACCEPTED = "accepted"  #: The person joined.
    REVOKED = "revoked"  #: Revoked by the organization (or replaced by a newer one).
    EXPIRED = "expired"  #: Not accepted in time.


class EventType(StrEnum):
    """A webhook event's type."""

    PAYMENT_COMPLETED = "payment.completed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_BILLED = "subscription.billed"
    SUBSCRIPTION_STATUS_CHANGED = "subscription.statusChanged"
    SUBSCRIPTION_ACTION_REQUIRED_CHANGED = "subscription.actionRequiredChanged"
    SUBSCRIPTION_BILLING_FAILED = "subscription.billingFailed"
    SUBSCRIPTION_UPCOMING_BILL = "subscription.upcomingBill"
    REFUND_REQUESTED = "refund.requested"
    REFUND_COMPLETED = "refund.completed"
    REFUND_DENIED = "refund.denied"
    MEMBER_JOINED = "member.joined"
    MEMBER_REMOVED = "member.removed"
    HELD_FUNDS_RELEASED = "heldFunds.released"
    CHECKOUT_EXPIRED = "checkout.expired"
    WEBHOOK_TEST = "webhook.test"


class WebhookPayloadVersion(StrEnum):
    """A webhook endpoint's (and an event's) payload version."""

    V1 = "v1"  #: v1's bodies (endpoints migrated from v1; not parsed by this SDK).
    V2 = "v2"  #: The event envelope.


class EndpointDisabledReason(StrEnum):
    """Why a webhook endpoint is disabled."""

    FAILING = "failing"  #: Every delivery failing for too long.
    OWNER = "owner"  #: Disabled by its owner.
    CLOSED = "closed"  #: Its member removed, or its organization closed.


class DurationUnit(StrEnum):
    """A :class:`Duration`'s unit (months = 30 days, years = 365 days)."""

    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class Role(StrEnum):
    """What a credential (or an invitation) may do in a space. An API key is ``admin`` (an
    organization key) or ``user`` (a member's key, or ``On-Behalf-Of``)."""

    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    HANDLE = "handle"


class Credential(StrEnum):
    """What authenticated a request (:attr:`Me.credential`)."""

    API_KEY = "apiKey"  #: An API key (``X-API-Key``).
    SESSION = "session"  #: A signed-in person's access token.


class MerchantNotReadyReason(StrEnum):
    """``details["reason"]`` of a 409 ``merchant_not_ready``."""

    NO_WALLET = "noWallet"
    ORGANIZATION_NO_WALLET = "organizationNoWallet"
    NO_TOKEN_WALLET = "noTokenWallet"
