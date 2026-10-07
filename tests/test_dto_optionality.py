"""
Offline tests of how DTOs decode API responses and validate request data.

Response models follow the Go server's ``encoding/json`` semantics:

* a non-pointer field that is **absent or null** decodes to its zero value (``0``, ``""``,
  ``False``, ``[]``, a zero-valued nested object, the Go zero time) — never ``None``, never an
  error;
* a pointer field is ``Optional`` and decodes to ``None``;
* a field of the **wrong JSON type** fails validation (the request layer turns that into a
  ``ServerError``, see ``tests/test_transport.py``);
* unknown enum values are kept as plain strings.

Request DTOs raise the SDK's ``ValidationError`` — never pydantic's — for every rule the API
enforces.

Run with:
    pytest tests/test_dto_optionality.py -v
"""

import inspect
from datetime import datetime, timezone

import pydantic
import pytest

import qbitflow.dto as dto_package
import qbitflow.dto.transaction as tx_package
from qbitflow import GO_ZERO_TIME
from qbitflow.dto.accounting import ACCOUNTING_EVENT_TYPES, AccountingEvent
from qbitflow.dto.api_key import ApiKey
from qbitflow.dto.base_model import ResponseModel
from qbitflow.dto.claim import ClaimFund
from qbitflow.dto.customer import CreateCustomerDto, Customer, UpdateCustomerDto
from qbitflow.dto.product import CreateProductDto, Product, UpdateProductDto
from qbitflow.dto.transaction.currency import Currency
from qbitflow.dto.transaction.metadata import OrganizationFee, PaymentMetadata, ReferralFee
from qbitflow.dto.transaction.payment import CombinedPaymentItem, Payment
from qbitflow.dto.transaction.refund import RefundEntry, RefundStatus
from qbitflow.dto.transaction.session import (
    OneTimePaymentSession,
    SessionWebhookResponse,
    SubscriptionSession,
    _discriminate_session,
)
from qbitflow.dto.transaction.status import TransactionStatus, TransactionStatusValue
from qbitflow.dto.transaction.subscription import (
    Subscription,
    SubscriptionHistory,
    SubscriptionStatus,
    SubscriptionStatusTransition,
    SubscriptionWebhook,
    SubscriptionWebhookType,
)
from qbitflow.dto.user import CreateUserDto, UpdateUserDto, User, UserRole
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import SuccessResponse
from qbitflow.utils.cursor_data import CursorData
from qbitflow.utils.helpers import validate_url

CURRENCY = {
    "id": 7,
    "symbol": "USDC",
    "name": "USD Coin",
    "decimals": 6,
    "address": "0xa0b8",
    "mainCurrencyId": 1,
    "mainCurrency": {
        "id": 1,
        "symbol": "ETH",
        "name": "Ethereum",
        "decimals": 18,
        "address": "",
        "mainCurrency": None,
        "test": False,
    },
    "test": False,
}


def _response_models():
    """Every ResponseModel subclass the SDK exposes."""
    seen = set()
    for module in (dto_package, tx_package):
        for obj in vars(module).values():
            if inspect.isclass(obj) and issubclass(obj, ResponseModel) and obj is not ResponseModel:
                seen.add(obj)
    seen.update({SuccessResponse, SubscriptionStatusTransition, CursorData[Customer, str]})
    return sorted(seen, key=lambda cls: cls.__name__)


RESPONSE_MODELS = _response_models()


# ── The decoding policy, for every response model ────────────────────────────


@pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
def test_an_empty_object_decodes_to_zero_values(model):
    """Absent non-pointer fields decode to their zero value (Go's encoding/json)."""
    instance = model.model_validate({})

    for name, field in model.model_fields.items():
        value = getattr(instance, name)
        assert value is not ... and not isinstance(value, pydantic.fields.FieldInfo), name


@pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
def test_null_for_every_field_decodes_like_absence(model):
    """`null` for a non-pointer field is its zero value; for a pointer field it is None."""
    data = {(field.alias or name): None for name, field in model.model_fields.items()}

    assert model.model_validate(data) == model.model_validate({})


@pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
def test_unknown_keys_are_ignored(model):
    assert model.model_validate({"someFieldAddedLater": {"x": [1]}}) == model.model_validate({})


def test_zero_values_are_the_go_zero_values():
    payment = Payment.model_validate({})

    assert payment.uuid == "" and payment.amount == 0.0 and payment.product_id == 0
    assert payment.test is False
    assert payment.created_at == GO_ZERO_TIME == datetime(1, 1, 1, tzinfo=timezone.utc)
    assert isinstance(payment.currency, Currency) and payment.currency.id == 0
    assert isinstance(payment.metadata, PaymentMetadata)
    assert payment.metadata.tx_amounts.usd.organization == 0.0
    assert payment.metadata.organization_fee is None, "a pointer stays None"
    assert payment.customer_uuid is None and payment.reference is None


def test_go_zero_time_on_the_wire_parses():
    sub = Subscription.model_validate({"lastBillingDate": "0001-01-01T00:00:00Z"})

    assert sub.last_billing_date == GO_ZERO_TIME


def test_nanosecond_timestamps_parse():
    user = User.model_validate({"createdAt": "2026-09-23T10:11:12.123456789+02:00"})

    assert user.created_at.microsecond == 123456


# ── Wrong JSON types are shape failures ──────────────────────────────────────


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (Product, {"id": "1"}),
        (Product, {"id": True}),
        (Product, {"id": 1.5}),
        (Product, {"price": "9.99"}),
        (Product, {"price": False}),
        (Product, {"name": 5}),
        (Product, {"isActive": "true"}),
        (Product, {"isActive": 1}),
        (Product, {"createdAt": 1700000000}),
        (Product, {"createdAt": "not a date"}),
        (Payment, {"currency": "USDC"}),
        (Payment, {"metadata": []}),
        (Payment, {"amountMinUnits": 1000}),
        (OneTimePaymentSession, {"availableCurrencies": {"a": 1}}),
        (OneTimePaymentSession, {"availableCurrencies": ["1"]}),
        (Subscription, {"allowance": 10}),
        (RefundEntry, {"status": 3}),
        (CursorData[Customer, str], {"items": "nope"}),
        (CursorData[Customer, str], {"nextCursor": 5}),
    ],
)
def test_a_present_field_of_the_wrong_type_fails(model, payload):
    with pytest.raises(pydantic.ValidationError):
        model.model_validate(payload)


def test_harmless_numeric_widening_is_accepted():
    product = Product.model_validate({"id": 3.0, "price": 10})

    assert product.id == 3 and isinstance(product.id, int)
    assert product.price == 10.0 and isinstance(product.price, float)


def test_wrong_types_fail_in_json_mode_too():
    with pytest.raises(pydantic.ValidationError):
        Product.model_validate_json('{"id":"1"}')
    assert Product.model_validate_json('{"id":1,"createdAt":null}').created_at == GO_ZERO_TIME


def test_response_values_are_never_rejected_for_their_range():
    """No ge/gt constraints on responses: the server's values are reported as they are."""
    assert Product.model_validate({"price": -1}).price == -1
    assert Subscription.model_validate({"frequency": 0}).frequency == 0
    assert SubscriptionSession.model_validate({"minPeriods": 0}).min_periods == 0
    assert Payment.model_validate({"amount": -3.5}).amount == -3.5


# ── Field-by-field contract (docs/core @ 5e7d5a5) ────────────────────────────


def test_currency_is_a_required_object_on_payments_subscriptions_and_history():
    for model in (Payment, CombinedPaymentItem, Subscription, SubscriptionHistory):
        record = model.model_validate({"currencyId": 7, "currency": CURRENCY})
        assert record.currency.symbol == "USDC"
        assert record.currency.main_currency is not None
        assert record.currency.main_currency.symbol == "ETH"
        assert record.currency.main_currency.main_currency is None
        assert record.currency_id == 7


def test_main_currency_fields_are_nullable():
    native = Currency.model_validate({"id": 1, "symbol": "ETH", "address": ""})

    assert native.main_currency is None and native.main_currency_id is None
    assert native.address == ""


def test_api_key_user_id_is_zero_for_an_organization_level_key():
    key = ApiKey.model_validate({"id": 1, "organizationId": 7, "role": "admin"})

    assert key.user_id == 0
    assert key.expires_at is None


def test_customer_optional_strings_are_empty_not_none():
    customer = Customer.model_validate({"uuid": "u", "organizationId": 3})

    assert (customer.phone_number, customer.address, customer.reference) == ("", "", "")
    assert customer.user_id == 0 and customer.organization_id == 3


def test_refund_strings_are_empty_until_set_and_pointers_are_none():
    refund = RefundEntry.model_validate({"uuid": "refund@1", "status": "pending"})

    assert refund.merchant_message == "" and refund.tx_hash == ""
    assert refund.amount_min_units == ""
    assert refund.responded_at is None and refund.metadata is None
    assert refund.user_id == 0 and refund.organization_id == 0


def test_transaction_status_hash_and_message_default_to_empty():
    status = TransactionStatus.model_validate({"status": "created"})

    assert status.tx_hash == "" and status.message == ""
    assert status.settlement_details is None


def test_fee_recipient_fields_are_present():
    fee = OrganizationFee.model_validate(
        {"organizationId": 3, "organization": "0xorg", "feeBps": 50}
    )
    referral = ReferralFee.model_validate({"feeBps": 10})

    assert (fee.organization_id, fee.organization, fee.fee_bps) == (3, "0xorg", 50)
    assert referral.referral_id == 0 and referral.referrer == ""
    assert referral.deadline == GO_ZERO_TIME


def test_payment_ownership_and_metadata_are_non_nullable():
    payment = Payment.model_validate(
        {"uuid": "pay@1", "organizationId": 7, "metadata": {"feeBps": 100}}
    )

    assert payment.organization_id == 7
    assert payment.user_id == 0, "absent for org-level payments (live) → 0"
    assert payment.metadata.fee_bps == 100
    assert payment.product_id == 0


def test_combined_payment_keeps_its_pointers_nullable():
    item = CombinedPaymentItem.model_validate({"source": "payment", "customerUUID": "0000"})

    assert item.product_id is None and item.subscription_uuid is None and item.metadata is None
    assert item.customer_uuid == "0000"


def test_subscription_billing_dates_are_timestamps_not_none():
    sub = Subscription.model_validate({"uuid": "sub@1"})

    assert sub.last_billing_date == GO_ZERO_TIME and sub.next_billing_date == GO_ZERO_TIME
    assert sub.minimum_cancellation_date is None and sub.reference is None
    assert sub.customer_uuid is None
    assert sub.organization_id == 0 and sub.user_id == 0


def test_subscription_history_carries_product_and_metadata():
    entry = SubscriptionHistory.model_validate(
        {"uuid": "sub-hist@1", "productId": 9, "subscriptionUUID": "sub@1", "metadata": {}}
    )

    assert entry.product_id == 9 and entry.subscription_uuid == "sub@1"
    assert isinstance(entry.metadata, PaymentMetadata)


def test_session_optional_fields_decode_to_zero_values():
    session = OneTimePaymentSession.model_validate(
        {"uuid": "pay@1", "txType": "payment", "availableCurrencies": None}
    )

    assert session.price == 0.0 and session.product_id == 0
    assert session.product_name == session.success_url == session.customer_reference == ""
    assert session.available_currencies == []
    assert session.customer_uuid is None
    assert session.organization_id == 0 and session.fee_bps == 0


def test_subscription_session_numbers_default_to_zero():
    session = SubscriptionSession.model_validate(
        {"uuid": "sub@1", "txType": "createSubscription", "frequency": 60}
    )

    assert (session.frequency, session.trial_period, session.min_periods) == (60, 0, 0)
    assert session.upgrading_from_trial is False


def test_accounting_event_type_values():
    assert {"payment", "refund", "organizationFee", "referralFee"} <= set(ACCOUNTING_EVENT_TYPES)
    assert {"subscriptionHistory", "subHistory"} <= set(ACCOUNTING_EVENT_TYPES)
    assert AccountingEvent.model_validate({"type": "brandNew"}).type == "brandNew"


def test_claim_fund_hydrates():
    fund = ClaimFund.model_validate({"userId": 4, "totalAmountOwed": 12, "funded": True})

    assert fund.total_amount_owed == 12.0 and fund.funded is True


# ── Roles and enums ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["handle", "user", "admin", "owner"])
def test_every_role_the_api_can_return_deserializes(role):
    user = User.model_validate({"id": 1, "role": role})

    assert user.role == role
    assert isinstance(user.role, UserRole)


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN, "user", "admin"])
def test_create_user_accepts_the_assignable_roles(role):
    assert CreateUserDto(name="Jane", lastName="Smith", email="j@x.com", role=role).role == role


@pytest.mark.parametrize("role", [UserRole.OWNER, UserRole.HANDLE, "superuser"])
def test_create_user_rejects_other_roles_with_the_sdk_error(role):
    with pytest.raises(ValidationError, match="role"):
        CreateUserDto(name="Jane", lastName="Smith", email="j@x.com", role=role)


def test_unknown_user_role_is_kept_as_a_string():
    user = User.model_validate({"id": 1, "role": "auditor"})

    assert user.role == "auditor"
    assert not isinstance(user.role, UserRole)
    assert user.role != UserRole.ADMIN


def test_unknown_subscription_status_is_kept_not_coerced():
    sub = Subscription.model_validate({"subscriptionStatus": "frozen"})

    assert sub.subscription_status == "frozen"
    known = Subscription.model_validate({"subscriptionStatus": "active"})
    assert known.subscription_status is SubscriptionStatus.ACTIVE


def test_unknown_refund_status_is_kept():
    assert RefundEntry.model_validate({"status": "escalated"}).status == "escalated"
    assert RefundEntry.model_validate({"status": "refused"}).status is RefundStatus.REFUSED


def test_unknown_transaction_status_and_tx_type_are_kept():
    assert TransactionStatus.model_validate({"status": "settling"}).status == "settling"
    assert (
        TransactionStatus.model_validate({"status": "completed"}).status
        is TransactionStatusValue.COMPLETED
    )

    session = OneTimePaymentSession.model_validate({"uuid": "pay@1", "txType": "somethingNew"})
    assert session.tx_type == "somethingNew"


def test_unknown_api_key_role_is_kept():
    assert ApiKey.model_validate({"role": "service"}).role == "service"


# ── Webhook payloads ─────────────────────────────────────────────────────────


def test_unknown_subscription_webhook_type_keeps_the_raw_data():
    event = SubscriptionWebhook.model_validate(
        {"subscriptionUUID": "sub@1", "type": "paused", "data": {"until": "2026-02-01"}}
    )

    assert event.type == "paused"
    assert event.data == {"until": "2026-02-01"}
    assert event.subscription_reference == ""


def test_subscription_transition_with_unknown_statuses_parses():
    event = SubscriptionWebhook.model_validate(
        {
            "subscriptionUUID": "sub@1",
            "type": "status_transition",
            "data": {
                "previousStatus": "active",
                "currentStatus": "frozen",
                "updatedAt": "2026-01-01T00:00:00Z",
            },
        }
    )
    assert event.type is SubscriptionWebhookType.STATUS_TRANSITION
    assert isinstance(event.data, SubscriptionStatusTransition)
    assert event.data.previous_status is SubscriptionStatus.ACTIVE
    assert event.data.current_status == "frozen"


def test_billing_webhook_with_null_data_is_a_zero_history_entry():
    event = SubscriptionWebhook.model_validate({"type": "billing", "data": None})

    assert isinstance(event.data, SubscriptionHistory)


def test_session_webhook_status_may_be_null_and_link_defaults_to_empty():
    event = SessionWebhookResponse.model_validate(
        {
            "uuid": "pay@1",
            "txType": "payment",
            "status": None,
            "session": {"uuid": "pay@1", "organizationName": "O", "txType": "payment"},
        }
    )

    assert event.status is None
    assert event.management_page_link == ""
    assert isinstance(event.session, OneTimePaymentSession)


def test_session_discriminator_prefers_tx_type():
    base = {"uuid": "x", "organizationName": "Org", "test": False}

    assert isinstance(
        _discriminate_session({**base, "txType": "createSubscription", "frequency": 60}),
        SubscriptionSession,
    )
    assert isinstance(_discriminate_session({**base, "txType": "payment"}), OneTimePaymentSession)
    assert isinstance(
        _discriminate_session({**base, "txType": "payment", "frequency": 60}),
        OneTimePaymentSession,
    )
    # Unknown txType: a frequency selects the subscription shape, otherwise one-time.
    assert isinstance(
        _discriminate_session({**base, "txType": "createPAYGSubscription", "frequency": 9}),
        SubscriptionSession,
    )
    session = _discriminate_session({**base, "txType": "somethingNew"})
    assert isinstance(session, OneTimePaymentSession) and session.tx_type == "somethingNew"


def test_response_emails_are_plain_strings():
    """A stored address the request rule dislikes must not make reads fail."""
    assert User.model_validate({"email": "odd@localhost"}).email == "odd@localhost"


# ── Request DTOs raise the SDK's ValidationError ─────────────────────────────


@pytest.mark.parametrize(
    "build",
    [
        lambda: CreateCustomerDto(name="J", last_name="Doe", email="j@example.com"),
        lambda: CreateCustomerDto(name="John", last_name="Doe", email="nope"),
        lambda: CreateCustomerDto(name="John", last_name="Doe"),  # type: ignore[call-arg]
        lambda: UpdateCustomerDto(name="<b>"),
        lambda: CreateProductDto(name="P", description="Desc", price=1),
        lambda: CreateProductDto(name="Pro", description="Desc", price=0),
        lambda: UpdateProductDto(price=float("nan")),
        lambda: CreateUserDto(name="Jo", last_name="Do", email="j@x.com", role="owner"),
        lambda: UpdateUserDto(organization_fee_bps=5001),
        lambda: CreateProductDto.model_validate({"name": "Pro"}),
        lambda: UpdateProductDto.model_validate_json('{"price": -1}'),
    ],
)
def test_request_dto_failures_are_the_sdk_validation_error(build):
    with pytest.raises(ValidationError) as exc_info:
        build()

    assert not isinstance(exc_info.value, pydantic.ValidationError)
    assert exc_info.value.fields, "every failure carries per-field detail"
    assert exc_info.value.status_code is None


def test_request_dto_error_names_the_field():
    with pytest.raises(ValidationError) as exc_info:
        CreateCustomerDto(name="John & Co", last_name="Doe", email="j@example.com")

    assert exc_info.value.fields[0].field == "name"
    assert "&" in exc_info.value.fields[0].message


@pytest.mark.parametrize(
    "name", ["Jean-Luc", "O'Neil", "Anne Marie", "Zoë", "J. R.", "李雷", "   ", "José 2"]
)
def test_alphanumspace_accepts_what_the_api_accepts(name):
    assert CreateCustomerDto(name=name, last_name="Doe", email="j@example.com").name == name
    assert (
        CreateUserDto(name=name, last_name="Doe", email="j@example.com", role="user").name == name
    )


@pytest.mark.parametrize(
    "name",
    ["John<b>", "John & Co", "Smith, Jr", "(John)", "a", "x" * 101, "Jo²", "Ⅻ Jo", "Jo①", "Jo\t"],
)
def test_alphanumspace_rejects_what_the_api_rejects(name):
    with pytest.raises(ValidationError):
        CreateCustomerDto(name=name, last_name="Doe", email="j@example.com")
    with pytest.raises(ValidationError):
        UpdateUserDto(last_name=name)
    with pytest.raises(ValidationError):
        UpdateCustomerDto(name=name)


def test_emails_are_never_normalised():
    """The server preserves email case; so does the SDK."""
    dto = CreateCustomerDto(name="John", last_name="Doe", email="John.Doe@EXAMPLE.COM")

    assert dto.email == "John.Doe@EXAMPLE.COM"
    assert dto.to_body()["email"] == "John.Doe@EXAMPLE.COM"


@pytest.mark.parametrize("email", ["a@shop.test", "a@host.local", "ünï@exämple.com", "a+b@x.co"])
def test_structural_email_rule_accepts_what_the_server_accepts(email):
    assert CreateUserDto(name="Jo", last_name="Do", email=email, role="user").email == email


@pytest.mark.parametrize("email", ["", "no-at", "a@b", "a b@c.com", "@x.com", "a@.com", "a@@b.co"])
def test_structural_email_rule_rejects_malformed_addresses(email):
    with pytest.raises(ValidationError, match="email"):
        CreateCustomerDto(name="John", last_name="Doe", email=email)


def test_update_dtos_treat_empty_strings_as_not_provided():
    assert UpdateCustomerDto().to_body() == {}
    assert UpdateCustomerDto(name="", last_name="", email="", phone_number="").to_body() == {}
    assert UpdateUserDto(name="", email="").to_body() == {}
    assert UpdateUserDto(email="a@b.co").to_body() == {"email": "a@b.co"}
    assert UpdateUserDto(organization_fee_bps=0).to_body() == {"organizationFeeBps": 0}


@pytest.mark.parametrize("field", ["name", "description"])
def test_product_update_rejects_an_empty_name_or_description(field):
    with pytest.raises(ValidationError, match=field):
        UpdateProductDto(**{field: ""})


@pytest.mark.parametrize("fee", [-1, 5001, 1.5, True, "100"])
def test_organization_fee_bps_is_an_integer_from_0_to_5000(fee):
    with pytest.raises(ValidationError, match="organization_fee_bps"):
        CreateUserDto(
            name="Jo", last_name="Do", email="j@x.com", role="user", organization_fee_bps=fee
        )
    with pytest.raises(ValidationError, match="organization_fee_bps"):
        UpdateUserDto(organization_fee_bps=fee)


@pytest.mark.parametrize("fee", [0, 5000, 250])
def test_organization_fee_bps_bounds_are_inclusive(fee):
    assert UpdateUserDto(organization_fee_bps=fee).organization_fee_bps == fee


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf"), True, "9"])
def test_product_price_must_be_finite_and_positive(price):
    with pytest.raises(ValidationError, match="price"):
        CreateProductDto(name="Pro", description="Desc", price=price)
    with pytest.raises(ValidationError, match="price"):
        UpdateProductDto(price=price)


def test_product_reference_empty_string_is_omitted():
    body = CreateProductDto(name="Pro", description="Desc", price=1, reference="").to_body()

    assert body == {"name": "Pro", "description": "Desc", "price": 1.0}


@pytest.mark.parametrize("text", ["<script>", "a{b}", "x" * 101, "\x00bad", "\x85bad", " ", "　"])
def test_producttext_rejects_markup_blank_and_control_characters(text):
    with pytest.raises(ValidationError):
        CreateProductDto(name=text, description="fine description", price=1)
    with pytest.raises(ValidationError):
        UpdateProductDto(name=text)


def test_producttext_accepts_punctuation_and_unicode_on_products():
    product = CreateProductDto(
        name="Café Premium: 2-pack (new!) & more", description="Line one\nLine two", price=1
    )
    assert product.name.startswith("Café")
    assert UpdateProductDto(name="Zoë's plan").name == "Zoë's plan"


def test_producttext_length_is_counted_in_code_points():
    """The server counts runes; 100 accented characters are 200 bytes but 100 characters."""
    name = "é" * 100
    assert CreateProductDto(name=name, description="dd", price=1).name == name


# ── URL validation matches the API's http_url rule ───────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/ok",
        "https://shop.example.technology/ok",
        "https://checkout-web/success",
        "http://localhost:3000/x",
        "https://192.168.1.10:8443/cb",
        "HTTPS://Example.com/Case",
        # Live-verified: Go's url.Parse keeps a trailing space / a space in the path.
        "https://example.com/ok ",
        "https://example.com/o k",
    ],
)
def test_urls_the_api_accepts(url):
    assert validate_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "not a url",
        "/relative/path",
        "",
        "ftp://x/y",
        "https://:80/x",
        # Live-verified 400s that urlsplit would otherwise repair or tolerate.
        " https://example.com/ok",
        "https://exa mple.com/ok",
        "http:\\\\example.com",
        "http:///x",
    ],
)
def test_urls_the_api_rejects(url):
    assert validate_url(url) is False
