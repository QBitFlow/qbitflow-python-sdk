"""
Offline tests that every DTO survives the responses the API actually sends.

Each case here corresponds to a field the API documents as `omitempty`, as a pointer, or as
``resource:"whenAuth"`` — i.e. a field that is legitimately absent from a real payload. The
SDK previously declared several of them required, so pydantic raised ``ValidationError`` on
ordinary responses and the affected methods could never succeed.

The payloads are deliberately *minimal*: they contain only what the API guarantees, so a
field drifting back to required fails here rather than in a user's process.

Run with:
    pytest tests/test_dto_optionality.py -v
"""

import pytest

from qbitflow.dto.api_key import ApiKey
from qbitflow.dto.transaction.payment import CombinedPaymentItem, Payment
from qbitflow.dto.transaction.refund import RefundEntry
from qbitflow.dto.transaction.session import OneTimePaymentSession
from qbitflow.dto.transaction.status import TransactionStatus
from qbitflow.dto.transaction.subscription import SubscriptionHistory
from qbitflow.dto.user import CreateUserDto, User, UserRole
from qbitflow.utils.helpers import validate_url

CURRENCY = {
    "id": 7,
    "symbol": "USDC",
    "name": "USD Coin",
    "decimals": 6,
    "address": "",
    "test": False,
}

TRANSFER = {
    "createdAt": "2026-01-01T00:00:00Z",
    "from": "addr-a",
    "to": "addr-b",
    "amount": 9.99,
    "amountMinUnits": "9990000",
    "currencyId": 7,
    "currency": CURRENCY,
    "test": False,
    "transactionHash": "hash",
}


# ── Roles ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["handle", "user", "admin", "owner"])
def test_every_role_the_api_can_return_deserializes(role):
    """
    The hierarchy is ``handle < user < admin < owner`` (docs README §1). `handle` and
    `owner` were both missing from the enum, so a real user carrying either could not be
    deserialized at all.
    """
    user = User(
        id=1,
        name="N",
        lastName="L",
        email="e@example.com",
        createdAt="2026-01-01T00:00:00Z",
        updatedAt="2026-01-01T00:00:00Z",
        organizationId=1,
        organizationFeeBps=0,
        role=role,
    )

    assert user.role.value == role


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_create_user_accepts_the_assignable_roles(role):
    assert CreateUserDto(name="Jane", lastName="Smith", email="j@x.com", role=role).role is role


@pytest.mark.parametrize("role", [UserRole.OWNER, UserRole.HANDLE])
def test_create_user_rejects_the_read_only_roles(role):
    """The API binds this `oneof=admin user`, so these are a guaranteed 400."""
    with pytest.raises(ValueError, match="admin"):
        CreateUserDto(name="Jane", lastName="Smith", email="j@x.com", role=role)


# ── Fields the API omits ─────────────────────────────────────────────────────


def test_org_level_api_key_has_no_user_id():
    """`userId` is `omitempty` and org-level keys carry 0, so the key is dropped."""
    key = ApiKey(
        id=1,
        name="org key",
        organizationId=7,
        createdAt="2026-01-01T00:00:00Z",
        role="admin",
        test=False,
    )

    assert key.user_id == 0


def test_refund_on_the_public_route_has_no_ownership_fields():
    """`organizationId`/`userId` are `whenAuth`; the by-transaction route is public."""
    refund = RefundEntry(
        uuid="ref@1",
        txId="pay@1",
        test=False,
        reason="damaged",
        status="refused",
        createdAt="2026-01-01T00:00:00Z",
    )

    assert refund.organization_id is None
    assert refund.user_id is None


def test_status_before_the_transaction_is_broadcast_has_no_hash():
    """`txHash` is `omitempty` — absent for created/waitingConfirmation/pending, i.e. the
    first status read of every transaction, which is exactly the polling case."""
    status = TransactionStatus(status="created")

    assert status.tx_hash is None


def test_payment_without_a_linked_customer():
    payment = Payment(uuid="pay@1", name="n", description="d", productId=1, **TRANSFER)

    assert payment.customer_uuid is None


def test_public_subscription_history_has_no_customer():
    """The history route is unauthenticated, so `whenAuth` strips customerUUID."""
    entry = SubscriptionHistory(
        uuid="sub-hist@1",
        name="n",
        description="d",
        productId=1,
        subscriptionUUID="sub@1",
        **TRANSFER,
    )

    assert entry.customer_uuid is None


def test_zero_price_session_omits_the_product_fields():
    """`price` is a float with `omitempty`, so a $0 product serializes without the key."""
    session = OneTimePaymentSession(
        uuid="pay@1",
        organizationName="Org",
        test=False,
        availableCurrencies=[1],
        txType="payment",
    )

    assert session.price is None
    assert session.product_name is None


def test_combined_payment_customer_uuid_stays_required():
    """
    Guards against over-correcting: unlike Payment, CombinedPaymentItem.customerUUID is a
    non-pointer field with no omitempty, and is present on the wire. It must NOT be
    loosened along with the others.
    """
    with pytest.raises(Exception):
        CombinedPaymentItem(
            uuid="pay@1",
            source="payment",
            name="n",
            description="d",
            createdAt="2026-01-01T00:00:00Z",
            **{"from": "a"},
            to="b",
            amount=1.0,
            amountMinUnits="",
            currencyId=7,
            test=False,
            transactionHash="h",
        )


# ── URL validation matches the API's http_url rule ───────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/ok",
        # Rejected by the old regex: TLD longer than 6 characters.
        "https://shop.example.technology/ok",
        # Rejected by the old regex: no dot in the host (internal service).
        "https://checkout-web/success",
        "http://localhost:3000/x",
        "https://192.168.1.10:8443/cb",
    ],
)
def test_urls_the_api_accepts(url):
    assert validate_url(url) is True


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "not a url", "/relative/path", "", "ftp://x/y"]
)
def test_urls_the_api_rejects(url):
    assert validate_url(url) is False
