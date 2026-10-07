"""Session-related data models."""

from typing import Any, Dict, List, Optional, Type, Union

from pydantic import AliasChoices, Field, field_validator, model_validator

from qbitflow.dto.base_model import Bool, Float, Int, RequestModel, ResponseModel, Str
from qbitflow.exceptions.exceptions import ValidationError
from qbitflow.utils.duration import Duration
from qbitflow.utils.helpers import (
    MAX_UINT32,
    validate_integer,
    validate_price,
    validate_product_text,
    validate_url,
    validate_uuid,
)

from .status import TransactionStatus, TransactionType

#: Largest value of a Go ``uint64`` (product ids).
_MAX_UINT64 = 2**64 - 1


class BaseSession(ResponseModel):
    """
    Common fields shared by all session types (the API's ``TransactionData``).

    String and number fields the API omits when empty decode to ``""`` / ``0``; only
    ``customer_uuid`` is ``Optional`` (a pointer in the API).

    Attributes:
        uuid: Session UUID (``pay@``/``sub@``-prefixed).
        reference: Your own reference for the transaction (``""`` when none was set).
        product_id: Product ID (``0`` when the session uses an inline product).
        product_reference: Your own product reference (``""`` when none was used).
        product_name: Product or service name.
        description: Session description.
        price: Price in USD.
        success_url: URL to redirect to on success (``""`` when none was set).
        cancel_url: URL to redirect to on cancellation (``""`` when none was set).
        organization_id: Organization the session belongs to.
        organization_name: Organization name.
        fee_bps: Platform fee in basis points.
        organization_fee_bps: Organization fee in basis points (``0`` when none).
        user_id: User ID of the session creator (``0`` for organization-level sessions).
        user_name: Name of the session creator (set only for user-role creators).
        tx_type: Transaction type of the session (long form, e.g. "createSubscription").
            A value this SDK does not know yet is kept as a plain string.
        test: Whether this is a test session.
        customer_uuid: Customer UUID, or ``None`` when the customer is collected at checkout.
        customer_reference: Your own customer reference (``""`` when none was used).
        available_currencies: IDs of the currencies accepted for this session. Resolve
            details via ``client.currencies``.
    """

    uuid: Str = ""
    reference: Str = ""
    product_id: Int = 0
    product_reference: Str = ""
    product_name: Str = ""
    description: Str = ""
    price: Float = 0.0
    success_url: Str = ""
    cancel_url: Str = ""
    organization_id: Int = 0
    organization_name: Str = ""
    fee_bps: Int = 0
    organization_fee_bps: Int = 0
    user_id: Int = 0
    user_name: Str = ""
    tx_type: Union[TransactionType, str] = Field(
        default="",
        union_mode="left_to_right",
        description=(
            'Transaction type of the session. A one-time payment reports "payment"; a '
            'subscription session reports "createSubscription" - not the short "subscription" '
            "form. Unknown values are kept as plain strings."
        ),
    )
    test: Bool = False
    available_currencies: List[Int] = Field(default_factory=list)
    customer_uuid: Optional[Str] = Field(
        default=None,
        validation_alias=AliasChoices("customerUUID", "customerUuid", "customer_uuid"),
    )
    customer_reference: Str = ""


class OneTimePaymentSession(BaseSession):
    """Session for a one-time payment (the API's ``TransactionData``, ``txType: "payment"``)."""


class SubscriptionSession(BaseSession):
    """
    Session for a recurring subscription (the API's ``SubscriptionData``).

    Attributes:
        frequency: Billing frequency in seconds.
        trial_period: Trial period in seconds (``0`` when there is none).
        min_periods: Minimum number of billing periods (``0`` when there is none).
        upgrading_from_trial: Whether this session upgrades an existing trial subscription.
    """

    frequency: Int = 0
    trial_period: Int = 0
    min_periods: Int = 0
    upgrading_from_trial: Bool = False


AnySession = Union[SubscriptionSession, OneTimePaymentSession]


def _session_class(data: Dict[str, Any]) -> Type[BaseSession]:
    """
    Pick the session class for a raw session payload.

    ``txType`` is the discriminator: ``"payment"`` is a one-time payment and
    ``"createSubscription"`` a subscription. For any other (or a missing) ``txType`` the
    presence of a non-zero ``frequency`` — a field only ``SubscriptionData`` carries — selects
    the subscription shape.
    """
    tx_type = data.get("txType", data.get("tx_type"))
    if tx_type == TransactionType.ONE_TIME_PAYMENT.value:
        return OneTimePaymentSession
    if tx_type == TransactionType.CREATE_SUBSCRIPTION.value:
        return SubscriptionSession
    return SubscriptionSession if data.get("frequency") else OneTimePaymentSession


def _discriminate_session(data: Dict[str, Any]) -> AnySession:
    """Construct the correct session type from raw API response data (see ``_session_class``)."""
    session_class = _session_class(data)
    if session_class is SubscriptionSession:
        return SubscriptionSession.model_validate(data)
    return OneTimePaymentSession.model_validate(data)


class CreatePaymentSessionDto(RequestModel):
    """
    DTO for creating a one-time payment session.

    Provide either ``product_id`` / ``product_reference`` OR all of
    (``product_name``, ``description``, ``price``). An empty string means "not provided" and
    is omitted from the request.

    Raises:
        ValidationError: (the SDK's) if a value breaks the API's rules or no product is
            selected.
    """

    reference: Optional[str] = Field(
        default=None,
        description="Your own reference for the transaction (e.g. an order or invoice ID)",
    )
    product_id: Optional[int] = Field(default=None, description="Product ID")
    product_reference: Optional[str] = Field(
        default=None,
        description="Select an existing product by your own reference (alternative to product_id)",
    )
    product_name: Optional[str] = Field(default=None, description="Product name")
    description: Optional[str] = Field(default=None, description="Description")
    price: Optional[float] = Field(default=None, description="Price in USD, greater than 0")
    success_url: Optional[str] = Field(default=None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel redirect URL")
    customer_uuid: Optional[str] = Field(default=None, description="Customer UUID (bare UUID)")
    customer_reference: Optional[str] = Field(
        default=None,
        description=(
            "Select an existing customer by your own reference (alternative to customer_uuid)"
        ),
    )

    @field_validator("product_id", mode="before")
    @classmethod
    def validate_product_id(cls, v: Any) -> Any:
        if v is not None:
            if validate_integer(v, 1, _MAX_UINT64) is not None:
                raise ValueError("product_id must be a positive integer")
        return v

    @field_validator("price", mode="before")
    @classmethod
    def validate_session_price(cls, v: Any) -> Any:
        # The API rejects an inline price of 0 (live-verified), so a provided price must be
        # finite and strictly positive.
        if v is not None:
            problem = validate_price(v)
            if problem is not None:
                raise ValueError(f"price {problem}")
        return v

    @field_validator("success_url", "cancel_url")
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        # A redirect target is attacker-visible, so only absolute http(s) URLs are allowed:
        # this rejects relative paths and schemes such as javascript:.
        #
        # An empty string means "not provided" - the API's omitempty skips validation for
        # it - so it is skipped here too (and omitted from the body).
        if v and not validate_url(v):
            raise ValueError("must be an absolute http(s) URL with a host")
        return v

    @field_validator("customer_uuid")
    @classmethod
    def validate_customer_uuid(cls, v: Optional[str]) -> Optional[str]:
        # "" means "not provided"; anything else must be a bare UUID (the API answers 400 for
        # a prefixed or malformed value).
        if v and not validate_uuid(v):
            raise ValueError("customer_uuid must be a bare UUID (8-4-4-4-12 hex digits)")
        return v

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, v: Optional[str]) -> Optional[str]:
        # Mirrors the API's producttext rule so markup is caught before the round-trip.
        # An empty string means "not provided" (the API's omitempty), so it is skipped.
        if v:
            problem = validate_product_text(v, 2, 100)
            if problem is not None:
                raise ValueError(f"product_name {problem}")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        # An empty string means "not provided" (the API's omitempty), so it is skipped.
        if v:
            problem = validate_product_text(v, 2, 500)
            if problem is not None:
                raise ValueError(f"description {problem}")
        return v

    @model_validator(mode="after")
    def _require_a_product(self) -> "CreatePaymentSessionDto":
        problem = self._product_problem()
        if problem is not None:
            raise ValueError(problem)
        return self

    def _product_problem(self) -> Optional[str]:
        if (
            self.product_id is None
            and not self.product_reference
            and (not self.product_name or not self.description or self.price is None)
        ):
            return (
                "Either product_id, product_reference, or "
                "(product_name, description, price) must be provided"
            )
        return None

    def check(self) -> None:
        """
        Validate that some product is selected (also enforced on construction).

        Raises:
            ValidationError: (the SDK's) if neither a stored product (``product_id`` /
                ``product_reference``) nor a complete inline product (``product_name`` +
                ``description`` + ``price``) is provided.
        """
        problem = self._product_problem()
        if problem is not None:
            raise ValidationError(problem)


class CreateSubscriptionSessionDto(CreatePaymentSessionDto):
    """
    DTO for creating a subscription session.

    Product resolution is the same as for a one-time payment: provide either an existing
    product (``product_id`` or ``product_reference``) **or** an inline ghost product
    (``product_name`` + ``description`` + ``price``).

    ``frequency`` is required and its value must be at least 1. ``trial_period`` may be 0.
    ``min_periods`` is an integer from 0 to 4294967295; 0 means "no minimum" and is omitted.
    """

    frequency: Duration = Field(..., description="Billing frequency")
    trial_period: Optional[Duration] = Field(default=None, description="Trial period")
    min_periods: Optional[int] = Field(default=None, description="Minimum billing periods")

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: Duration) -> Duration:
        if v.value < 1:
            raise ValueError("frequency value must be at least 1")
        return v

    @field_validator("min_periods", mode="before")
    @classmethod
    def validate_min_periods(cls, v: Any) -> Any:
        if v is not None:
            problem = validate_integer(v, 0, MAX_UINT32)
            if problem is not None:
                raise ValueError(f"min_periods {problem}")
        return v

    def to_body(self) -> Dict[str, Any]:
        body = super().to_body()
        if body.get("minPeriods") == 0:
            del body["minPeriods"]
        return body


class LinkResponse(ResponseModel):
    """Response containing a payment/subscription link (the API's ``LinkResponse``)."""

    uuid: Str = ""
    link: Str = ""


class SessionWebhookResponse(ResponseModel):
    """
    Webhook payload sent when a session completes (the API's ``WebhookCompletedTransaction``).

    The ``session`` field is one of :class:`OneTimePaymentSession` or
    :class:`SubscriptionSession`, resolved automatically from its ``txType``. Parse a delivery
    with :func:`qbitflow.parse_session_webhook` (after verifying its signature).

    Attributes:
        uuid: Transaction UUID.
        status: Transaction status, or ``None``.
        session: The session data.
        tx_type: Transaction type (unknown values are kept as plain strings).
        management_page_link: Link to the QBitFlow management page for this transaction
            (``""`` when not provided).

    Example:
        >>> event = parse_session_webhook(body)
        >>> if event.status and event.status.status == TransactionStatusValue.COMPLETED:
        ...     print(f"Payment completed: {event.session.uuid}")
    """

    uuid: Str = ""
    status: Optional[TransactionStatus] = None
    session: AnySession = Field(default_factory=OneTimePaymentSession)
    tx_type: Union[TransactionType, str] = Field(default="", union_mode="left_to_right")
    management_page_link: Str = ""

    @model_validator(mode="before")
    @classmethod
    def _parse_session_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("session"), dict):
            data = dict(data)
            data["session"] = _discriminate_session(data["session"])
        return data
