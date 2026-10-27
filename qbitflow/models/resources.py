"""Refunds, customers, products, the key's identity, members and invitations, held funds,
wallets, the accounting export, webhook endpoints and deliveries."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Int, Model, Str, Time, UInt
from ._fields import (
    AccountingEventTypeT,
    ChainT,
    CheckoutSessionStatusValueT,
    EndpointDisabledReasonT,
    EventTypeT,
    InvitationStatusT,
    LedgerEntryTypeT,
    NetworkFeesPayerT,
    RefundInitiatorT,
    RefundStatusT,
    RoleT,
)
from .common import (
    Attempt,
    Currency,
    CustomerSummary,
    Metadata,
    Settlement,
    TokenAmount,
    TransferSettlement,
)
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
    "MemberHeldFunds",
    "Invitation",
    "CreatedInvitation",
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
    """Where a pending request's refund transfer stands once sent."""

    #: ``waitingConfirmation`` (sent, being confirmed on-chain) or ``created`` (its last attempt
    #: failed: ``last_attempt``; send it again from the dashboard).
    status: CheckoutSessionStatusValueT = ""
    #: The transfer being confirmed, once known.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: Why the last attempt failed.
    last_attempt: Optional[Attempt] = Field(default=None, alias="lastAttempt")


class Refund(Model):
    """A refund of a payment (``pay@…``) or a subscription bill (``sub-hist@…``): a customer's
    request the merchant approves or rejects, or a refund the merchant sent from the dashboard
    (recorded once its transfer confirmed: approved, nothing before). Refunds are read only here.
    Also the data of the ``refund.requested``, ``refund.approved`` and ``refund.rejected``
    events."""

    #: The refund's id (``refund@…``).
    uuid: Str = ""
    #: The refunded transaction: a payment (``pay@…``) or a bill (``sub-hist@…``).
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: Why the refund: the customer's reason, or the merchant's when it started the refund;
    #: ``None`` when it gave none.
    reason: Optional[Str] = None
    #: pending (a customer's request not answered yet), approved (its transfer confirmed) or
    #: rejected.
    status: RefundStatusT = ""
    #: When it was requested (or prepared by the merchant).
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The merchant's message to the customer (why it rejected the request, or a note on a refund
    #: it started); ``None`` when none.
    merchant_message: Optional[Str] = Field(default=None, alias="merchantMessage")
    #: When the refund was answered (rejected, or its transfer confirmed); ``None`` while pending.
    responded_at: Optional[Time] = Field(default=None, alias="respondedAt")
    #: True in test mode.
    test: Bool = False
    #: The member whose space the refunded transaction is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: The refund transfer's transaction, once approved; ``None`` before.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: ``customer`` (requested by the customer, the merchant answers) or ``merchant`` (sent by the
    #: merchant without a request, from the dashboard: recorded once confirmed, approved).
    initiated_by: RefundInitiatorT = Field(default="", alias="initiatedBy")
    #: True when the refunded payment was paid to the organization's wallet, which holds
    #: the seller's funds: the organization decides the refund and sends it from its wallet. Once
    #: sent, it is a negative line of the seller's held funds.
    held: Bool = False
    #: What the customer paid for the refunded transaction (its amount, fees included, and the
    #: network fee they paid on top), in the currency's units: the base of ``refund_percent``.
    paid: Str = ""
    #: The same in the currency's smallest unit, a string of digits.
    paid_min_units: Str = Field(default="", alias="paidMinUnits")
    #: The same in USD at the refunded transaction's time; ``None`` when unknown (a request made
    #: before it was recorded).
    paid_usd: Optional[Str] = Field(default=None, alias="paidUsd")
    #: The share of ``paid`` the refund sends back, a percent string (``"100"``: all of it). A
    #: customer requests ``"100"``; the merchant sets it when it approves, or when it starts the
    #: refund.
    refund_percent: Str = Field(default="", alias="refundPercent")
    #: What the refund sends back: ``refund_percent`` of ``paid``, rounded down to a whole min
    #: unit, in the currency's units.
    amount: Str = ""
    #: The same in the currency's smallest unit, a string of digits.
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: The same in USD at the refunded transaction's time; ``None`` when unknown.
    amount_usd: Optional[Str] = Field(default=None, alias="amountUsd")
    #: The currency paid, and sent back.
    currency: Currency = Field(default_factory=Currency)
    #: The refund transfer's transaction (its block, what it cost), once approved; ``None``
    #: before.
    settlement: Optional[TransferSettlement] = None
    #: The currency's chain.
    chain: Optional[ChainT] = None
    #: The refund transfer on the chain's explorer, once sent.
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: Where the refund transfer stands while the request is pending and it was sent (approved, or
    #: answered by the merchant's own refund): being confirmed, or its last attempt failed (API
    #: reads only, never in webhooks).
    approval: Optional[RefundApproval] = None
    #: The refunded transaction's customer (API reads only).
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: What the refunded transaction paid for (API reads only).
    product_name: Optional[Str] = Field(default=None, alias="productName")
    #: Names the refunded transaction's customer, even once deleted (API reads only).
    customer: Optional[CustomerSummary] = None


# ── Customers and products ───────────────────────────────────────────────────


class Customer(Model):
    """A merchant's customer: who pays, named on the payments and subscriptions it makes."""

    #: The customer's id (a UUIDv7).
    uuid: Str = ""
    #: The first name.
    first_name: Str = Field(default="", alias="firstName")
    #: The last name; ``None`` when not given.
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    #: The email address, lowercase (matched case-insensitively). Several customers of a space may
    #: share one: ``customers.list(email=...)`` returns them all.
    email: Str = ""
    #: The phone number; ``None`` when not given.
    phone_number: Optional[Str] = Field(default=None, alias="phoneNumber")
    #: The physical address; ``None`` when not given.
    address: Optional[Str] = None
    #: The merchant's reference (its id in your system), unique per space; ``None`` without one.
    reference: Optional[Str] = None
    #: The merchant's own data on the customer (never copied onto its payments or
    #: subscriptions); ``{}`` without any.
    metadata: Metadata = Field(default_factory=dict)
    #: When it was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: True in test mode.
    test: Bool = False
    #: The member whose space it is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


class Product(Model):
    """Something a merchant sells: a one-time product, or a subscription product with its terms.
    Its payment link opens a checkout of it."""

    #: The product's id (a UUIDv7).
    uuid: Str = ""
    #: Its name.
    name: Str = ""
    #: Its description; ``None`` without one.
    description: Optional[Str] = None
    #: Its price in USD, a decimal string (``"12.5"``): what a checkout of the product charges
    #: before its fees (per period for a subscription product).
    price_usd: Str = Field(default="", alias="priceUsd")
    #: When it was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: False for a hidden product: out of ``products.list`` unless ``include_hidden``, still
    #: readable and editable by uuid. Hidden are the inline products of subscription checkouts,
    #: those of a removed member or a closed organization, and those hidden with ``update``.
    is_active: Bool = Field(default=False, alias="isActive")
    #: The merchant's reference, unique per space and mode (the uuid when none was given).
    reference: Str = ""
    #: The merchant's own data on the product (never copied onto its checkouts, payments or
    #: subscriptions); ``{}`` without any.
    metadata: Metadata = Field(default_factory=dict)
    #: A subscription product's terms (the defaults of its subscription checkouts); ``None`` for
    #: a one-time product.
    subscription: Optional[SubscriptionTerms] = None
    #: The product's shareable link: opening it starts a checkout of the product.
    payment_link: Optional[Str] = Field(default=None, alias="paymentLink")
    #: True in test mode.
    test: Bool = False
    #: The member whose space it is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


# ── The key's identity, members, invitations ─────────────────────────────────


class MeMember(Model):
    """Names the member whose space a request acts in."""

    #: The member (as ``members.list`` lists them).
    user_uuid: Str = Field(default="", alias="userUuid")
    #: The first name.
    first_name: Str = Field(default="", alias="firstName")
    #: The last name; ``None`` when the account has none.
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    #: The email.
    email: Str = ""


class MeSpace(Model):
    """The space a request acts in: one organization's data in one mode, the organization's
    shared space or a member's personal space."""

    #: The space's id.
    uuid: Str = ""
    #: Its organization.
    organization_uuid: Str = Field(default="", alias="organizationUuid")
    #: Its organization's name.
    organization_name: Str = Field(default="", alias="organizationName")
    #: The member whose space it is; ``None`` for the organization's own space.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: The space's mode: True for test, False for live.
    test: Bool = False
    #: The key's role in the organization: ``admin`` (an organization key) or ``user`` (a
    #: member's key).
    role: RoleT = ""
    #: Names the member whose space it is; ``None`` for the organization's own space.
    member: Optional[MeMember] = None
    #: The organization's fee on the member's payments in this space, a percent string (``"0"``:
    #: none); ``None`` for the organization's own space.
    organization_fee_percent: Optional[Str] = Field(default=None, alias="organizationFeePercent")
    #: When the organization started paying the member directly; ``None`` while it holds their
    #: funds (always set on the organization's own space).
    trusted_at: Optional[Time] = Field(default=None, alias="trustedAt")
    #: When the space was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")


class Me(Model):
    """What the API key is, and where the request acts (``client.me()``)."""

    #: The key's id.
    api_key_uuid: Optional[Str] = Field(default=None, alias="apiKeyUuid")
    #: What the request may do in the space: ``admin`` (an organization key) or ``user`` (a
    #: member's key, or an organization key acting ``On-Behalf-Of`` a member).
    role: Optional[RoleT] = None
    #: The member an organization key acts as (``On-Behalf-Of``): the space is that member's.
    #: ``None`` otherwise.
    on_behalf_of_user_uuid: Optional[Str] = Field(default=None, alias="onBehalfOfUserUuid")
    #: The space the request reads and writes in (``space.test`` says the mode).
    space: Optional[MeSpace] = None


class Member(Model):
    """A member of the organization (a seller of a marketplace), in one mode: their personal
    space there."""

    #: The member's id: what ``on_behalf_of`` (``client.on_behalf_of``, ``RequestOptions``)
    #: takes.
    user_uuid: Str = Field(default="", alias="userUuid")
    #: The first name.
    first_name: Str = Field(default="", alias="firstName")
    #: The last name; ``None`` when the account has none.
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    #: The email.
    email: Str = ""
    #: The mode.
    test: Bool = False
    #: The organization's fee on the member's payments in this mode, a percent string (``"0"``:
    #: none).
    organization_fee_percent: Str = Field(default="", alias="organizationFeePercent")
    #: When the organization started paying them directly; ``None`` while it holds their funds
    #: (held funds).
    trusted_at: Optional[Time] = Field(default=None, alias="trustedAt")
    #: When they joined in this mode.
    joined_at: Time = Field(default=ZERO_TIME, alias="joinedAt")
    #: The currencies a checkout of the member can be paid in now: those their wallets accept,
    #: always within the organization's (the organization's own while it holds their funds).
    #: Empty: a checkout of theirs answers 409 ``merchant_not_ready``.
    accepted_currencies: List[Currency] = Field(default_factory=list, alias="acceptedCurrencies")
    #: Their personal space in this mode.
    space_uuid: Str = Field(default="", alias="spaceUuid")


class LedgerEntry(Model):
    """A line of a member's held funds: a payment made to them while the organization held their
    funds (it adds what the organization owes them), or a refund of one (it takes off what the
    refund sent back to the customer)."""

    #: The line's transaction: the payment (``pay@…``) or the refund (``refund@…``).
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: payment or refund.
    type: LedgerEntryTypeT = ""
    #: What the line is, in words (``"Payment pay@…"``).
    description: Str = ""
    #: On a refund line, the payment it refunds; ``None`` on the others.
    refunded_tx_uuid: Optional[Str] = Field(default=None, alias="refundedTxUuid")
    #: What the customer paid (a payment), or what a refund sent back (positive:
    #: ``owed_usd`` is its negative), in USD, a decimal string.
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: A payment's fees and split (the member was owed ``settlement.split.merchant``);
    #: ``None`` on a refund line.
    settlement: Optional[Settlement] = None
    #: The currency paid (and refunded).
    currency: Currency = Field(default_factory=Currency)
    #: What the line counts for in a release, in the currency's units, exact: a payment's
    #: merchant share, or minus what a refund sent back (negative). In
    #: ``heldFunds.released``: what it counted for in that release.
    owed: Str = ""
    #: The same in the currency's smallest unit (negative for a refund).
    owed_min_units: Str = Field(default="", alias="owedMinUnits")
    #: The same in USD, at the payment's time (negative for a refund).
    owed_usd: Str = Field(default="", alias="owedUsd")
    #: When the line was recorded.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")


class HeldFunds(Model):
    """What the organization holds for a member in one mode (held funds)."""

    #: The lines not settled yet, oldest first: the payments held (positive), and the refunds
    #: sent of them (negative, type refund). Empty when nothing is held.
    ledgers: List[LedgerEntry] = Field(default_factory=list)
    #: What the organization owes the member, in USD, a decimal string: the sum of the lines'
    #: ``owed_usd``. A release pays it, converted at the release's price. ``"0"`` or negative when
    #: refunds cancel out the payments (nothing to send: the held funds are closed instead).
    total_usd: Str = Field(default="", alias="totalUsd")


class MemberHeldFunds(Model):
    """What the organization owes one member (``members.list_held_funds``)."""

    #: The member (a removed member still owed too).
    user_uuid: Str = Field(default="", alias="userUuid")
    #: What the organization owes them, in USD, a decimal string (``"0"`` or negative when refunds
    #: cancel out the payments).
    total_usd: Str = Field(default="", alias="totalUsd")
    #: Their lines not settled: payments held, refunds of them.
    count: Int = 0
    #: Their oldest line not settled: how long the organization has held funds for them.
    oldest_at: Time = Field(default=ZERO_TIME, alias="oldestAt")


class Invitation(Model):
    """An invitation to the organization: to be a member in one mode (role ``user``), or to its
    team (role ``admin``, from the dashboard: mode-free, so ``test``, ``hold_funds`` and
    ``organization_fee_percent`` are ``None``)."""

    #: The invitation's id.
    uuid: Str = ""
    #: A member invitation's mode; ``None`` for a team invitation.
    test: Optional[Bool] = None
    #: The invited address.
    email: Str = ""
    #: ``admin`` (the team) or ``user`` (a member).
    role: RoleT = ""
    #: For a member, True when the organization holds their payments until it trusts them
    #: (``members.trust``), False when they are paid directly; ``None`` for the team.
    hold_funds: Optional[Bool] = Field(default=None, alias="holdFunds")
    #: For a member, the organization's fee on their payments, a percent string (``"0"``: none);
    #: ``None`` for the team.
    organization_fee_percent: Optional[Str] = Field(default=None, alias="organizationFeePercent")
    #: Where the person goes once they accepted (with ``?invitationUuid=<uuid>``); ``None`` when
    #: none.
    redirect_url: Optional[Str] = Field(default=None, alias="redirectUrl")
    #: When it expires.
    expires_at: Time = Field(default=ZERO_TIME, alias="expiresAt")
    #: The account that accepted it; ``None`` until accepted.
    accepted_by_user_uuid: Optional[Str] = Field(default=None, alias="acceptedByUserUuid")
    #: When it was accepted; ``None`` until then.
    accepted_at: Optional[Time] = Field(default=None, alias="acceptedAt")
    #: When it was revoked (or replaced by a newer one); ``None`` unless revoked.
    revoked_at: Optional[Time] = Field(default=None, alias="revokedAt")
    #: When it was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: pending, accepted, revoked or expired (computed when read).
    status: InvitationStatusT = ""


class CreatedInvitation(Invitation):
    """An invitation just created (``invitations.create``): the invitation's fields and its
    ``link``, only returned here."""

    #: The link to accept it, also emailed to the person unless ``send_email`` was False: share it
    #: in your own onboarding if you prefer.
    link: Str = ""


# ── Wallets ──────────────────────────────────────────────────────────────────


class Balance(TokenAmount):
    """What a wallet holds of a currency, read on its chain now. ``amount``,
    ``amount_min_units`` and ``amount_usd`` (its value at today's price; ``None`` when QBitFlow has
    no price it can trust right now) come from :class:`TokenAmount`::

        {"currency": {…}, "amount": "12.5", "amountMinUnits": "12500000", "amountUsd": "12.5"}
    """

    #: The currency held.
    currency: Currency = Field(default_factory=Currency)


class TokenWallet(Model):
    """A currency a wallet accepts on its chain: a token (USDC on Base) or the chain's native
    coin."""

    #: The token wallet's id.
    uuid: Str = ""
    #: When the wallet started accepting it.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The currency accepted.
    currency: Currency = Field(default_factory=Currency)
    #: The wallet it belongs to.
    wallet_uuid: Str = Field(default="", alias="walletUuid")
    #: What the wallet holds of the currency, read on its chain now: set only by
    #: ``wallets.list(with_balances=True)``, and ``None`` when the chain couldn't be read.
    balance: Optional[Balance] = None


class Wallet(Model):
    """A space's receiving address on one chain (``currency``, its native coin), with the
    currencies it accepts on that chain (``token_wallets``). Its mode is the space's. Wallets are
    added and removed in the dashboard."""

    #: The wallet's id.
    uuid: Str = ""
    #: When it was added.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The wallet's address on its chain (EVM: ``0x…``, Solana: base58).
    address: Str = ""
    #: True in test mode.
    test: Bool = False
    #: The member whose wallet it is; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: The currencies it accepts on its chain; empty when none.
    token_wallets: List[TokenWallet] = Field(default_factory=list, alias="tokenWallets")
    #: The chain, by its native coin.
    currency: Currency = Field(default_factory=Currency)


# ── Accounting ───────────────────────────────────────────────────────────────


class AccountingEvent(Model):
    """One row of the accounting export (``accounting.export_json``): a payment, a bill or a
    refund of the space, or a fee it earned on another space's payment or bill.

    The export is flat on purpose, for spreadsheets: one column per key, the currency named by
    its symbol, chain and decimals (no nested currency object). Every amount is a decimal string,
    in the currency's units (7.5 USDC, not 7500000) with its on-chain twin ``…_min_units`` beside
    it; a value the row doesn't have (a fee that doesn't apply, an amount not known) is ``None``
    (absent), never ``"0"``. The fields are in the CSV's column order, laid out to be read left to
    right: what happened and when, the USD amounts (gross, the fees, net), the same amounts in the
    currency paid, the network fees, the rates, the on-chain proof, then the ids. Read CSV columns
    by header name, not position. Rows are ordered by ``tx_time_utc``, then ``type``, then
    ``tx_uuid``.

    ``gross_amount = platform_fee + organization_fee + net_amount`` exactly (an absent fee counts
    0); a refund's net is its gross, both negative. A referralFee row only tells what the
    referrer earned, when and on which chain: ``type``, ``tx_time_utc``, ``chain``,
    ``block_number_or_slot``, ``currency``, ``currency_decimals``, ``currency_price_usd``,
    ``token_contract_or_mint``, ``referral_fee_percent``, ``referral_fee_usd``, ``referral_fee``
    and ``referral_fee_min_units``; every other field is ``None``.
    """

    #: When the transaction's block was mined (UTC): an event is in the export of that day.
    tx_time_utc: Time = Field(default=ZERO_TIME, alias="txTimeUtc")
    #: payment, bill, refund, organizationFee or referralFee.
    type: AccountingEventTypeT = ""
    #: The payment's own reference (yours), when it has one.
    reference: Optional[Str] = None
    #: For a refund of a payment, the payment's reference (a bill has none).
    related_reference: Optional[Str] = Field(default=None, alias="relatedReference")
    #: The product's name.
    product_name: Optional[Str] = Field(default=None, alias="productName")
    #: Your reference of the customer.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")

    #: What the customer paid in USD (a refund: what went back, negative).
    gross_amount_usd: Optional[Str] = Field(default=None, alias="grossAmountUsd")
    #: QBitFlow's fee in USD, the referrer's share included; ``None`` when none (a refund).
    platform_fee_usd: Optional[Str] = Field(default=None, alias="platformFeeUsd")
    #: The referrer's share of the platform fee in USD; ``None`` when no referral applied.
    referral_fee_usd: Optional[Str] = Field(default=None, alias="referralFeeUsd")
    #: The organization's fee on a member's payment in USD; ``None`` when none.
    organization_fee_usd: Optional[Str] = Field(default=None, alias="organizationFeeUsd")
    #: What the merchant received (a payment or a bill: after the fees) or sent back (a refund:
    #: the refunded amount, negative), in USD. Network fees are never part of it.
    net_amount_usd: Optional[Str] = Field(default=None, alias="netAmountUsd")

    #: The chain.
    chain: ChainT = ""
    #: What was paid, as markets name it: the token (USDC) or the chain's native currency (ETH,
    #: SOL; Base's is ETH). Always set.
    currency: Str = ""
    #: The currency's decimals: an amount × 10^decimals is its min units on-chain.
    currency_decimals: UInt = Field(default=0, alias="currencyDecimals")
    #: The currency's USD price the amounts were converted at: ``gross_amount_usd /
    #: gross_amount``, to 8 decimals (a refund: its refunded transaction's). ``None`` without a
    #: gross amount.
    currency_price_usd: Optional[Str] = Field(default=None, alias="currencyPriceUsd")
    #: The gross amount in the currency's units.
    gross_amount: Optional[Str] = Field(default=None, alias="grossAmount")
    #: The same on-chain: an integer string.
    gross_amount_min_units: Optional[Str] = Field(default=None, alias="grossAmountMinUnits")
    #: QBitFlow's fee in the currency's units, the referrer's share included.
    platform_fee: Optional[Str] = Field(default=None, alias="platformFee")
    #: The same on-chain.
    platform_fee_min_units: Optional[Str] = Field(default=None, alias="platformFeeMinUnits")
    #: The referrer's share, paid out of the platform fee, in the currency's units: what a
    #: referralFee event earned. ``None`` when no referral applied (none, or past its deadline).
    referral_fee: Optional[Str] = Field(default=None, alias="referralFee")
    #: The same on-chain.
    referral_fee_min_units: Optional[Str] = Field(default=None, alias="referralFeeMinUnits")
    #: The organization's fee in the currency's units; ``None`` when none.
    organization_fee: Optional[Str] = Field(default=None, alias="organizationFee")
    #: The same on-chain.
    organization_fee_min_units: Optional[Str] = Field(default=None, alias="organizationFeeMinUnits")
    #: The net amount in the currency's units (a refund: the refunded amount, negative).
    net_amount: Optional[Str] = Field(default=None, alias="netAmount")
    #: The same on-chain.
    net_amount_min_units: Optional[Str] = Field(default=None, alias="netAmountMinUnits")

    #: Whose wallet paid the transaction's network fees, never part of the net: payer (a payment
    #: or a bill: on top of the amount), merchant (a refund the space sent: book it apart) or
    #: organization (a refund of a payment the organization held for its member). ``None`` on
    #: referralFee rows.
    network_fees_paid_by: Optional[NetworkFeesPayerT] = Field(
        default=None, alias="networkFeesPaidBy"
    )
    #: The network fees in ``network_fees_currency``'s units; ``None`` when not recorded.
    network_fees: Optional[Str] = Field(default=None, alias="networkFees")
    #: The same in ``network_fees_currency``'s min units.
    network_fees_min_units: Optional[Str] = Field(default=None, alias="networkFeesMinUnits")
    #: What paid them: the event's currency on a payment or a bill (the payer's gas refund, taken
    #: in it), the chain's native currency (ETH, SOL) on a refund.
    network_fees_currency: Optional[Str] = Field(default=None, alias="networkFeesCurrency")
    #: ``network_fees_currency``'s decimals; ``None`` when absent.
    network_fees_currency_decimals: Optional[UInt] = Field(
        default=None, alias="networkFeesCurrencyDecimals"
    )
    #: ``network_fees_currency``'s USD price ``network_fees_usd`` was converted at; ``None`` when
    #: unknown.
    network_fees_currency_price_usd: Optional[Str] = Field(
        default=None, alias="networkFeesCurrencyPriceUsd"
    )
    #: The network fees in USD; ``None`` when unknown.
    network_fees_usd: Optional[Str] = Field(default=None, alias="networkFeesUsd")

    #: QBitFlow's fee rate on the event, a percent string (``"0.99"`` = 0.99 %).
    platform_fee_percent: Optional[Str] = Field(default=None, alias="platformFeePercent")
    #: The referrer's share of the platform fee (``"20"`` = 20 % of it), when a referral applied.
    referral_fee_percent: Optional[Str] = Field(default=None, alias="referralFeePercent")
    #: The organization's fee rate on the event, when it took one.
    organization_fee_percent: Optional[Str] = Field(default=None, alias="organizationFeePercent")

    #: The sender; ``None`` on referralFee rows.
    from_address: Optional[Str] = Field(default=None, alias="fromAddress")
    #: The receiver; ``None`` on referralFee rows.
    to_address: Optional[Str] = Field(default=None, alias="toAddress")
    #: The transaction's hash; ``None`` on referralFee rows.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: The block (or slot).
    block_number_or_slot: Optional[Str] = Field(default=None, alias="blockNumberOrSlot")
    #: The token's contract (EVM) or mint (Solana); ``None`` for a native currency.
    token_contract_or_mint: Optional[Str] = Field(default=None, alias="tokenContractOrMint")
    #: The transaction on the chain's explorer; ``None`` on referralFee rows.
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: The transaction's public page for its customer; ``None`` on referralFee rows.
    receipt_url: Optional[Str] = Field(default=None, alias="receiptUrl")

    #: The event's transaction, prefixed by its type: ``pay@`` (a payment), ``sub-hist@`` (a
    #: bill), ``refund@`` (a refund); ``None`` on referralFee rows.
    tx_uuid: Optional[Str] = Field(default=None, alias="txUuid")
    #: For a refund, the refunded payment's (``pay@…``) or bill's (``sub-hist@…``) id.
    related_tx_uuid: Optional[Str] = Field(default=None, alias="relatedTxUuid")
    #: The product; ``None`` when the event has none.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The product's reference.
    product_reference: Optional[Str] = Field(default=None, alias="productReference")
    #: The product's description.
    product_description: Optional[Str] = Field(default=None, alias="productDescription")
    #: The customer.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: The member whose space the event is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


# ── Webhook endpoints and deliveries ─────────────────────────────────────────


class WebhookEndpoint(Model):
    """A webhook endpoint of a space."""

    #: The endpoint's id.
    uuid: Str = ""
    #: True in test mode.
    test: Bool = False
    #: Where the events are posted.
    url: Str = ""
    #: The event types it receives (stored sorted, without duplicates); empty: every type,
    #: including types added later.
    events: List[EventTypeT] = Field(default_factory=list)
    #: True for an organization endpoint that also receives its members' events.
    include_members: Bool = Field(default=False, alias="includeMembers")
    #: A note for the dashboard; ``None`` when none.
    description: Optional[Str] = None
    #: When it was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: When it was disabled (it receives nothing): after 3 days without a successful delivery
    #: (live mode only), or by its owner; ``None`` while enabled. ``update(enabled=True)`` enables
    #: it again.
    disabled_at: Optional[Time] = Field(default=None, alias="disabledAt")
    #: Why: failing (live mode only: a test-mode endpoint is never disabled for failing), owner or
    #: closed.
    disabled_reason: Optional[EndpointDisabledReasonT] = Field(default=None, alias="disabledReason")
    #: When its deliveries started failing (live mode: failing for 3 days, it is disabled).
    failing_since: Optional[Time] = Field(default=None, alias="failingSince")
    #: Its last successful delivery.
    last_delivered_at: Optional[Time] = Field(default=None, alias="lastDeliveredAt")


class WebhookEndpointCreated(WebhookEndpoint):
    """``webhooks.endpoints.create``'s answer: the endpoint and its secret."""

    #: The secret (``whsec_…``) that verifies the signature of its deliveries. Shown once: store
    #: it. Left out of ``repr()`` (and so of logs that print the model).
    secret: Str = Field(default="", repr=False)


class DeliveryAttempt(Model):
    """One attempt to deliver an event to an endpoint."""

    #: The attempt's id.
    uuid: Str = ""
    #: The event (``evt_…``).
    event_id: Str = Field(default="", alias="eventId")
    #: The event's type.
    event_type: EventTypeT = Field(default="", alias="eventType")
    #: The endpoint.
    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
    #: 1 for the first, then one more per retry or resend.
    attempt: Int = 0
    #: True when the endpoint answered with a 2xx.
    delivered: Bool = False
    #: True when it was not posted: a member's endpoint while the organization's
    #: ``members.webhooks`` policy was off for them (never retried; not counted against the
    #: endpoint's health). The API leaves it out when false.
    skipped: Bool = False
    #: The endpoint's answer; ``None`` when it didn't answer, or when the attempt was skipped.
    status_code: Optional[Int] = Field(default=None, alias="statusCode")
    #: Why it wasn't delivered (a skipped attempt's says the policy is off).
    error: Optional[Str] = None
    #: How long it took, in milliseconds.
    duration_ms: Int = Field(default=0, alias="durationMs")
    #: When it was made.
    attempted_at: Time = Field(default=ZERO_TIME, alias="attemptedAt")


class EndpointDelivery(Model):
    """An event's deliveries to one endpoint."""

    #: The endpoint.
    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
    #: The endpoint's URL now.
    url: Str = ""
    #: True when one attempt was answered with a 2xx.
    delivered: Bool = False
    #: Its attempts, oldest first.
    attempts: List[DeliveryAttempt] = Field(default_factory=list)
