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
    "RefundStatus",
    "RefundInitiator",
    "NotRefundableReason",
    "TransactionKind",
    "FailureKind",
    "FailureCategory",
    "Chain",
    "TransactionType",
    "LedgerEntryType",
    "AccountingEventType",
    "NetworkFeesPayer",
    "InvitationStatus",
    "EventType",
    "EndpointDisabledReason",
    "DurationUnit",
    "Role",
    "MerchantNotReadyReason",
    "FeeLineType",
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
    """Where a bill stands (:attr:`TestBill.stage`)."""

    RUNNING = "running"  #: Being planned, charged or recorded.
    WAITING = "waiting"  #: Waiting for its next attempt, its due date, or a trial's grace end.
    PENDING = "pending"  #: Over the customer's maximum: waiting for their new one.
    DONE = "done"


class BillingOutcome(StrEnum):
    """How a bill ended (:attr:`TestBill.outcome`)."""

    PAID = "paid"
    NOT_DUE = "notDue"  #: Nothing to bill: paid already, cancelled, or gone.
    SKIPPED = "skipped"  #: Below the minimum amount: the period moved on without a charge.
    #: The subscription was cancelled (stopped, its trial over, its merchant closed, inactive
    #: on-chain, or its last attempt failed).
    CANCELLED = "cancelled"
    PAUSED = "paused"  #: Its customer paused the subscription: not charged.


class CheckoutSessionStatusValue(StrEnum):
    """A checkout session's (or a refund approval's) status."""

    CREATED = "created"  #: Waiting for the customer (``last_attempt``: their last one failed).
    WAITING_CONFIRMATION = "waitingConfirmation"  #: Sent: waiting for the network and its record.
    COMPLETED = "completed"  #: Confirmed and recorded. Final.
    #: Expired unpaid (at its ``expires_at``, or expired by its merchant). Final.
    EXPIRED = "expired"


class RefundStatus(StrEnum):
    """Where a refund stands. An approval and a rejection are final: the transaction never gets
    another refund."""

    PENDING = "pending"  #: A customer's request not answered yet.
    #: The refund transfer is confirmed (``refund.approved``); the merchant's own refund is
    #: recorded only then.
    APPROVED = "approved"
    REJECTED = "rejected"  #: Rejected by whoever decides it (``refund.rejected``).


class RefundInitiator(StrEnum):
    """Who started a refund."""

    CUSTOMER = "customer"  #: Requested by the customer; the merchant answers.
    MERCHANT = "merchant"  #: Sent by the merchant without a request.


class NotRefundableReason(StrEnum):
    """Why a transaction cannot be refunded now."""

    REFUND_EXISTS = "refundExists"
    HELD_FUNDS_RELEASED = "heldFundsReleased"


class TransactionKind(StrEnum):
    """What a row of the transactions feed is (:attr:`Transaction.type`). Not
    :class:`TransactionType`, which is a checkout's ``txType``."""

    PAYMENT = "payment"  #: A one-time payment (``pay@…``): ``payments.get``.
    BILL = "bill"  #: A subscription's bill (``sub-hist@…``): ``subscriptions.get_bill``.


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
    """A blockchain, by its native coin's symbol (:attr:`Currency.chain`; the testnet's in test
    mode)."""

    ETH = "ETH"  #: Ethereum.
    BASE = "BASE"  #: Base.
    SOL = "SOL"  #: Solana.


class TransactionType(StrEnum):
    """A checkout's kind (``checkout.expired``'s ``txType``)."""

    PAYMENT = "payment"  #: A one-time payment's checkout.
    CREATE_SUBSCRIPTION = "createSubscription"  #: A subscription's checkout.


class LedgerEntryType(StrEnum):
    """A held-funds line's kind. A held member sells no subscription, so no bill is ever a
    line."""

    #: A payment made to the member while the organization held their funds.
    PAYMENT = "payment"
    REFUND = "refund"  #: A refund the organization sent of one of them.


class AccountingEventType(StrEnum):
    """An accounting export row's kind."""

    PAYMENT = "payment"  #: A one-time payment (``pay@…``).
    BILL = "bill"  #: A subscription's bill (``sub-hist@…``).
    REFUND = "refund"  #: A refund the space sent (``refund@…``).
    #: The fee the organization earned on a member's payment or bill.
    ORGANIZATION_FEE = "organizationFee"
    #: The referrer's share earned on a referred organization's payment or bill.
    REFERRAL_FEE = "referralFee"


class NetworkFeesPayer(StrEnum):
    """Whose wallet paid an accounting event's network fees
    (:attr:`AccountingEvent.network_fees_paid_by`)."""

    PAYER = "payer"  #: A payment or a bill: the payer, on top of the amount.
    MERCHANT = "merchant"  #: A refund the space sent from its wallet.
    #: A refund of a payment the organization held for its member, sent from the organization's
    #: wallet.
    ORGANIZATION = "organization"


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
    REFUND_APPROVED = "refund.approved"  #: Was ``refund.completed``.
    REFUND_REJECTED = "refund.rejected"  #: Was ``refund.denied``.
    MEMBER_JOINED = "member.joined"
    MEMBER_REMOVED = "member.removed"
    HELD_FUNDS_RELEASED = "heldFunds.released"
    CHECKOUT_EXPIRED = "checkout.expired"
    #: Sent only by an endpoint's test (the dashboard); no endpoint subscribes to it.
    WEBHOOK_TEST = "webhook.test"


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
    """What a credential may do in a space (:attr:`Me.role`, :attr:`MeSpace.role`). An API key is
    at most ``admin``: ``admin`` (an organization key) or ``user`` (a member's key, or
    ``On-Behalf-Of``)."""

    ADMIN = "admin"  #: An organization key.
    USER = "user"  #: A member's key, or ``On-Behalf-Of`` a member.


class MerchantNotReadyReason(StrEnum):
    """``details["reason"]`` of a 409 ``merchant_not_ready``."""

    NO_WALLET = "noWallet"
    ORGANIZATION_NO_WALLET = "organizationNoWallet"
    NO_TOKEN_WALLET = "noTokenWallet"
    #: A subscription checkout of a member whose funds the organization holds: one-time payments
    #: only until ``members.trust``.
    FUNDS_HELD = "fundsHeld"


class FeeLineType(StrEnum):
    """Who added a line to a checkout's price (:class:`FeeLine`)."""

    CUSTOM = "custom"  #: The merchant's own line: a tax, shipping, a service fee.
    #: QBitFlow's processing fee, which the merchant has the customer pay (computed by QBitFlow).
    PROCESSING_FEE = "processingFee"
