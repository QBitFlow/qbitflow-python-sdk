"""Every response model against fixtures with every wire key (Go models_test.go)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pydantic
import pytest

import qbitflow
import qbitflow.models
from qbitflow import (
    AccountingEvent,
    AccountingEventType,
    Balance,
    Bill,
    Chain,
    CheckoutSessionStatus,
    CreatedCheckoutSession,
    CreatedInvitation,
    Credential,
    Currency,
    Customer,
    CustomerSummary,
    EventDetail,
    Failure,
    FeeLine,
    FeeLineType,
    HeldFunds,
    HeldFundsReleased,
    Invitation,
    LedgerEntryType,
    Me,
    Member,
    MemberHeldFunds,
    MemberJoined,
    NetworkFeesPayer,
    NotRefundableReason,
    Page,
    Payment,
    PaymentCompleted,
    Product,
    Refund,
    RefundStatus,
    Role,
    Settlement,
    SettlementTransaction,
    Split,
    Subscription,
    SubscriptionSessionData,
    TokenAmount,
    Transaction,
    TransactionKind,
    TransactionType,
    TransferSettlement,
    Wallet,
    WebhookEndpointCreated,
)
from qbitflow.models import Model

from .conftest import FIXTURES

#: Fixtures with every wire key of each response model, all non-empty, shaped like the docs'
#: examples (a 10 USD price paid in BASE:USDC, 0.99 % fee): tests/fixtures/models.json, built
#: from the Go SDK's models_test.go.
RAW: Dict[str, Any] = json.loads((FIXTURES / "models.json").read_text())

MODEL_TYPES: Dict[str, Any] = {
    "Currency": Currency,
    "Currency/native": Currency,
    "Payment": Payment,
    "PaymentCompleted": PaymentCompleted,
    "SubscriptionSessionData": SubscriptionSessionData,
    "Bill": Bill,
    "Transaction": Transaction,
    "Failure": Failure,
    "CreatedCheckoutSession": CreatedCheckoutSession,
    "CheckoutSessionStatus": CheckoutSessionStatus,
    "Subscription": Subscription,
    "TestBill": qbitflow.TestBill,
    "Refund": Refund,
    "Customer": Customer,
    "Product": Product,
    "Member": Member,
    "MemberJoined": MemberJoined,
    "HeldFunds": HeldFunds,
    "MemberHeldFunds": MemberHeldFunds,
    "HeldFundsReleased": HeldFundsReleased,
    "Wallet": Wallet,
    "Invitation": Invitation,
    "CreatedInvitation": CreatedInvitation,
    "AccountingEvent": AccountingEvent,
    "WebhookEndpointCreated": WebhookEndpointCreated,
    "EventDetail": EventDetail,
    "Me": Me,
    "Page": Page[CustomerSummary],
}
MODEL_FIXTURES: Dict[str, Tuple[Any, str]] = {
    name: (MODEL_TYPES[name], json.dumps(RAW[name])) for name in MODEL_TYPES
}


def test_every_fixture_has_a_model() -> None:
    assert set(RAW) == set(MODEL_TYPES)


def fx(name: str) -> str:
    return MODEL_FIXTURES[name][1]


def _keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_keys(v) for v in value]
    return None


def _dump(value: Model) -> Any:
    out = value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, EventDetail):  # the envelope is nested in Python, flat on the wire
        out = {**out["event"], "deliveries": out["deliveries"]}
    return out


@pytest.mark.parametrize("name", sorted(MODEL_FIXTURES))
def test_models_match_the_wire(name: str) -> None:
    model, raw = MODEL_FIXTURES[name]
    value = model.model_validate(json.loads(raw))
    got, want = _dump(value), json.loads(raw)
    if isinstance(value, EventDetail):
        # Python decodes an event's data eagerly (Go keeps it raw): the typed data writes back
        # its zero-valued fields too, so its keys are a superset of the fixture's.
        assert set(want.pop("data")) <= set(got.pop("data"))
    # Round trip: the model writes back exactly the fixture's keys, at every level: no field
    # without a wire key, no wire key lost.
    assert _keys(got) == _keys(want)


def test_model_values() -> None:
    p = Payment.model_validate_json(fx("Payment"))
    assert (p.amount, p.amount_min_units, p.amount_usd) == ("10", "10000000", "10")
    assert p.price_usd == "8.5" and p.product_name == "Pro"
    assert p.currency.code == "BASE:USDC" and p.currency.chain == Chain.BASE
    assert p.currency.main_currency_id == 3
    assert p.metadata == {"orderId": "order-1", "crm:customer": "C-5521"}
    assert p.paid == "10.0042" and p.paid_usd == "10.0042"
    assert p.from_ == "0xfrom" and p.to_dict()["from"] == "0xfrom"
    assert p.customer is not None and p.customer.deleted and p.customer.first_name == "Ada"
    assert p.refund is not None and p.refund.status == RefundStatus.APPROVED
    assert p.refund.refund_percent == "50" and p.refund.amount == "5.0021"
    assert p.refund.responded_at is not None
    assert p.refundable is False and p.not_refundable_reason == NotRefundableReason.REFUND_EXISTS

    st = p.settlement
    assert st.fee_percent == "0.99"
    assert st.organization_fee is not None and st.organization_fee.address == "0xorg"
    assert st.organization_fee.fee_percent == "10"
    assert st.referral_fee is not None and st.referral_fee.fee_percent == "20"
    assert st.split is not None and st.split.merchant.amount == "8.9109"
    assert st.split.platform.amount_min_units == "79200"
    assert st.split.network_fee is not None and st.split.network_fee.amount_usd == "0.0042"
    tx = st.transaction
    assert tx is not None and tx.block_number == "52468103" and tx.gas_used == 95000
    assert tx.fee.amount_min_units == "1140000000000" and tx.l1_fee is not None
    assert tx.native_price_usd == "4512.37"
    assert tx.block_time == datetime(2026, 10, 1, 11, 59, 58, tzinfo=timezone.utc)
    assert p.fees == [
        FeeLine(
            type=FeeLineType.CUSTOM, label="VAT (20%)", description="French VAT", amount_usd="1.30"
        ),
        FeeLine(type=FeeLineType.PROCESSING_FEE, label="Processing fee", amount_usd="0.20"),
    ]

    native = Currency.model_validate_json(fx("Currency/native"))
    assert native.address is None and native.main_currency_id is None
    assert native.code == "ETH" and native.decimals == 18

    ss = SubscriptionSessionData.model_validate_json(fx("SubscriptionSessionData"))
    assert ss.amount_usd == "4.81" and ss.price_usd == "3.99" and len(ss.fees) == 2
    assert ss.tx_type == TransactionType.CREATE_SUBSCRIPTION
    assert [c.code for c in ss.available_currencies] == ["BASE:USDC", "ETH"]
    assert ss.metadata["orderId"] == "order-1044" and ss.min_periods == 3
    assert ss.frequency.value == 1 and ss.frequency.unit == "months" and ss.upgrading_from_trial

    sb = Subscription.model_validate_json(fx("Subscription"))
    assert sb.price_usd == "9.99" and sb.currency.symbol == "USDC"
    allowance = sb.allowance
    assert allowance is not None and allowance.amount == "110" and allowance.remaining_periods == 0
    assert allowance.max_per_period == "30" and allowance.max_per_period_min_units == "30000000"
    assert sb.last_billed_at and sb.next_billing_at and sb.cancellable_at
    assert sb.metadata["plan"] == "pro" and sb.management_page_link
    assert sb.dunning is not None and sb.dunning.remaining_attempts == 3

    t = Transaction.model_validate_json(fx("Transaction"))
    assert t.type == TransactionKind.BILL and t.price_usd == "8.5" and t.period_end is not None
    assert t.settlement.split is not None and t.metadata == {"k": "v"}

    tb = qbitflow.TestBill.model_validate_json(fx("TestBill"))
    assert tb.bill_uuid.startswith("sub-hist@") and tb.stage == "waiting"
    assert tb.next_attempt_at is not None

    r = Refund.model_validate_json(fx("Refund"))
    assert r.paid == "10.0042" and r.refund_percent == "50" and r.amount == "5.0021"
    assert r.settlement is not None and r.settlement.transaction is not None
    assert r.settlement.transaction.block_number == "52468103"
    assert r.currency.id == 8 and r.customer_uuid == "c-1"

    ae = AccountingEvent.model_validate_json(fx("AccountingEvent"))
    assert ae.currency == "USDC" and ae.currency_price_usd == "1.00002"
    assert ae.network_fees_paid_by == NetworkFeesPayer.MERCHANT
    assert ae.network_fees_currency == "ETH" and ae.network_fees_currency_decimals == 18
    assert ae.network_fees_currency_price_usd == "4512.37"
    assert ae.net_amount == "-10.0042" and ae.gross_amount_min_units == "-10004200"
    assert ae.tx_uuid == "refund@1" and ae.related_tx_uuid == "pay@0"
    assert ae.reference == "r" and ae.related_reference == "r0"
    assert ae.platform_fee_percent == "0.99"
    assert ae.tx_time_utc == datetime(2026, 9, 13, 19, 23, 26, 620000, tzinfo=timezone.utc)

    inv = CreatedInvitation.model_validate_json(fx("CreatedInvitation"))
    assert isinstance(inv, Invitation)  # flat: the invitation's fields and its link
    assert inv.uuid == "i-1" and inv.test is True and inv.hold_funds is False and inv.link
    assert inv.organization_fee_percent == "0"

    hf = HeldFunds.model_validate_json(fx("HeldFunds"))
    assert hf.total_usd == "-1.0933"
    assert hf.ledgers[0].settlement is not None and hf.ledgers[1].settlement is None
    assert hf.ledgers[1].type == LedgerEntryType.REFUND and hf.ledgers[1].owed == "-10.0042"
    assert hf.ledgers[1].refunded_tx_uuid == "pay@1"

    w = Wallet.model_validate_json(fx("Wallet"))
    assert w.address == "0xpk" and w.currency.code == "ETH"
    tw = w.token_wallets[0]
    assert tw.currency.code == "BASE:USDC" and tw.balance is not None
    assert tw.balance.amount == "12.5" and tw.balance.currency.id == 8

    m = Member.model_validate_json(fx("Member"))
    assert m.first_name == "Ada" and m.organization_fee_percent == "7.5"
    assert [c.code for c in m.accepted_currencies] == ["BASE:USDC"]

    me = Me.model_validate_json(fx("Me"))
    assert me.on_behalf_of_user_uuid == "m-1" and me.space is not None
    assert me.space.role == Role.ADMIN and me.space.organization_fee_percent == "7.5"
    assert me.space.member is not None and me.space.member.first_name == "Ada"
    assert me.space.trusted_at is not None
    assert me.space.created_at == datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    # The session-only fields (user, spaces, reauthenticatedUntil) are not modelled: ignored.
    me2 = Me.model_validate_json('{"credential":"apiKey","spaces":[],"user":{"uuid":"u"}}')
    assert me2.credential == Credential.API_KEY and "spaces" not in me2.to_dict()

    rel = HeldFundsReleased.model_validate_json(fx("HeldFundsReleased"))
    assert rel.amount_usd == "10" and rel.received and rel.type == "heldFundsRelease"
    assert isinstance(rel.settlement, TransferSettlement)
    assert rel.ledgers[0].type == LedgerEntryType.PAYMENT and rel.ledgers[0].owed == "9.901"

    mj = MemberJoined.model_validate_json(fx("MemberJoined"))
    assert mj.invitation_uuid == "i-1" and mj.accepted_currencies == [] and mj.last_name is None

    detail = EventDetail.model_validate_json(fx("EventDetail"))
    assert detail.event.id == "evt_1" and detail.event.user_uuid == "m-1"
    attempt = detail.deliveries[0].attempts[0]
    assert attempt.skipped is True and attempt.status_code == 500 and attempt.duration_ms == 120

    page = Page[CustomerSummary].model_validate_json(fx("Page"))
    assert page.has_more is True and page.next_cursor == "djF8MDE5Y2FkZmQ" and len(page.items) == 1


def test_accounting_event_rows() -> None:
    # A referralFee row: only what the referrer earned; no network fees, no payer; an absent fee
    # is None, never "0".
    rf = AccountingEvent.model_validate_json(
        '{"txTimeUtc":"2026-09-13T19:23:26Z","type":"referralFee","referralFeeUsd":"0.02",'
        '"chain":"SOL","currency":"SOL","currencyDecimals":9,"currencyPriceUsd":"150.5",'
        '"referralFee":"0.000132","referralFeeMinUnits":"132000","referralFeePercent":"20",'
        '"blockNumberOrSlot":"1"}'
    )
    assert rf.type == AccountingEventType.REFERRAL_FEE and rf.network_fees_paid_by is None
    assert rf.network_fees_currency_decimals is None and rf.network_fees is None
    assert rf.referral_fee == "0.000132" and rf.referral_fee_min_units == "132000"
    assert rf.currency == "SOL" and rf.gross_amount_usd is None and rf.organization_fee is None
    assert rf.token_contract_or_mint is None and rf.tx_uuid is None
    # The draft's names are no fields any more; an unknown payer is kept as its raw string.
    row = AccountingEvent.model_validate_json(
        '{"type":"bill","paymentUuid":"pay@1","paymentReference":"r","networkFeesPaidBy":"other"}'
    )
    assert row.type == AccountingEventType.BILL and row.tx_uuid is None and row.reference is None
    assert "paymentUuid" not in row.to_dict() and not hasattr(row, "payment_uuid")
    assert row.network_fees_paid_by == "other"
    assert not isinstance(row.network_fees_paid_by, NetworkFeesPayer)
    assert NetworkFeesPayer("organization") is NetworkFeesPayer.ORGANIZATION


def test_optional_fields() -> None:
    """The minimal shapes the docs allow: every O field absent is None, every L field [], every
    metadata {} (types.md §1)."""
    sub = Subscription.model_validate_json(
        '{"uuid":"sub@1","to":"0xt","status":"trial","priceUsd":"9.99","fees":[],"metadata":{},'
        '"currency":' + fx("Currency") + ',"frequency":{"value":1,"unit":"months"},'
        '"currentPeriodEnd":"2026-10-15T12:00:00Z"}'
    )
    assert sub.from_ is None and sub.product_uuid is None and sub.subscription_hash is None
    assert sub.allowance is None and sub.last_billed_at is None and sub.next_billing_at is None
    assert sub.cancellable_at is None and sub.dunning is None and sub.action_required is None
    assert sub.current_period_end is not None and sub.management_page_link is None

    pay = Payment.model_validate_json(
        '{"uuid":"pay@1","amount":"10","priceUsd":"10","fees":[],"metadata":{},'
        '"settlement":{"feePercent":"0.99"}}'
    )
    assert pay.settlement.split is None and pay.settlement.transaction is None
    assert pay.confirmed_at is None and pay.paid is None and pay.refund is None
    assert pay.refundable is None and pay.customer is None and pay.product_description is None

    ref = Refund.model_validate_json(
        '{"uuid":"refund@1","txUuid":"pay@1","status":"pending","paid":"10",'
        '"paidMinUnits":"10000000","refundPercent":"100","amount":"10","amountMinUnits":"10000000"}'
    )
    assert ref.reason is None and ref.merchant_message is None and ref.responded_at is None
    assert ref.tx_hash is None and ref.paid_usd is None and ref.amount_usd is None
    assert ref.settlement is None and ref.approval is None

    team = Invitation.model_validate_json(
        '{"uuid":"i-2","email":"a@b.co","role":"admin","expiresAt":"2026-10-08T12:00:00Z",'
        '"createdAt":"2026-10-01T12:00:00Z","status":"pending"}'
    )
    assert team.test is None and team.hold_funds is None and team.organization_fee_percent is None
    assert team.role == Role.ADMIN and team.accepted_at is None

    # Lenient on absence and null (behaviour §6): zero values, never an error.
    nulls = Product.model_validate_json(
        '{"uuid":"p-1","description":null,"metadata":null,"subscription":null,"priceUsd":null}'
    )
    assert nulls.description is None and nulls.metadata == {} and nulls.subscription is None
    assert nulls.price_usd == "" and nulls.is_active is False
    empty = Payment.model_validate({})
    assert empty.currency == Currency() and empty.settlement == Settlement() and empty.fees == []
    assert TokenAmount().amount_usd is None and Split().merchant == TokenAmount()
    assert SettlementTransaction().fee == TokenAmount() and Balance().currency == Currency()
    assert Page[Product].model_validate({}).has_more is False
    assert Page[Product].model_validate({}).next_cursor is None


@pytest.mark.parametrize(
    "model, raw",
    [
        (Payment, '{"amount":10}'),
        (Payment, '{"priceUsd":8.5}'),
        (Payment, '{"fees":[{"amountUsd":2}]}'),
        (Payment, '{"fees":{"type":"custom"}}'),
        (Payment, '{"settlement":{"feePercent":0.99}}'),
        (Product, '{"priceUsd":1e2}'),
        (Member, '{"organizationFeePercent":5}'),
        (Refund, '{"refundPercent":100}'),
        (HeldFunds, '{"totalUsd":-10}'),
        (Balance, '{"amount":12.5}'),
        (AccountingEvent, '{"grossAmount":-10.0042}'),
        (Payment, '{"currency":8}'),
        (Subscription, '{"allowance":"110000000"}'),
        (Page[Product], '{"items":[],"hasMore":"false"}'),
        (Customer, '{"metadata":{"k":1}}'),
    ],
)
def test_strict_types(model: Any, raw: str) -> None:
    """A present value of the wrong JSON type is refused: money, token amounts and rates are
    decimal strings (a JSON number is never parsed into a float); an object refuses a list."""
    with pytest.raises(pydantic.ValidationError):
        model.model_validate_json(raw)


def test_integral_floats_into_integers() -> None:
    f = Failure.model_validate_json('{"attempt":2.0,"currency":{"id":8.0,"decimals":6.0}}')
    assert f.attempt == 2 and f.currency.id == 8 and f.currency.decimals == 6
    s = Subscription.model_validate_json(
        '{"allowance":{"amount":"1","amountMinUnits":"1","remainingPeriods":11.0}}'
    )
    assert s.allowance is not None and s.allowance.remaining_periods == 11


def test_models_build_by_field_name() -> None:
    c = Customer(uuid="c-1", first_name="Ada", last_name="Lovelace")
    assert c.to_dict() == {
        "uuid": "c-1",
        "firstName": "Ada",
        "lastName": "Lovelace",
        "email": "",
        "verified": False,
        "metadata": {},
        "createdAt": "0001-01-01T00:00:00Z",
        "test": False,
    }


def test_fees() -> None:
    none = Payment.model_validate_json('{"uuid":"pay@1","amount":"10","priceUsd":"10","fees":[]}')
    assert none.price_usd == "10" and none.fees == [] and "fees" in none.to_dict()
    absent = Payment.model_validate_json('{"uuid":"pay@1","fees":null}')
    assert absent.price_usd == "" and absent.fees == []
    p = Payment.model_validate_json(
        '{"amountUsd":"12.03","priceUsd":"10","fees":[{"type":"tip","label":"Tip","amountUsd":"2"},'
        '{"type":"processingFee","label":"Processing fee","description":null,"amountUsd":"0.03"}]}'
    )
    # An unknown FeeLineType is kept as its raw string.
    assert p.fees[0].type == "tip" and not isinstance(p.fees[0].type, FeeLineType)
    assert p.fees[0].amount_usd == "2" and p.fees[1].description is None
    assert p.fees[1].type == FeeLineType.PROCESSING_FEE
    assert FeeLine().type == "" and FeeLine().amount_usd == ""
    assert Subscription.model_validate_json('{"priceUsd":"9.99","fees":null}').fees == []


def test_test_bill_is_not_collected_by_pytest() -> None:
    assert getattr(qbitflow.TestBill, "__test__", True) is False
    assert "__test__" not in qbitflow.TestBill.model_fields


def test_has_access() -> None:
    end = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    sub = Subscription(current_period_end=end)
    assert sub.has_access(datetime(2026, 10, 31, 11, 59, tzinfo=timezone.utc))
    assert not sub.has_access(end)  # equal → no access
    assert not Subscription().has_access(end)
    assert sub.has_access(datetime(2026, 10, 1))  # a naive datetime is UTC
    with pytest.raises(qbitflow.ValidationError):
        sub.has_access("2026-10-01")  # type: ignore[arg-type]


def test_every_model_is_exported() -> None:
    for name in qbitflow.models.__all__:
        assert name in qbitflow.__all__ and hasattr(qbitflow, name), name
    for gone in (
        "CheckoutSession",
        "CombinedPayment",
        "CombinedPaymentSource",
        "BillingState",
        "InvitationCreated",
        "MemberHeldFundsSummary",
        "SubscriptionCreated",
        "RefundCompletedEvent",
        "RefundDeniedEvent",
        "PaymentMetadata",
        "TxMetadata",
        "TxAmounts",
    ):
        assert not hasattr(qbitflow, gone), gone
