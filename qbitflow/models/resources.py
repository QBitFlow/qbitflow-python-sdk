"""Refunds, customers, products, the key's identity, members and invitations, wallets, the
accounting export, webhook endpoints and deliveries."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Float, Int, Model, Str, Time, UInt
from ._fields import (
    AccountingEventTypeT,
    ChainT,
    CheckoutSessionStatusValueT,
    CredentialT,
    EndpointDisabledReasonT,
    EventTypeT,
    InvitationStatusT,
    LedgerEntryTypeT,
    RefundInitiatorT,
    RefundStatusT,
    RoleT,
    WebhookPayloadVersionT,
)
from .common import Attempt, Currency, CustomerSummary, PaymentMetadata, TxMetadata
from .subscriptions import SubscriptionTerms

__all__ = [
    "Refund",
    "RefundApproval",
    "Customer",
    "Product",
    "Me",
    "MeSpace",
    "MeMember",
    "Member",
    "HeldFunds",
    "LedgerEntry",
    "MemberHeldFundsSummary",
    "Invitation",
    "InvitationCreated",
    "Wallet",
    "TokenWallet",
    "Balance",
    "AccountingEvent",
    "WebhookEndpoint",
    "WebhookEndpointCreated",
    "EndpointDelivery",
    "DeliveryAttempt",
]


# ── Refunds ──────────────────────────────────────────────────────────────────


class RefundApproval(Model):
    """A refund's approval in progress."""

    #: ``waitingConfirmation`` (sent, being confirmed) or ``created`` (its last attempt failed).
    status: CheckoutSessionStatusValueT = ""
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: Why the last attempt failed.
    last_attempt: Optional[Attempt] = Field(default=None, alias="lastAttempt")


class Refund(Model):
    """A refund of a payment or a bill."""

    #: The refund's id (``refund@…``).
    uuid: Str = ""
    #: The refunded transaction: a payment (``pay@…``) or a bill (``sub-hist@…``).
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: The customer's reason, or the merchant's when it started the refund.
    reason: Str = ""
    #: pending, approved or rejected.
    status: RefundStatusT = ""
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The merchant's message to the customer (``""`` until set).
    merchant_message: Str = Field(default="", alias="merchantMessage")
    #: When the merchant answered; ``None`` while pending.
    responded_at: Optional[Time] = Field(default=None, alias="respondedAt")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: The refund transfer's hash (``""`` until sent).
    tx_hash: Str = Field(default="", alias="txHash")
    #: ``customer`` (a request the merchant answers) or ``merchant``.
    initiated_by: RefundInitiatorT = Field(default="", alias="initiatedBy")
    #: True when the refunded transaction's funds are held by the organization.
    held: Bool = False
    #: What the customer paid for the refunded transaction, in min units.
    paid_min_units: Str = Field(default="", alias="paidMinUnits")
    paid_usd: Float = Field(default=0.0, alias="paidUsd")
    #: The share of what the customer paid it sends back, in percent.
    refund_percent: Float = Field(default=0.0, alias="refundPercent")
    #: What it sends back, in min units (a decimal string).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    amount_usd: Float = Field(default=0.0, alias="amountUsd")
    currency_id: UInt = Field(default=0, alias="currencyId")
    #: The refund transfer's network fees and block, once approved; ``None`` before.
    metadata: Optional[TxMetadata] = None
    chain: Optional[ChainT] = None
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: The approval being confirmed, or its failed attempt (API reads only).
    approval: Optional[RefundApproval] = None
    #: What the refunded transaction paid for (API reads only).
    product_name: Optional[Str] = Field(default=None, alias="productName")
    #: Names the refunded transaction's customer (API reads only).
    customer: Optional[CustomerSummary] = None


# ── Customers and products ───────────────────────────────────────────────────


class Customer(Model):
    """A customer of a space."""

    uuid: Str = ""
    #: The first name.
    name: Str = ""
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    #: The email address, lowercase. Several customers of a space may share one.
    email: Str = ""
    #: True for a customer the merchant created, False for one created at checkout.
    verified: Bool = False
    phone_number: Optional[Str] = Field(default=None, alias="phoneNumber")
    address: Optional[Str] = None
    reference: Optional[Str] = None
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


class Product(Model):
    """A product: a one-time product, or a subscription product with its terms."""

    uuid: Str = ""
    name: Str = ""
    #: Its description (``""`` when none).
    description: Str = ""
    #: Its price in USD (per period for a subscription product).
    price: Float = 0.0
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: False for a hidden product (left out of ``products.list`` unless ``include_hidden``).
    is_active: Bool = Field(default=False, alias="isActive")
    #: The merchant's reference (defaults to the uuid).
    reference: Str = ""
    #: A subscription product's terms; ``None`` for a one-time product.
    subscription: Optional[SubscriptionTerms] = None
    payment_link: Optional[Str] = Field(default=None, alias="paymentLink")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


# ── The key's identity, members, invitations ─────────────────────────────────


class MeMember(Model):
    """Names the member whose space a request acts in."""

    user_uuid: Str = Field(default="", alias="userUuid")
    name: Str = ""
    last_name: Str = Field(default="", alias="lastName")
    email: Str = ""


class MeSpace(Model):
    """The space a request acts in."""

    uuid: Str = ""
    organization_uuid: Str = Field(default="", alias="organizationUuid")
    organization_name: Str = Field(default="", alias="organizationName")
    #: The member whose space it is; ``None`` for the organization's own space.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: Names that member; ``None`` for the organization's own space.
    member: Optional[MeMember] = None
    #: The space's mode: True for test, False for live.
    test: Bool = False


class Me(Model):
    """What the API key is (``client.me()``)."""

    #: ``apiKey`` for an API key.
    credential: CredentialT = ""
    api_key_uuid: Optional[Str] = Field(default=None, alias="apiKeyUuid")
    #: Who signed in, for a session (``None`` for an API key).
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: ``admin`` (an organization key) or ``user`` (a member's key, or ``On-Behalf-Of``).
    role: Optional[RoleT] = None
    #: The member an organization key acts as (``On-Behalf-Of``); ``None`` otherwise.
    on_behalf_of: Optional[Str] = Field(default=None, alias="onBehalfOf")
    #: The space the request reads and writes in.
    space: Optional[MeSpace] = None


class Member(Model):
    """A member of the organization (a seller of a marketplace), in one mode."""

    #: The member's id: what ``on_behalf_of`` takes.
    user_uuid: Str = Field(default="", alias="userUuid")
    name: Str = ""
    last_name: Str = Field(default="", alias="lastName")
    email: Str = ""
    test: Bool = False
    #: The organization's fee on the member's payments, in percent.
    organization_fee_percent: Float = Field(default=0.0, alias="organizationFeePercent")
    #: When the organization started paying them directly; ``None`` while it holds their funds.
    trusted_at: Optional[Time] = Field(default=None, alias="trustedAt")
    joined_at: Time = Field(default=ZERO_TIME, alias="joinedAt")
    #: The currencies their wallets accept.
    accepted_currency_ids: List[UInt] = Field(default_factory=list, alias="acceptedCurrencyIds")
    #: Their personal space in this mode.
    space_uuid: Str = Field(default="", alias="spaceUuid")


class LedgerEntry(Model):
    """One held-funds line."""

    #: The line's transaction: ``pay@…``, ``sub-hist@…`` or ``refund@…``.
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: payment, subscriptionHistory or refund.
    type: LedgerEntryTypeT = ""
    description: Str = ""
    #: On a refund line, the payment or bill it refunds.
    refunded_tx_uuid: Optional[Str] = Field(default=None, alias="refundedTxUuid")
    #: What the customer paid (a payment or bill), or what a refund sent back, in USD.
    amount: Float = 0.0
    #: A payment's or bill's fees and split; ``None`` on refund lines.
    metadata: Optional[PaymentMetadata] = None
    currency_id: UInt = Field(default=0, alias="currencyId")
    #: What the line counts for in a release, in min units (negative on refunds).
    owed_min_units: Str = Field(default="", alias="owedMinUnits")
    owed_usd: Float = Field(default=0.0, alias="owedUsd")
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")


class HeldFunds(Model):
    """What the organization holds for a member (trust layer)."""

    #: The lines not settled yet, oldest first.
    ledgers: List[LedgerEntry] = Field(default_factory=list)
    #: What the organization owes the member, in USD (may be 0 or less).
    total_amount: Float = Field(default=0.0, alias="totalAmount")


class MemberHeldFundsSummary(Model):
    """One member's held funds, in the organization's overview."""

    user_uuid: Str = Field(default="", alias="userUuid")
    total_amount: Float = Field(default=0.0, alias="totalAmount")
    #: Their lines not settled.
    count: Int = 0
    #: Their oldest line not settled.
    oldest_at: Time = Field(default=ZERO_TIME, alias="oldestAt")


class Invitation(Model):
    """An invitation to join the organization."""

    uuid: Str = ""
    #: A member invitation's mode; ``None`` for a team invitation.
    test: Optional[Bool] = None
    email: Str = ""
    #: ``admin`` (the team) or ``user`` (a member).
    role: RoleT = ""
    #: True when the organization holds the member's payments until it trusts them.
    trust_layer: Optional[Bool] = Field(default=None, alias="trustLayer")
    organization_fee_percent: Float = Field(default=0.0, alias="organizationFeePercent")
    #: Where the person goes once they accepted (with ``?invitationUuid=<uuid>``).
    redirect_url: Optional[Str] = Field(default=None, alias="redirectUrl")
    expires_at: Time = Field(default=ZERO_TIME, alias="expiresAt")
    accepted_by_user_uuid: Optional[Str] = Field(default=None, alias="acceptedByUserUuid")
    accepted_at: Optional[Time] = Field(default=None, alias="acceptedAt")
    revoked_at: Optional[Time] = Field(default=None, alias="revokedAt")
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: pending, accepted, revoked or expired.
    status: InvitationStatusT = ""


class InvitationCreated(Model):
    """``invitations.create``'s answer: the invitation and the link to accept it (also emailed)."""

    invitation: Invitation = Field(default_factory=Invitation)
    link: Str = ""


# ── Wallets ──────────────────────────────────────────────────────────────────


class Balance(Model):
    """A token wallet's balance."""

    #: The token (e.g. ``SOL:USDC``).
    currency: Str = ""
    #: The balance in the token (a decimal string).
    balance: Str = ""
    balance_usd: Float = Field(default=0.0, alias="balanceUsd")


class TokenWallet(Model):
    """A token enabled on a wallet."""

    uuid: Str = ""
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    token_id: UInt = Field(default=0, alias="tokenId")
    token: Currency = Field(default_factory=Currency)
    wallet_uuid: Str = Field(default="", alias="walletUuid")
    #: Its balance; set only by ``wallets.list(with_balances=True)``.
    balance: Optional[Balance] = None


class Wallet(Model):
    """A wallet of a space on one chain, with its token wallets."""

    uuid: Str = ""
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The wallet's address.
    public_key: Str = Field(default="", alias="publicKey")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    token_wallets: List[TokenWallet] = Field(default_factory=list, alias="tokenWallets")
    #: The chain's native coin.
    currency_id: UInt = Field(default=0, alias="currencyId")
    currency: Currency = Field(default_factory=Currency)


# ── Accounting ───────────────────────────────────────────────────────────────


class AccountingEvent(Model):
    """One row of the accounting export: a payment, a bill, a refund, or a fee."""

    #: The event's transaction (prefixed); ``None`` on referralFee rows.
    payment_uuid: Optional[Str] = Field(default=None, alias="paymentUuid")
    payment_reference: Optional[Str] = Field(default=None, alias="paymentReference")
    #: payment, subscriptionHistory, refund, organizationFee or referralFee.
    type: AccountingEventTypeT = ""
    #: The transaction's time (the API may send a local offset).
    tx_time_utc: Time = Field(default=ZERO_TIME, alias="txTimeUtc")
    receipt_url: Optional[Str] = Field(default=None, alias="receiptUrl")
    #: For a refund, the refunded payment.
    related_payment_uuid: Optional[Str] = Field(default=None, alias="relatedPaymentUuid")
    related_payment_reference: Optional[Str] = Field(default=None, alias="relatedPaymentReference")
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    product_reference: Optional[Str] = Field(default=None, alias="productReference")
    product_name: Optional[Str] = Field(default=None, alias="productName")
    product_description: Optional[Str] = Field(default=None, alias="productDescription")
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    chain: ChainT = ""
    block_number_or_slot: Str = Field(default="", alias="blockNumberOrSlot")
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    from_address: Optional[Str] = Field(default=None, alias="fromAddress")
    to_address: Optional[Str] = Field(default=None, alias="toAddress")
    token_symbol: Str = Field(default="", alias="tokenSymbol")
    currency_decimals: UInt = Field(default=0, alias="currencyDecimals")
    token_contract_or_mint: Str = Field(default="", alias="tokenContractOrMint")
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: The gross amount in min units (a decimal string).
    gross_amount: Optional[Str] = Field(default=None, alias="grossAmount")
    gross_amount_usd: Optional[Float] = Field(default=None, alias="grossAmountUsd")
    #: QBitFlow's fee rate, in percent (1.5 = 1.5 %).
    platform_fee_percent: Optional[Float] = Field(default=None, alias="platformFeePercent")
    platform_fee_usd: Optional[Float] = Field(default=None, alias="platformFeeUsd")
    platform_fee: Optional[Str] = Field(default=None, alias="platformFee")
    organization_fee_percent: Optional[Float] = Field(default=None, alias="organizationFeePercent")
    organization_fee_usd: Optional[Float] = Field(default=None, alias="organizationFeeUsd")
    organization_fee: Optional[Str] = Field(default=None, alias="organizationFee")
    referral_fee_percent: Float = Field(default=0.0, alias="referralFeePercent")
    referral_fee_usd: Float = Field(default=0.0, alias="referralFeeUsd")
    referral_fee: Str = Field(default="", alias="referralFee")
    network_fees_usd: Optional[Float] = Field(default=None, alias="networkFeesUsd")
    network_fees: Optional[Str] = Field(default=None, alias="networkFees")
    net_amount_usd: Optional[Float] = Field(default=None, alias="netAmountUsd")
    net_amount: Optional[Str] = Field(default=None, alias="netAmount")
    user_name: Optional[Str] = Field(default=None, alias="userName")
    user_last_name: Optional[Str] = Field(default=None, alias="userLastName")
    customer_name: Optional[Str] = Field(default=None, alias="customerName")
    customer_last_name: Optional[Str] = Field(default=None, alias="customerLastName")


# ── Webhook endpoints and deliveries ─────────────────────────────────────────


class WebhookEndpoint(Model):
    """A webhook endpoint of a space."""

    uuid: Str = ""
    test: Bool = False
    #: Where the events are posted.
    url: Str = ""
    #: The event types it receives; empty: every type.
    events: List[EventTypeT] = Field(default_factory=list)
    #: True for an organization endpoint that also receives its members' events.
    include_members: Bool = Field(default=False, alias="includeMembers")
    #: v2 (the event envelope), or v1 for an endpoint migrated from v1.
    payload_version: WebhookPayloadVersionT = Field(default="", alias="payloadVersion")
    description: Str = ""
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: When its secret last changed.
    rotated_at: Optional[Time] = Field(default=None, alias="rotatedAt")
    #: When it was disabled; ``None`` while enabled.
    disabled_at: Optional[Time] = Field(default=None, alias="disabledAt")
    #: failing, owner or closed.
    disabled_reason: Optional[EndpointDisabledReasonT] = Field(default=None, alias="disabledReason")
    failing_since: Optional[Time] = Field(default=None, alias="failingSince")
    last_delivered_at: Optional[Time] = Field(default=None, alias="lastDeliveredAt")


class WebhookEndpointCreated(WebhookEndpoint):
    """``webhooks.endpoints.create``'s answer: the endpoint and its ``secret`` (``whsec_…``),
    shown only this once: store it to verify the deliveries."""

    secret: Str = ""


class DeliveryAttempt(Model):
    """One attempt to deliver an event to an endpoint."""

    uuid: Str = ""
    #: The event (``evt_…``).
    event_id: Str = Field(default="", alias="eventId")
    event_type: EventTypeT = Field(default="", alias="eventType")
    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
    #: 1 for the first, then one more per retry or resend.
    attempt: Int = 0
    #: True when the endpoint answered with a 2xx.
    delivered: Bool = False
    #: True when it was not posted (a member's endpoint with members.webhooks off).
    skipped: Optional[Bool] = None
    #: The endpoint's answer; ``None`` when it didn't answer.
    status_code: Optional[Int] = Field(default=None, alias="statusCode")
    #: Why it wasn't delivered.
    error: Optional[Str] = None
    #: How long it took, in milliseconds.
    duration_ms: Int = Field(default=0, alias="durationMs")
    attempted_at: Time = Field(default=ZERO_TIME, alias="attemptedAt")


class EndpointDelivery(Model):
    """An event's deliveries to one endpoint."""

    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
    #: The endpoint's URL now.
    url: Str = ""
    #: True when one attempt was answered with a 2xx.
    delivered: Bool = False
    #: Its attempts, oldest first.
    attempts: List[DeliveryAttempt] = Field(default_factory=list)
