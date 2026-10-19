"""Every response model against fixtures with every wire key (Go models_test.go)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pytest

from qbitflow import (
    AccountingEvent,
    AccountingEventType,
    Bill,
    BillingState,
    CheckoutSession,
    CheckoutSessionStatus,
    CombinedPayment,
    Currency,
    Customer,
    CustomerSummary,
    Failure,
    FeeLine,
    FeeLineType,
    HeldFunds,
    Invitation,
    InvitationCreated,
    Me,
    Member,
    MemberHeldFundsSummary,
    NetworkFeesPayer,
    NotRefundableReason,
    Page,
    Payment,
    Product,
    Refund,
    Role,
    Subscription,
    Wallet,
    WebhookEndpointCreated,
)

from .conftest import FIXTURES

#: Fixtures with every wire key of each response model (docs/core Go tags), all non-empty:
#: tests/fixtures/models.json, the same as the Go SDK's models_test.go.
RAW = json.loads((FIXTURES / "models.json").read_text())

MODEL_TYPES: Dict[str, Any] = {
    "Currency": Currency,
    "Payment": Payment,
    "Bill": Bill,
    "CombinedPayment": CombinedPayment,
    "Failure": Failure,
    "CheckoutSession": CheckoutSession,
    "CheckoutSessionStatus": CheckoutSessionStatus,
    "Subscription": Subscription,
    "BillingState": BillingState,
    "Refund": Refund,
    "Customer": Customer,
    "Product": Product,
    "Member": Member,
    "HeldFunds": HeldFunds,
    "MemberHeldFundsSummary": MemberHeldFundsSummary,
    "Wallet": Wallet,
    "Invitation": Invitation,
    "InvitationCreated": InvitationCreated,
    "AccountingEvent": AccountingEvent,
    "WebhookEndpointCreated": WebhookEndpointCreated,
    "Me": Me,
    "Page": Page[CustomerSummary],
}
MODEL_FIXTURES: Dict[str, Tuple[Any, str]] = {
    name: (MODEL_TYPES[name], json.dumps(RAW[name])) for name in MODEL_TYPES
}


def fx(name: str) -> str:
    return MODEL_FIXTURES[name][1]


def _without_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_without_nulls(v) for v in value]
    return value


def _keys(value: Any, path: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _keys(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [_keys(v, path) for v in value]
    return None


@pytest.mark.parametrize("name", sorted(MODEL_FIXTURES))
def test_models_match_the_wire(name: str) -> None:
    model, raw = MODEL_FIXTURES[name]
    value = model.model_validate(json.loads(raw))
    # Round trip: the model writes back exactly the fixture's (non-null) keys, at every level:
    # no field without a wire key, no wire key lost.
    out = value.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert _keys(out) == _keys(_without_nulls(json.loads(raw)))


def test_model_values() -> None:
    p = Payment.model_validate_json(fx("Payment"))
    assert p.customer is not None and p.customer.deleted is True
    assert p.refund is not None and p.refund.responded_at is None
    assert p.refundable is False and p.not_refundable_reason == NotRefundableReason.REFUND_EXISTS
    assert p.metadata.organization_fee is not None and p.metadata.organization_fee.fee_percent == 10
    assert p.metadata.tx_amounts.usd.organization == 0.98
    assert p.from_ == "0xfrom" and p.to_dict()["from"] == "0xfrom"

    inv = InvitationCreated.model_validate_json(fx("InvitationCreated"))
    assert inv.invitation.test is None and inv.invitation.trust_layer is None
    assert inv.invitation.role == Role.ADMIN and inv.link

    hf = HeldFunds.model_validate_json(fx("HeldFunds"))
    assert hf.total_amount < 0 and hf.ledgers[0].metadata is None
    assert hf.ledgers[0].owed_min_units == "-10004200"

    assert p.price == 8.5 and [f.type for f in p.fees] == [
        FeeLineType.CUSTOM,
        FeeLineType.PROCESSING_FEE,
    ]
    assert p.fees[0].description == "Standard rate" and p.fees[1].description is None
    assert p.fees[0].amount_usd == "1.35" and p.fees[1].label == "Processing fee"

    m = Member.model_validate_json('{"organizationFeePercent":2,"acceptedCurrencyIds":[8.0]}')
    assert m.organization_fee_percent == 2 and m.accepted_currency_ids == [8]

    sb = Subscription.model_validate_json(fx("Subscription"))
    assert sb.price_usd == "9.99" and len(sb.fees) == 2
    assert sb.fees[0] == FeeLine(
        type=FeeLineType.CUSTOM, label="VAT (20%)", description="French VAT", amount_usd="2.00"
    )
    assert sb.fees[1].type == FeeLineType.PROCESSING_FEE

    ae = AccountingEvent.model_validate_json(fx("AccountingEvent"))
    assert ae.currency == "USDC" and ae.currency_price_usd == 1
    assert ae.network_fees_paid_by == NetworkFeesPayer.MERCHANT
    assert ae.network_fees_currency == "ETH" and ae.network_fees_currency_decimals == 18
    assert ae.network_fees_currency_price_usd == 4512.37
    assert ae.net_amount == "-10.0042" and ae.gross_amount == "-10.0042"
    assert ae.tx_time_utc == datetime(2026, 9, 13, 19, 23, 26, 620071, tzinfo=timezone.utc)


def test_accounting_event_rows() -> None:
    # A referralFee row: only what the referrer earned; no network fees, no payer.
    rf = AccountingEvent.model_validate_json(
        '{"txTimeUtc":"2026-09-13T19:23:26Z","type":"referralFee","referralFeeUsd":0.02,'
        '"chain":"SOL","currency":"SOL","currencyDecimals":9,"currencyPriceUsd":150.5,'
        '"referralFee":"0.000132","referralFeePercent":20,"blockNumberOrSlot":"1",'
        '"tokenContractOrMint":""}'
    )
    assert rf.type == AccountingEventType.REFERRAL_FEE and rf.network_fees_paid_by is None
    assert rf.network_fees_currency_decimals is None and rf.network_fees is None
    assert rf.referral_fee == "0.000132" and rf.currency == "SOL" and rf.gross_amount_usd is None
    # The removed v2 keys are not fields any more; an unknown payer is kept as its raw string.
    row = AccountingEvent.model_validate_json(
        '{"type":"refund","tokenSymbol":"USDC","userName":"Ada","networkFeesPaidBy":"other"}'
    )
    assert row.currency == "" and "tokenSymbol" not in row.to_dict()
    assert "userName" not in row.to_dict() and not hasattr(row, "user_name")
    assert row.network_fees_paid_by == "other"
    assert not isinstance(row.network_fees_paid_by, NetworkFeesPayer)
    assert NetworkFeesPayer("organization") is NetworkFeesPayer.ORGANIZATION


def test_models_build_by_field_name() -> None:
    c = Customer(uuid="c-1", last_name="Lovelace")
    assert c.to_dict() == {
        "uuid": "c-1",
        "name": "",
        "lastName": "Lovelace",
        "email": "",
        "verified": False,
        "createdAt": "0001-01-01T00:00:00Z",
        "test": False,
    }


def test_fees() -> None:
    # A payment recorded before fees: price absent (0), fees absent ([]).
    old = Payment.model_validate_json('{"uuid":"pay@1","amount":10}')
    assert old.price == 0 and old.fees == [] and "fees" in old.to_dict()
    # A payment with fees: amount = price + the lines.
    paid = Payment.model_validate_json(
        '{"amount":4.88,"price":3.99,"fees":[{"type":"custom","label":"Shipping",'
        '"amountUsd":"0.75"},{"type":"processingFee","label":"Processing fee","amountUsd":"0.14"}]}'
    )
    assert paid.price == 3.99 and [f.amount_usd for f in paid.fees] == ["0.75", "0.14"]
    # An unknown FeeLineType is kept as its raw string.
    line = FeeLine.model_validate_json('{"type":"tax","label":"VAT","amountUsd":"1.20"}')
    assert line.type == "tax" and not isinstance(line.type, FeeLineType)
    assert line.to_dict() == {"type": "tax", "label": "VAT", "amountUsd": "1.20"}
    # amountUsd is a decimal string: a number there is a wrong type.
    with pytest.raises(ValueError):
        FeeLine.model_validate_json('{"type":"custom","label":"VAT","amountUsd":1.2}')
    assert FeeLineType("processingFee") is FeeLineType.PROCESSING_FEE
    assert FeeLine().type == "" and FeeLine().amount_usd == ""
    # A subscription's fees: absent or null is an empty list.
    assert Subscription.model_validate_json('{"priceUsd":"9.99","fees":null}').fees == []
    assert Subscription.model_validate_json('{"priceUsd":"9.99"}').fees == []
