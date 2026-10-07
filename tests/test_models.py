"""Every response model against fixtures with every wire key (Go models_test.go)."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

import pytest

from qbitflow import (
    AccountingEvent,
    Bill,
    BillingState,
    CheckoutSession,
    CheckoutSessionStatus,
    CombinedPayment,
    Currency,
    Customer,
    CustomerSummary,
    Failure,
    HeldFunds,
    Invitation,
    InvitationCreated,
    Me,
    Member,
    MemberHeldFundsSummary,
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

    m = Member.model_validate_json('{"organizationFeePercent":2,"acceptedCurrencyIds":[8.0]}')
    assert m.organization_fee_percent == 2 and m.accepted_currency_ids == [8]


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
