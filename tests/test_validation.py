"""Client-side validation rules (Go validate_test.go): each case calls the method against a stub
server and checks which fields fail (or that the request is sent)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, List, Tuple

import pytest

from qbitflow import (
    NOT_GIVEN,
    CheckoutFees,
    Duration,
    DurationUnit,
    EventType,
    FeeItem,
    NotFoundError,
    QBitFlow,
    RefundStatus,
    ServerError,
    SubscriptionTermsParams,
    TransactionKind,
    ValidationError,
)
from qbitflow._validation import (
    Validator,
    check_path_required,
    check_path_tx_id,
    check_path_uuid,
    is_idempotency_key,
    is_request_id,
    is_tx_id,
)

from .conftest import MEMBER_UUID, make_client, static


@pytest.fixture
def client() -> QBitFlow:
    c, _, _ = make_client(static(200, "{}"))
    return c


def fields(call: Callable[[], Any]) -> List[str]:
    """The failing fields of a call ([] when it was sent)."""
    try:
        call()
    except ValidationError as exc:
        assert exc.status is None, "a client-side error has no status"
        for f in exc.field_errors:
            assert f.message.startswith(f.field + " "), f
        return [f.field for f in exc.field_errors]
    except (ServerError, NotFoundError):
        pass  # sent; the stub's {} may not fit the answer (an empty page for get_by_reference)
    return []


GOOD_NAMES = [
    "Pro plan",
    "O’Brien",
    "Smith & Co",
    "prod/backend",
    "Dr. Who (II)",
    "Zoë",
    "李小龙",
    "ab",
    "é" * 100,
]
BAD_NAMES = [
    "a",
    "  ",
    " \t ",
    "line\nbreak",
    "tab\there",
    "<b>",
    "x{y}",
    "a[1]",
    "back`tick",
    "back\\slash",
    "pi|pe",
    "semi;colon",
    'quo"te',
    "til~de",
    "car^et",
    "bidi‮name",
    "bidi⁦x",
    "nul\x00x",
    "é" * 101,
    "  ",
]


@pytest.mark.parametrize("name", GOOD_NAMES)
def test_name_good(client: QBitFlow, name: str) -> None:
    assert fields(lambda: client.products.create(name=name, price_usd="1")) == []


@pytest.mark.parametrize("name", BAD_NAMES)
def test_name_bad(client: QBitFlow, name: str) -> None:
    assert fields(lambda: client.products.create(name=name, price_usd="1")) == ["name"]


def test_first_and_last_name(client: QBitFlow) -> None:
    assert (
        fields(lambda: client.customers.create(first_name="Ada", last_name="L", email="a@b.co"))
        == []
    )
    assert fields(
        lambda: client.customers.create(first_name="Ada", last_name="L\n", email="a@b.co")
    ) == ["lastName"]
    assert fields(lambda: client.customers.create(first_name="A", email="a@b.co")) == ["firstName"]
    assert fields(lambda: client.customers.create(first_name=None, email="a@b.co")) == ["firstName"]
    assert fields(lambda: client.customers.update(MEMBER_UUID, first_name="<x>")) == ["firstName"]


@pytest.mark.parametrize(
    "text", ["Two\nlines\r\nand\ttab", "Lifetime access (Pro) & more: 100%", "ok"]
)
def test_text_good(client: QBitFlow, text: str) -> None:
    assert fields(lambda: client.products.create(name="Pro", price_usd="1", description=text)) == []


@pytest.mark.parametrize("text", ["   ", "\n\n", "<script>", "x\x07bell", "x" * 501, "a"])
def test_text_bad(client: QBitFlow, text: str) -> None:
    assert fields(lambda: client.products.create(name="Pro", price_usd="1", description=text)) == [
        "description"
    ]


def test_text_bounds(client: QBitFlow) -> None:
    assert (
        fields(lambda: client.customers.create(first_name="Ada", email="a@b.co", address="x")) == []
    )
    assert fields(
        lambda: client.customers.create(first_name="Ada", email="a@b.co", address="x" * 501)
    ) == ["address"]
    assert fields(
        lambda: client.webhooks.endpoints.create(url="https://x.io", description="x" * 201)
    ) == ["description"]


@pytest.mark.parametrize("ref", ["order-1042", "INV_2026.10:01@shop", "a", "r" * 100])
def test_reference_good(client: QBitFlow, ref: str) -> None:
    assert (
        fields(lambda: client.customers.create(first_name="Ada", email="a@b.co", reference=ref))
        == []
    )


@pytest.mark.parametrize("ref", ["has space", "slash/x", "é", "#1", "r" * 101])
def test_reference_bad(client: QBitFlow, ref: str) -> None:
    assert fields(
        lambda: client.customers.create(first_name="Ada", email="a@b.co", reference=ref)
    ) == ["reference"]


def test_reference_session_and_filter(client: QBitFlow) -> None:
    got = fields(
        lambda: client.checkout_sessions.create_payment(
            product_reference="bad ref", reference="o/1", customer_reference="c 1"
        )
    )
    assert got == ["reference", "productReference", "customerReference"]
    for lister in (
        client.subscriptions.list,
        client.products.list,
        client.customers.list,
        client.payments.list,
    ):
        assert fields(lambda: lister(reference="bad ref")) == ["reference"]
        assert fields(lambda: lister(reference="crm:42@shop.v1")) == []


@pytest.mark.parametrize(
    "lookup", ["products", "customers", "payments", "subscriptions"], ids=lambda n: n
)
@pytest.mark.parametrize("ref", ["bad ref", "", " ", "r" * 101, "a/b", None, 42], ids=repr)
def test_get_by_reference_checks_the_reference(lookup: str, ref: Any) -> None:
    client, server, _ = make_client(static(200, '{"items":[],"hasMore":false}'))
    service = getattr(client, lookup)
    assert fields(lambda: service.get_by_reference(ref)) == ["reference"]
    assert server.requests == []


@pytest.mark.parametrize("ref", [".", "..", "...", "r" * 100, "INV_2026.10:01@shop"])
def test_get_by_reference_valid_references_are_sent(ref: str) -> None:
    client, server, _ = make_client(static(200, '{"items":[],"hasMore":false}'))
    with pytest.raises(NotFoundError):
        client.products.get_by_reference(ref)
    assert len(server.requests) == 1 and server.requests[0].path == "/products"


@pytest.mark.parametrize(
    "phone", ["+33 6 12 34 56 78", "555 (123) 4567", "06.12.34.56.78", "123456"]
)
def test_phone_good(client: QBitFlow, phone: str) -> None:
    assert (
        fields(
            lambda: client.customers.create(first_name="Ada", email="a@b.co", phone_number=phone)
        )
        == []
    )


@pytest.mark.parametrize(
    "phone", ["12345", "+", "phone", "+33 6 12 34 56 7x", "-123456", "123456-", "+" + "1" * 32]
)
def test_phone_bad(client: QBitFlow, phone: str) -> None:
    assert fields(
        lambda: client.customers.create(first_name="Ada", email="a@b.co", phone_number=phone)
    ) == ["phoneNumber"]


@pytest.mark.parametrize("email", ["a@b.co", "First.Last+tag@Example.COM", "x@sub.domain.io"])
def test_email_good(client: QBitFlow, email: str) -> None:
    assert fields(lambda: client.customers.create(first_name="Ada", email=email)) == []


@pytest.mark.parametrize(
    "email",
    [
        "no-at",
        "a@b",
        "@b.co",
        "a@.b.co",
        "a@b.co.",
        "a b@c.io",
        "a@@b.co",
        "a@b@c.io",
        "a" * 250 + "@b.co",
    ],
)
def test_email_bad(client: QBitFlow, email: str) -> None:
    assert fields(lambda: client.customers.create(first_name="Ada", email=email)) == ["email"]


def test_email_elsewhere(client: QBitFlow) -> None:
    assert fields(lambda: client.customers.create(first_name="Ada", email=None)) == ["email"]
    assert fields(lambda: client.customers.update(MEMBER_UUID, email="nope")) == ["email"]
    assert fields(lambda: client.invitations.create(email="nope", hold_funds=True)) == ["email"]
    assert fields(lambda: client.customers.list(email="nope")) == ["email"]


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.example.com/thanks?id={{UUID}}&t={{TRANSACTION_TYPE}}",
        "http://localhost:8080/x",
        "HTTPS://EXAMPLE.COM",
    ],
)
def test_url_good(client: QBitFlow, url: str) -> None:
    assert (
        fields(
            lambda: client.checkout_sessions.create_payment(
                product_uuid=MEMBER_UUID, success_url=url, cancel_url=url
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://x.io",
        "/relative",
        "https://",
        "javascript:alert(1)",
        "https://x.io/" + "p" * 2040,
        "https://exa mple.com",
    ],
)
def test_url_bad(client: QBitFlow, url: str) -> None:
    assert fields(
        lambda: client.checkout_sessions.create_payment(product_uuid=MEMBER_UUID, success_url=url)
    ) == ["successUrl"]


def test_url_elsewhere(client: QBitFlow) -> None:
    assert fields(
        lambda: client.invitations.create(email="a@b.co", hold_funds=True, redirect_url="nope")
    ) == ["redirectUrl"]
    assert fields(lambda: client.webhooks.endpoints.create(url="")) == ["url"]
    assert fields(lambda: client.webhooks.endpoints.update(MEMBER_UUID, url="x")) == ["url"]


# ── Money: decimal strings (or Decimal), never float/int ─────────────────────

GOOD_PRICES: List[Any] = [
    "0.01",
    "5",
    "9.99",
    "12.50",
    "007.5",
    "1000000",
    "1000000.00",
    Decimal("9.99"),
    Decimal("1000000"),
]
BAD_PRICES: List[Any] = [
    "0",
    "0.00",
    "-1",
    "+1",
    "1e2",
    "1E2",
    ".5",
    "5.",
    "1.999",
    "1,5",
    " 9.99",
    "9.99 ",
    "1000000.01",
    "1000001",
    "NaN",
    "Infinity",
    "٤",
    "abc",
    Decimal("1E+2"),
    Decimal("4.990"),
    Decimal("-1"),
    Decimal("NaN"),
    9.99,
    10,
    0.1,
    True,
    [1],
]


@pytest.mark.parametrize("price", GOOD_PRICES, ids=repr)
def test_price_good(client: QBitFlow, price: Any) -> None:
    assert fields(lambda: client.products.create(name="Pro", price_usd=price)) == []


@pytest.mark.parametrize("price", BAD_PRICES + [None, "", "  "], ids=repr)
def test_price_bad(client: QBitFlow, price: Any) -> None:
    assert fields(lambda: client.products.create(name="Pro", price_usd=price)) == ["priceUsd"]


def test_money_messages(client: QBitFlow) -> None:
    with pytest.raises(ValidationError) as info:
        client.products.create(name="Pro", price_usd=9.99)
    assert info.value.field_errors[0].message == (
        'priceUsd must be a decimal string (e.g. "12.50") or a decimal.Decimal, not a number '
        "(money is never a float or an int: a float cannot carry 0.1)"
    )
    with pytest.raises(ValidationError) as info:
        client.products.create(name="Pro", price_usd=[1])
    assert info.value.field_errors[0].message.endswith("not a list")
    with pytest.raises(ValidationError) as info:
        client.products.create(name="Pro", price_usd="1e2")
    assert info.value.field_errors[0].message == (
        'priceUsd must be an amount in USD as a decimal string (e.g. "12.50"): above 0, at most '
        "1000000, with at most 2 decimals"
    )
    with pytest.raises(ValidationError) as info:
        client.products.create(name="Pro", price_usd=None)
    assert info.value.field_errors[0].message == "priceUsd is required"


def test_price_update(client: QBitFlow) -> None:
    assert fields(lambda: client.products.update(MEMBER_UUID, price_usd="0")) == ["priceUsd"]
    assert fields(lambda: client.products.update(MEMBER_UUID, price_usd=0.0)) == ["priceUsd"]
    assert fields(lambda: client.products.update(MEMBER_UUID, price_usd=12)) == ["priceUsd"]
    assert fields(lambda: client.products.update(MEMBER_UUID, price_usd="")) == []  # unchanged
    assert fields(lambda: client.products.update(MEMBER_UUID, price_usd=Decimal("12.5"))) == []
    assert fields(lambda: client.products.update(MEMBER_UUID)) == []


# The percent rule: a decimal string (or a Decimal), digits with at most 2 decimals, at most 16
# characters, from 0 to its maximum (50 for organization_fee_percent), compared exactly.
@pytest.mark.parametrize(
    "pct",
    [
        "0",
        "0.00",
        "0.05",
        "1.5",
        "33.33",
        "50",
        "50.00",
        "007.5",
        "0000000000000050",  # 16 characters: the most a percentage may have
        Decimal("7.5"),
        Decimal("0"),
        Decimal("0.5"),
        Decimal("50"),
    ],
    ids=repr,
)
def test_fee_good(client: QBitFlow, pct: Any) -> None:
    assert fields(lambda: client.members.update(MEMBER_UUID, organization_fee_percent=pct)) == []
    assert (
        fields(
            lambda: client.invitations.create(
                email="a@b.co", hold_funds=False, organization_fee_percent=pct
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "pct",
    [
        "-0.01",
        "-1",
        "50.01",
        "51",
        "1.234",
        "1.155",
        "0.30000000000000004",
        "1e1",
        ".5",
        "5.",
        "50%",
        " 5",
        "NaN",
        "Infinity",
        "x",
        "00000000000000050",  # 17 characters: over the 16 a percentage may have
        Decimal("-1"),
        Decimal("1E+1"),
        5,
        50,
        0.0,
        0.5,
        0.1 + 0.2,
        True,
    ],
    ids=repr,
)
def test_fee_bad(client: QBitFlow, pct: Any) -> None:
    assert fields(lambda: client.members.update(MEMBER_UUID, organization_fee_percent=pct)) == [
        "organizationFeePercent"
    ]
    assert fields(
        lambda: client.invitations.create(
            email="a@b.co", hold_funds=False, organization_fee_percent=pct
        )
    ) == ["organizationFeePercent"]


def test_fee_required_on_member_update(client: QBitFlow) -> None:
    for missing in (None, "", " "):
        assert fields(
            lambda: client.members.update(MEMBER_UUID, organization_fee_percent=missing)
        ) == ["organizationFeePercent"]


# ── Metadata ─────────────────────────────────────────────────────────────────


def meta_fields(client: QBitFlow, metadata: Any) -> List[str]:
    return fields(lambda: client.products.create(name="Pro", price_usd="1", metadata=metadata))


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"sku": "PRO-M"},
        {"crm:id": "C-1", "a.b_c-d": "x", "K" * 40: "v"},
        {"empty": ""},
        {"note": "é" * 500},
        {"note": "Zoë & Co (2026) <b>"},  # values have no character rule but controls and bidi
        {f"k{i}": "v" for i in range(50)},
    ],
    ids=repr,
)
def test_metadata_good(client: QBitFlow, metadata: Any) -> None:
    assert meta_fields(client, metadata) == []


@pytest.mark.parametrize(
    "metadata, want",
    [
        ({f"k{i}": "v" for i in range(51)}, ["metadata"]),
        ({"a b": "x"}, ["metadata"]),
        ({"": "x"}, ["metadata"]),
        ({"K" * 41: "x"}, ["metadata"]),
        ({"é": "x"}, ["metadata"]),
        ({"k/1": "x"}, ["metadata"]),
        ({5: "x"}, ["metadata"]),
        ({"note": "é" * 501}, ["metadata.note"]),
        ({"note": "a\tb"}, ["metadata.note"]),
        ({"note": "line\nbreak"}, ["metadata.note"]),
        ({"note": "nul\x00"}, ["metadata.note"]),
        ({"note": "bidi\u202ex"}, ["metadata.note"]),
        ({"note": "iso\u2066x"}, ["metadata.note"]),
        ({"note": 5}, ["metadata.note"]),
        ({"note": None}, ["metadata.note"]),
        (["sku"], ["metadata"]),
        ("sku=1", ["metadata"]),
        # Sorted by key; the bad keys are reported once, last.
        ({"z": "\x07", "bad key": "x", "a": "\u202a"}, ["metadata.a", "metadata.z", "metadata"]),
    ],
    ids=repr,
)
def test_metadata_bad(client: QBitFlow, metadata: Any, want: List[str]) -> None:
    assert meta_fields(client, metadata) == want


def test_metadata_bad_key_not_echoed(client: QBitFlow) -> None:
    with pytest.raises(ValidationError) as info:
        client.products.create(name="Pro", price_usd="1", metadata={"secret key!": "x"})
    message = info.value.field_errors[0].message
    assert "secret key!" not in message and "secret key!" not in str(info.value)
    assert message == "metadata keys must be 1 to 40 characters among A-Z a-z 0-9 _ - . :"


def test_metadata_everywhere(client: QBitFlow) -> None:
    bad = {"bad key": "x"}
    assert fields(
        lambda: client.customers.create(first_name="Ada", email="a@b.co", metadata=bad)
    ) == ["metadata"]
    assert fields(
        lambda: client.checkout_sessions.create_payment(product_uuid=MEMBER_UUID, metadata=bad)
    ) == ["metadata"]
    assert fields(
        lambda: client.checkout_sessions.create_subscription(product_uuid=MEMBER_UUID, metadata=bad)
    ) == ["metadata"]
    assert fields(lambda: client.products.update(MEMBER_UUID, metadata=bad)) == ["metadata"]
    assert fields(lambda: client.customers.update(MEMBER_UUID, metadata=bad)) == ["metadata"]
    assert fields(lambda: client.subscriptions.update("sub@" + MEMBER_UUID, metadata=bad)) == [
        "metadata"
    ]
    # An update's map is checked alone: deleting keys with "" is fine.
    assert fields(lambda: client.subscriptions.update(MEMBER_UUID, metadata={"old": ""})) == []
    assert fields(lambda: client.subscriptions.update(MEMBER_UUID)) == []


# ── Cursors and ids ──────────────────────────────────────────────────────────


def test_cursor(client: QBitFlow) -> None:
    assert fields(lambda: client.customers.list(cursor="c" * 200)) == []
    assert fields(lambda: client.customers.list(cursor="djF8MDFh")) == []
    assert fields(lambda: client.customers.list(cursor="c" * 201)) == ["cursor"]
    assert fields(lambda: client.customers.list(cursor=5)) == ["cursor"]
    assert fields(lambda: client.webhooks.events.list(cursor="e" * 201)) == ["cursor"]
    assert fields(lambda: client.products.list(cursor="p" * 201)) == ["cursor"]
    assert fields(lambda: client.subscriptions.list_bills(MEMBER_UUID, cursor="b" * 201)) == [
        "cursor"
    ]
    assert fields(lambda: client.webhooks.endpoints.list(cursor="e" * 201)) == ["cursor"]


MONTH = Duration(value=1, unit=DurationUnit.MONTHS)
DURATION_CASES: List[Tuple[str, SubscriptionTermsParams, List[str]]] = [
    ("monthly", SubscriptionTermsParams(frequency=MONTH), []),
    ("1 year", SubscriptionTermsParams(frequency=Duration(value=1, unit=DurationUnit.YEARS)), []),
    ("365 days", SubscriptionTermsParams(frequency=Duration(value=365, unit="days")), []),
    ("52 weeks", SubscriptionTermsParams(frequency=Duration(value=52, unit="weeks")), []),
    ("12 months", SubscriptionTermsParams(frequency=Duration(value=12, unit="months")), []),
    (
        "5 seconds (mode minimum is the API's)",
        SubscriptionTermsParams(frequency=Duration(value=5, unit="seconds")),
        [],
    ),
    (
        "13 months > 1 year",
        SubscriptionTermsParams(frequency=Duration(value=13, unit="months")),
        ["subscription.frequency"],
    ),
    (
        "2 years",
        SubscriptionTermsParams(frequency=Duration(value=2, unit="years")),
        ["subscription.frequency"],
    ),
    (
        "max uint32 years",
        SubscriptionTermsParams(frequency=Duration(value=4294967295, unit="years")),
        ["subscription.frequency"],
    ),
    (
        "over uint32",
        SubscriptionTermsParams(frequency=Duration(value=4294967296, unit="seconds")),
        ["subscription.frequency.value"],
    ),
    (
        "frequency 0",
        SubscriptionTermsParams(frequency=Duration(value=0, unit="days")),
        ["subscription.frequency.value"],
    ),
    (
        "no unit",
        SubscriptionTermsParams(frequency=Duration(value=3)),
        ["subscription.frequency.unit"],
    ),
    (
        "bad unit",
        SubscriptionTermsParams(frequency=Duration(value=1, unit="fortnights")),
        ["subscription.frequency.unit"],
    ),
    ("frequency required on create", SubscriptionTermsParams(), ["subscription.frequency"]),
    ("trial 0 without unit", SubscriptionTermsParams(frequency=MONTH, trial_period=Duration()), []),
    (
        "trial 14 days",
        SubscriptionTermsParams(frequency=MONTH, trial_period=Duration(value=14, unit="days")),
        [],
    ),
    (
        "trial no unit",
        SubscriptionTermsParams(frequency=MONTH, trial_period=Duration(value=14)),
        ["subscription.trialPeriod.unit"],
    ),
    (
        "trial 0 bad unit",
        SubscriptionTermsParams(frequency=MONTH, trial_period=Duration(value=0, unit="x")),
        ["subscription.trialPeriod.unit"],
    ),
    ("minPeriods 1000", SubscriptionTermsParams(frequency=MONTH, min_periods=1000), []),
    ("minPeriods 0", SubscriptionTermsParams(frequency=MONTH, min_periods=0), []),
    (
        "minPeriods 1001",
        SubscriptionTermsParams(frequency=MONTH, min_periods=1001),
        ["subscription.minPeriods"],
    ),
    ("not a Duration", SubscriptionTermsParams(frequency={"value": 1}), ["subscription.frequency"]),
]


@pytest.mark.parametrize("name, terms, want", DURATION_CASES, ids=[c[0] for c in DURATION_CASES])
def test_duration(
    client: QBitFlow, name: str, terms: SubscriptionTermsParams, want: List[str]
) -> None:
    assert (
        fields(lambda: client.products.create(name="Pro", price_usd="1", subscription=terms))
        == want
    )


def test_duration_on_sessions_and_updates(client: QBitFlow) -> None:
    assert (
        fields(lambda: client.checkout_sessions.create_subscription(product_uuid=MEMBER_UUID)) == []
    )
    got = fields(
        lambda: client.checkout_sessions.create_subscription(
            product_uuid=MEMBER_UUID, frequency=Duration(value=1), min_periods=2000
        )
    )
    assert got == ["frequency.unit", "minPeriods"]
    assert (
        fields(
            lambda: client.products.update(
                MEMBER_UUID, subscription=SubscriptionTermsParams(trial_period=Duration())
            )
        )
        == []
    )
    assert fields(
        lambda: client.products.create(name="Pro", price_usd="1", subscription={"frequency": MONTH})
    ) == ["subscription"]


SESSION_CASES: List[Tuple[str, dict, List[str]]] = [
    ("by uuid", {"product_uuid": MEMBER_UUID}, []),
    ("by reference", {"product_reference": "pro-plan"}, []),
    ("inline", {"product_name": "Pro", "price_usd": "10"}, []),
    ("inline Decimal", {"product_name": "Pro", "price_usd": Decimal("4.99")}, []),
    (
        "inline + description",
        {"product_name": "Pro", "price_usd": "10", "description": "Lifetime"},
        [],
    ),
    ("nothing", {}, ["productUuid"]),
    ("uuid + reference", {"product_uuid": MEMBER_UUID, "product_reference": "x"}, ["productUuid"]),
    (
        "uuid + inline",
        {"product_uuid": MEMBER_UUID, "product_name": "Pro", "price_usd": "1"},
        ["productUuid"],
    ),
    ("uuid + price", {"product_uuid": MEMBER_UUID, "price_usd": "1"}, ["productUuid"]),
    ("uuid + description", {"product_uuid": MEMBER_UUID, "description": "x y"}, ["productUuid"]),
    ("inline without price", {"product_name": "Pro"}, ["priceUsd"]),
    ("inline empty price", {"product_name": "Pro", "price_usd": ""}, ["priceUsd"]),
    ("inline without name", {"price_usd": "3"}, ["productName"]),
    ("inline negative price", {"product_name": "Pro", "price_usd": "-3"}, ["priceUsd"]),
    ("inline zero Decimal", {"product_name": "Pro", "price_usd": Decimal("0")}, ["priceUsd"]),
    ("inline float price", {"product_name": "Pro", "price_usd": 3.5}, ["priceUsd"]),
    ("bad uuid", {"product_uuid": "42"}, ["productUuid"]),
    ("bad customer uuid", {"product_uuid": MEMBER_UUID, "customer_uuid": "x"}, ["customerUuid"]),
    ("expires 10", {"product_uuid": MEMBER_UUID, "expires_in_minutes": 10}, []),
    ("expires 1440", {"product_uuid": MEMBER_UUID, "expires_in_minutes": 1440}, []),
    ("expires 0 is the default", {"product_uuid": MEMBER_UUID, "expires_in_minutes": 0}, []),
    ("expires 9", {"product_uuid": MEMBER_UUID, "expires_in_minutes": 9}, ["expiresInMinutes"]),
    (
        "expires 1441",
        {"product_uuid": MEMBER_UUID, "expires_in_minutes": 1441},
        ["expiresInMinutes"],
    ),
]


@pytest.mark.parametrize("name, kwargs, want", SESSION_CASES, ids=[c[0] for c in SESSION_CASES])
def test_session(client: QBitFlow, name: str, kwargs: dict, want: List[str]) -> None:
    assert fields(lambda: client.checkout_sessions.create_payment(**kwargs)) == want


def test_subscription_session(client: QBitFlow) -> None:
    month = Duration(value=1, unit="months")
    assert (
        fields(
            lambda: client.checkout_sessions.create_subscription(
                product_name="Pro", price_usd="9.99", frequency=month
            )
        )
        == []
    )
    assert fields(
        lambda: client.checkout_sessions.create_subscription(
            product_reference="pro", price_usd="9.99"
        )
    ) == ["productUuid"]


# ── Checkout fees (fees.items[i].label / description / amountUsd, fees.items) ──


def fee_fields(client: QBitFlow, fees: Any) -> List[str]:
    return fields(
        lambda: client.checkout_sessions.create_payment(
            product_name="T-shirt", price_usd="3.99", fees=fees
        )
    )


def one(label: Any = "Shipping", amount: Any = "0.75", description: Any = None) -> CheckoutFees:
    return CheckoutFees(items=[FeeItem(label=label, amount_usd=amount, description=description)])


AMOUNT = "fees.items[0].amountUsd"
GOOD_AMOUNTS: List[Any] = [
    "0.01",
    "0.75",
    "4.99",
    "19.9",
    "100.00",
    "1000000",
    "1000000.00",
    "007.5",
    Decimal("4.99"),
    Decimal("1000000"),
]
BAD_AMOUNTS: List[Any] = [
    0.01,
    0.75,
    1,
    1000000,
    True,
    None,
    "0",
    "0.00",
    "-1",
    "+1",
    "1e2",
    "abc",
    "",
    " 4.99",
    "4.99 ",
    "4.",
    ".5",
    "1.999",
    "1,5",
    "1000000.01",
    "NaN",
    "Infinity",
    "٤",  # an Arabic-Indic digit: not [0-9]
    Decimal("1.999"),
    Decimal("4.990"),
    Decimal("1E+2"),
    Decimal("-1"),
    Decimal("NaN"),
    [1],
]


@pytest.mark.parametrize("amount", GOOD_AMOUNTS, ids=repr)
def test_fee_amount_good(client: QBitFlow, amount: Any) -> None:
    assert fee_fields(client, one(amount=amount)) == []


@pytest.mark.parametrize("amount", BAD_AMOUNTS, ids=repr)
def test_fee_amount_bad(client: QBitFlow, amount: Any) -> None:
    assert fee_fields(client, one(amount=amount)) == [AMOUNT]


def test_fee_amount_message(client: QBitFlow) -> None:
    with pytest.raises(ValidationError) as info:
        client.checkout_sessions.create_payment(product_uuid=MEMBER_UUID, fees=one(amount="1e2"))
    assert info.value.field_errors[0].message == (
        'fees.items[0].amountUsd must be an amount in USD as a decimal string (e.g. "12.50"): '
        "above 0, at most 1000000, with at most 2 decimals"
    )
    with pytest.raises(ValidationError) as info:
        client.checkout_sessions.create_payment(product_uuid=MEMBER_UUID, fees=one(amount=0.75))
    assert "not a number" in info.value.field_errors[0].message


@pytest.mark.parametrize("label", ["a", "VAT (20%)", "Shipping", "é" * 40, "Zoë & Co"])
def test_fee_label_good(client: QBitFlow, label: str) -> None:
    assert fee_fields(client, one(label=label)) == []


@pytest.mark.parametrize(
    "label", ["", None, 42, "é" * 41] + [n for n in BAD_NAMES if n != "a"], ids=repr
)
def test_fee_label_bad(client: QBitFlow, label: Any) -> None:
    assert fee_fields(client, one(label=label)) == ["fees.items[0].label"]


@pytest.mark.parametrize(
    "description", [None, "", "x", "Standard, 3 to 5 days", "Two\nlines\tand tab", "é" * 200]
)
def test_fee_description_good(client: QBitFlow, description: Any) -> None:
    assert fee_fields(client, one(description=description)) == []


@pytest.mark.parametrize(
    "description", ["é" * 201, "  ", "<b>", "semi;colon", "nul\x00x", 7], ids=repr
)
def test_fee_description_bad(client: QBitFlow, description: Any) -> None:
    assert fee_fields(client, one(description=description)) == ["fees.items[0].description"]


def test_fee_items_count(client: QBitFlow) -> None:
    ten = [FeeItem(f"Line {i}", "1") for i in range(10)]
    assert fee_fields(client, CheckoutFees(items=ten)) == []
    eleven = ten + [FeeItem("Line 10", "1")]
    assert fee_fields(client, CheckoutFees(items=eleven)) == ["fees.items"]
    assert fee_fields(client, CheckoutFees(items=[])) == []


def test_fee_paths_and_types(client: QBitFlow) -> None:
    fees = CheckoutFees(
        items=[
            FeeItem("Shipping", "0.75"),
            FeeItem("", "0", "<x>"),
            FeeItem("VAT", "1e2"),
        ]
    )
    assert fee_fields(client, fees) == [
        "fees.items[1].label",
        "fees.items[1].description",
        "fees.items[1].amountUsd",
        "fees.items[2].amountUsd",
    ]
    assert fee_fields(client, CheckoutFees(processing_fee=True)) == []
    assert fee_fields(client, CheckoutFees(processing_fee=False)) == []
    assert fee_fields(client, CheckoutFees(processing_fee="yes")) == [  # type: ignore[arg-type]
        "fees.processingFee"
    ]
    assert fee_fields(client, {"processingFee": True}) == ["fees"]
    assert fee_fields(client, CheckoutFees(items="Shipping")) == [  # type: ignore[arg-type]
        "fees.items"
    ]
    assert fee_fields(client, CheckoutFees(items=[{"label": "x"}])) == [  # type: ignore[list-item]
        "fees.items[0]"
    ]
    assert fee_fields(client, None) == []


def test_fees_reported_last(client: QBitFlow) -> None:
    got = fields(
        lambda: client.checkout_sessions.create_payment(
            product_name="Pro",
            price_usd="0",
            reference="a b",
            metadata={"x": "\x00"},
            fees=one(amount="0"),
        )
    )
    assert got == ["reference", "metadata.x", "priceUsd", AMOUNT]


def sub_fee_fields(client: QBitFlow, fees: Any, **kwargs: Any) -> List[str]:
    return fields(
        lambda: client.checkout_sessions.create_subscription(
            product_uuid=MEMBER_UUID, fees=fees, **kwargs
        )
    )


def test_subscription_fees(client: QBitFlow) -> None:
    # A subscription checkout's fees follow the same rules, reported after the terms.
    ten = [FeeItem(f"Line {i}", "1") for i in range(10)]
    assert sub_fee_fields(client, None) == []
    assert sub_fee_fields(client, CheckoutFees(processing_fee=True)) == []
    assert sub_fee_fields(client, CheckoutFees(processing_fee=False, items=ten)) == []
    eleven = ten + [FeeItem("Line 10", "1")]
    assert sub_fee_fields(client, CheckoutFees(items=eleven)) == ["fees.items"]
    bad = CheckoutFees(items=[FeeItem("a|b", "0.001", " ")])
    assert sub_fee_fields(client, bad) == [
        "fees.items[0].label",
        "fees.items[0].description",
        "fees.items[0].amountUsd",
    ]
    assert sub_fee_fields(
        client, CheckoutFees(items=[FeeItem("Tax", "-1")]), frequency=Duration(value=1)
    ) == ["frequency.unit", "fees.items[0].amountUsd"]


def test_ids() -> None:
    prefixes = ("pay", "sub", "payg", "sub-hist", "refund", "transfer", "release")
    for good in (
        MEMBER_UUID,
        "019ECA82-5680-7B00-8000-0000000000B1",
        *(p + "@" + MEMBER_UUID for p in prefixes),
    ):
        assert is_tx_id(good), good
    for bad in (
        "",
        "pay@",
        "pay@x",
        "evt@" + MEMBER_UUID,
        "releases@" + MEMBER_UUID,
        "@" + MEMBER_UUID,
        "PAY@" + MEMBER_UUID,
        MEMBER_UUID + "0",
        "42",
        None,
        5,
    ):
        assert not is_tx_id(bad), bad
    check_path_uuid("uuid", MEMBER_UUID)
    check_path_uuid("uuid", "00000000-0000-0000-0000-000000000000")  # the server answers 404
    for bad_uuid in ("", "pay@" + MEMBER_UUID, None):
        with pytest.raises(ValidationError):
            check_path_uuid("uuid", bad_uuid)
    check_path_tx_id("uuid", "sub@" + MEMBER_UUID)
    check_path_tx_id("uuid", "release@" + MEMBER_UUID)
    for bad_tx in ("", "x"):
        with pytest.raises(ValidationError):
            check_path_tx_id("uuid", bad_tx)
    check_path_required("id", "evt_a/b")
    for bad_id in (" ", ".", ".."):
        with pytest.raises(ValidationError):
            check_path_required("id", bad_id)


def test_tx_id_params(client: QBitFlow) -> None:
    assert fields(lambda: client.refunds.list(tx_uuid="order-1")) == ["txUuid"]
    assert fields(lambda: client.refunds.list(tx_uuid="release@" + MEMBER_UUID)) == []
    assert fields(lambda: client.failures.list(subscription_uuid="sub@nope")) == [
        "subscriptionUuid"
    ]
    assert fields(lambda: client.transactions.list(subscription_uuid="sub@nope")) == [
        "subscriptionUuid"
    ]
    assert fields(lambda: client.refunds.list(tx_uuid="x")) == ["txUuid"]
    assert fields(lambda: client.refunds.get("refund@nope")) == ["uuid"]


def test_filters(client: QBitFlow) -> None:
    assert fields(lambda: client.payments.list(include_members=True, user_uuid=MEMBER_UUID)) == [
        "userUuid"
    ]
    assert fields(lambda: client.payments.list(user_uuid=MEMBER_UUID)) == []
    assert fields(
        lambda: client.subscriptions.list(customer_uuid="x", product_uuid="y", user_uuid="z")
    ) == ["customerUuid", "productUuid", "userUuid"]
    # Subscription statuses and event types are not checked: newer values may appear.
    assert fields(lambda: client.subscriptions.list(status="hibernating")) == []
    assert fields(lambda: client.subscriptions.list(status="cancelled")) == []
    assert fields(lambda: client.webhooks.events.list(type="payment.done")) == []
    assert fields(lambda: client.webhooks.events.list(type=EventType.WEBHOOK_TEST)) == []
    # The transactions feed's type is: payment or bill.
    assert fields(lambda: client.transactions.list(type="bill")) == []
    assert fields(lambda: client.transactions.list(type=TransactionKind.PAYMENT)) == []
    assert fields(lambda: client.transactions.list(type="subscriptionHistory")) == ["type"]
    assert fields(
        lambda: client.transactions.list(include_members=True, user_uuid=MEMBER_UUID)
    ) == ["userUuid"]
    assert fields(lambda: client.failures.list(kind="refund", category="boom")) == [
        "kind",
        "category",
    ]
    assert fields(lambda: client.invitations.list(status="open")) == ["status"]
    assert fields(lambda: client.refunds.list(include_members=True, user_uuid=MEMBER_UUID)) == [
        "userUuid"
    ]
    assert fields(lambda: client.refunds.list(include_members=False, user_uuid=MEMBER_UUID)) == []
    assert fields(lambda: client.wallets.list_accepted_currencies(user_uuid="x")) == ["userUuid"]
    assert fields(lambda: client.customers.list(limit=2.5)) == ["limit"]
    assert fields(lambda: client.customers.list(verified="yes")) == ["verified"]
    assert fields(lambda: client.products.list(include_hidden="yes")) == ["includeHidden"]
    assert fields(lambda: client.currencies.list(main="yes")) == ["main"]


@pytest.mark.parametrize(
    "status, want",
    [
        (None, []),
        ([], []),
        (["pending"], []),
        ([RefundStatus.REJECTED, RefundStatus.FAILED], []),
        (["pending", "approved", "rejected", "failed", "pending"], []),  # duplicates allowed
        (["approved", "cancelled"], ["status[1]"]),  # no longer a refund status
        (["pending"] * 6, ["status"]),
        (["pending", "", "nope"], ["status[1]", "status[2]"]),
        (["completed"], ["status[0]"]),  # the retired refund.completed is no status
        ([None], ["status[0]"]),
        ("pending", ["status"]),
    ],
    ids=repr,
)
def test_refund_status_filter(client: QBitFlow, status: Any, want: List[str]) -> None:
    assert fields(lambda: client.refunds.list(status=status)) == want


@pytest.mark.parametrize(
    "start, end, ok",
    [
        ("2026-06-01", "2026-06-01", True),
        ("2024-02-29", "2026-12-31", True),  # no window check (the API's: 92 days)
        ("2026-06-02", "2026-06-01", False),
        ("2026-13-01", "2026-12-01", False),
        ("2025-02-29", "2025-03-01", False),
        ("26-01-01", "2026-01-01", False),
        ("2026-1-1", "2026-01-02", False),
    ],
)
def test_dates(start: str, end: str, ok: bool) -> None:
    v = Validator()
    v.date_range("from", start, "to", end)
    assert (v.error() is None) is ok


def test_date_objects(client: QBitFlow) -> None:
    from datetime import date

    assert fields(lambda: client.accounting.export_json(date(2026, 9, 1), date(2026, 9, 30))) == []
    assert fields(lambda: client.accounting.export_json(date(2026, 9, 30), "2026-09-01")) == ["to"]


def test_endpoint_events(client: QBitFlow) -> None:
    twenty = [EventType.PAYMENT_COMPLETED] * 20
    assert fields(lambda: client.webhooks.endpoints.create(url="https://x.io", events=twenty)) == []
    assert fields(
        lambda: client.webhooks.endpoints.create(
            url="https://x.io", events=twenty + ["refund.rejected"]
        )
    ) == ["events"]
    assert fields(
        lambda: client.webhooks.endpoints.create(
            url="https://x.io", events=["refund.approved", "webhook.test"]
        )
    ) == ["events[1]"]
    assert fields(
        lambda: client.webhooks.endpoints.update(MEMBER_UUID, events=[EventType.WEBHOOK_TEST])
    ) == ["events[0]"]
    assert (
        fields(
            lambda: client.webhooks.endpoints.create(url="https://x.io", events=["future.event"])
        )
        == []
    )
    assert fields(lambda: client.webhooks.endpoints.create(url="https://x.io", events=[""])) == [
        "events[0]"
    ]
    assert fields(lambda: client.webhooks.endpoints.update(MEMBER_UUID, payload_version="v1")) == [
        "payloadVersion"
    ]
    assert fields(lambda: client.webhooks.endpoints.update(MEMBER_UUID, payload_version="v2")) == []


def test_invitation_hold_funds(client: QBitFlow) -> None:
    assert fields(lambda: client.invitations.create(email="a@b.co", hold_funds=False)) == []
    assert fields(lambda: client.invitations.create(email="a@b.co", hold_funds=True)) == []
    assert fields(lambda: client.invitations.create(email="a@b.co", hold_funds=None)) == [
        "holdFunds"
    ]
    assert fields(lambda: client.invitations.create(email="a@b.co", hold_funds="yes")) == [
        "holdFunds"
    ]
    assert fields(lambda: client.invitations.create(email=None, hold_funds=None)) == [
        "email",
        "holdFunds",
    ]


def test_headers_rules() -> None:
    for key in ("a", "order-1042", "~!@#$%^&*()_+{}|:<>?", "k" * 255):
        assert is_idempotency_key(key)
    for key in ("", "a b", "tab\t", "é", "del\x7f", "k" * 256):
        assert not is_idempotency_key(key)
    for rid in ("a", "sdk-probe.123:abc", "A_b-C.d:E", "r" * 128):
        assert is_request_id(rid)
    for rid in ("", "a b", "a/b", "a@b", "r" * 129):
        assert not is_request_id(rid)


SUB = "sub@" + MEMBER_UUID
UPDATE_CASES: List[Tuple[str, Callable[[QBitFlow], Any], dict]] = [
    ("customer nothing", lambda c: c.customers.update(MEMBER_UUID), {}),
    (
        "customer clears",
        lambda c: c.customers.update(MEMBER_UUID, last_name="", phone_number="", address=""),
        {"lastName": "", "phoneNumber": "", "address": ""},
    ),
    (
        "customer clears with None",
        lambda c: c.customers.update(MEMBER_UUID, phone_number=None, last_name=None),
        {"phoneNumber": "", "lastName": ""},
    ),
    ("customer NOT_GIVEN", lambda c: c.customers.update(MEMBER_UUID, phone_number=NOT_GIVEN), {}),
    (
        "customer sets",
        lambda c: c.customers.update(
            MEMBER_UUID, first_name="Ada", last_name="L", phone_number="+33 6 12 34 56 78"
        ),
        {"firstName": "Ada", "lastName": "L", "phoneNumber": "+33 6 12 34 56 78"},
    ),
    (
        "customer first name '' is unchanged",
        lambda c: c.customers.update(MEMBER_UUID, first_name=""),
        {},
    ),
    (
        "customer metadata merge",
        lambda c: c.customers.update(MEMBER_UUID, metadata={"crm": "C-2", "old": ""}),
        {"metadata": {"crm": "C-2", "old": ""}},
    ),
    ("customer empty metadata omitted", lambda c: c.customers.update(MEMBER_UUID, metadata={}), {}),
    ("product nothing", lambda c: c.products.update(MEMBER_UUID), {}),
    (
        "product clears description",
        lambda c: c.products.update(MEMBER_UUID, description=""),
        {"description": ""},
    ),
    (
        "product sets",
        lambda c: c.products.update(
            MEMBER_UUID, price_usd="9.99", is_active=False, remove_subscription=True
        ),
        {"priceUsd": "9.99", "isActive": False, "removeSubscription": True},
    ),
    (
        "product Decimal price",
        lambda c: c.products.update(MEMBER_UUID, price_usd=Decimal("12.50")),
        {"priceUsd": "12.50"},
    ),
    ("product empty price unchanged", lambda c: c.products.update(MEMBER_UUID, price_usd=""), {}),
    (
        "product metadata merge",
        lambda c: c.products.update(MEMBER_UUID, metadata={"sku": "PRO-M2", "legacy": ""}),
        {"metadata": {"sku": "PRO-M2", "legacy": ""}},
    ),
    ("subscription nothing", lambda c: c.subscriptions.update(SUB), {}),
    (
        "subscription metadata merge",
        lambda c: c.subscriptions.update(SUB, metadata={"plan": "pro-annual", "coupon": ""}),
        {"metadata": {"plan": "pro-annual", "coupon": ""}},
    ),
    ("endpoint nothing", lambda c: c.webhooks.endpoints.update(MEMBER_UUID), {}),
    (
        "endpoint clears",
        lambda c: c.webhooks.endpoints.update(MEMBER_UUID, description="", events=[]),
        {"events": [], "description": ""},
    ),
    (
        "endpoint sets",
        lambda c: c.webhooks.endpoints.update(MEMBER_UUID, enabled=False, payload_version="v2"),
        {"payloadVersion": "v2", "enabled": False},
    ),
    (
        "member fee 0",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent="0"),
        {"organizationFeePercent": "0"},
    ),
    (
        "member fee Decimal",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent=Decimal("7.50")),
        {"organizationFeePercent": "7.50"},
    ),
    (
        "invitation minimal",
        lambda c: c.invitations.create(email="a@b.co", hold_funds=False),
        {"email": "a@b.co", "role": "user", "holdFunds": False},
    ),
    (
        "invitation full",
        lambda c: c.invitations.create(
            email="a@b.co",
            hold_funds=True,
            organization_fee_percent="2.5",
            redirect_url="https://x.io",
        ),
        {
            "email": "a@b.co",
            "role": "user",
            "holdFunds": True,
            "organizationFeePercent": "2.5",
            "redirectUrl": "https://x.io",
        },
    ),
    (
        "product create minimal",
        lambda c: c.products.create(name="Pro", price_usd="10"),
        {"name": "Pro", "priceUsd": "10"},
    ),
    (
        "product create Decimal and metadata",
        lambda c: c.products.create(
            name="Pro", price_usd=Decimal("10.00"), metadata={"sku": "PRO", "skip": ""}
        ),
        {"name": "Pro", "priceUsd": "10.00", "metadata": {"sku": "PRO", "skip": ""}},
    ),
    (
        "product create empty metadata omitted",
        lambda c: c.products.create(name="Pro", price_usd="10", metadata={}),
        {"name": "Pro", "priceUsd": "10"},
    ),
    (
        "product create terms",
        lambda c: c.products.create(
            name="Pro",
            price_usd="10",
            subscription=SubscriptionTermsParams(
                frequency=Duration(value=1, unit="months"), trial_period=Duration(), min_periods=0
            ),
        ),
        {
            "name": "Pro",
            "priceUsd": "10",
            "subscription": {
                "frequency": {"value": 1, "unit": "months"},
                "trialPeriod": {"value": 0},
                "minPeriods": 0,
            },
        },
    ),
    (
        "customer create",
        lambda c: c.customers.create(
            first_name="Ada", email="a@b.co", reference="crm-1", metadata={"crm": "1"}
        ),
        {"firstName": "Ada", "email": "a@b.co", "reference": "crm-1", "metadata": {"crm": "1"}},
    ),
    (
        "session by uuid",
        lambda c: c.checkout_sessions.create_payment(product_uuid=MEMBER_UUID),
        {"productUuid": MEMBER_UUID},
    ),
    (
        "session inline Decimal with metadata",
        lambda c: c.checkout_sessions.create_payment(
            product_name="T-shirt", price_usd=Decimal("4.99"), metadata={"orderId": "order-1042"}
        ),
        {"productName": "T-shirt", "priceUsd": "4.99", "metadata": {"orderId": "order-1042"}},
    ),
    (
        "subscription session",
        lambda c: c.checkout_sessions.create_subscription(
            product_name="Pro",
            price_usd="9.99",
            frequency=Duration(value=1, unit="weeks"),
            expires_in_minutes=30,
        ),
        {
            "productName": "Pro",
            "priceUsd": "9.99",
            "expiresInMinutes": 30,
            "frequency": {"value": 1, "unit": "weeks"},
        },
    ),
    (
        "endpoint create",
        lambda c: c.webhooks.endpoints.create(url="https://x.io", include_members=False),
        {"url": "https://x.io", "includeMembers": False},
    ),
    (
        "endpoint create empty events",
        lambda c: c.webhooks.endpoints.create(url="https://x.io", events=[]),
        {"url": "https://x.io"},
    ),
]


@pytest.mark.parametrize("name, call, body", UPDATE_CASES, ids=[c[0] for c in UPDATE_CASES])
def test_update_semantics_and_bodies(
    name: str, call: Callable[[QBitFlow], Any], body: dict
) -> None:
    client, server, _ = make_client(static(200, "{}"))
    try:
        call(client)
    except ServerError:  # pragma: no cover - every call here answers an object
        pass
    assert server.requests[0].json() == body
    # Money is a JSON string on the wire, never a number.
    raw = server.requests[0].body.decode()
    for key in ("priceUsd", "refundPercent", "organizationFeePercent"):
        if key in body:
            assert f'"{key}":"' in raw


def test_update_validation(client: QBitFlow) -> None:
    assert fields(lambda: client.customers.update(MEMBER_UUID, phone_number="", address="")) == []
    assert fields(lambda: client.customers.update(MEMBER_UUID, last_name="")) == []
    assert fields(lambda: client.customers.update(MEMBER_UUID, last_name="a\nb")) == ["lastName"]
    assert fields(lambda: client.customers.update(MEMBER_UUID, phone_number="abc")) == [
        "phoneNumber"
    ]
    assert fields(lambda: client.customers.update(MEMBER_UUID, address="   ")) == ["address"]
    assert fields(lambda: client.products.update(MEMBER_UUID, description="")) == []
    assert fields(lambda: client.products.update(MEMBER_UUID, description="x")) == ["description"]
    assert fields(
        lambda: client.products.update(
            MEMBER_UUID, remove_subscription=True, subscription=SubscriptionTermsParams()
        )
    ) == ["removeSubscription"]
    assert fields(lambda: client.webhooks.endpoints.update(MEMBER_UUID, description="")) == []


def test_collects_all_fields(client: QBitFlow) -> None:
    with pytest.raises(ValidationError) as info:
        client.customers.create(
            first_name="x",
            last_name="<",
            email="nope",
            phone_number="1",
            address=" ",
            reference="a b",
            metadata={"k": "\x00"},
        )
    assert [f.field for f in info.value.field_errors] == [
        "firstName",
        "lastName",
        "email",
        "phoneNumber",
        "address",
        "reference",
        "metadata.k",
    ]
    assert str(info.value).startswith(
        "validation failed; firstName: firstName must be 2 to 100 characters"
    )


def test_duration_unit_type_checked() -> None:
    with pytest.raises(Exception):
        Duration(value=-1)
