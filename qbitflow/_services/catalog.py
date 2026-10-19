"""Products, customers and checkout sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional, Union

from .._transport import Endpoint, Query, RequestOptions, pathf
from .._validation import Money, Validator, check_path_tx_id, check_path_uuid
from ..errors import field_error
from ..models.checkout import CheckoutSessionStatus, CreatedCheckoutSession
from ..models.common import Duration, Page
from ..models.enums import CheckoutSessionStatusValue
from ..models.resources import Customer, Product
from ._base import (
    NOT_GIVEN,
    NotGiven,
    Service,
    compact,
    duration_body,
    iterate_pages,
    metadata_body,
    money,
)

__all__ = [
    "SubscriptionTermsParams",
    "CheckoutFees",
    "FeeItem",
    "ProductsService",
    "CustomersService",
    "CheckoutSessionsService",
]

#: The most lines :attr:`CheckoutFees.items` may have.
MAX_FEE_ITEMS = 10


@dataclass
class SubscriptionTermsParams:
    """Subscription terms (a product's, on ``products.create`` / ``products.update``): each field
    given replaces the base's, each field left ``None`` keeps it.

    Attributes:
        frequency: How often it bills: at least 1 unit, at most 1 year (the API also requires
            at least 1 hour in live mode, 5 minutes in test mode). Required on a create.
        trial_period: A free trial before the first bill (``Duration(value=0)``: none, removing
            one).
        min_periods: The periods the customer commits to before cancelling, at most 1000 (0:
            none, removing one).
    """

    frequency: Optional[Duration] = None
    trial_period: Optional[Duration] = None
    min_periods: Optional[int] = None


@dataclass
class FeeItem:
    """A line of your own on a checkout (:class:`CheckoutFees`): a tax, shipping, a service fee,
    shown to the customer and paid with the price (a subscription's: with every bill).

    Attributes:
        label: The line's name, as the checkout shows it: one line, 1 to 40 characters, the
            name rule (``"VAT (20%)"``, ``"Shipping"``).
        amount_usd: The line's amount in USD, a decimal string (``"4.99"``) or a
            ``decimal.Decimal`` (sent as ``str(value)``): above 0, at most 1,000,000, with at most
            2 decimals. Never a float.
        description: More about the line, at most 200 characters (the text rule).
    """

    label: str
    amount_usd: Money
    description: Optional[str] = None


@dataclass
class CheckoutFees:
    """What a checkout adds to its price: a one-time payment's
    (``checkout_sessions.create_payment`` ``fees``), or a subscription's
    (``checkout_sessions.create_subscription`` ``fees``, each of its bills then charging the price
    and the same lines). The customer pays the price plus every line (the payment's
    ``amount_usd``); QBitFlow's fee (and an organization's) is taken on that amount, and the
    network fee comes on top of it. In test mode the amount, fees included, is capped at ``"5"``
    (a 400 on ``fees``).

    Attributes:
        processing_fee: The customer pays QBitFlow's processing fee, as a last line
            (``type`` ``processingFee``, label ``Processing fee``) computed by QBitFlow on the
            price and your lines at your platform fee p (never below 0.5 %) as
            base × p / (1 − p), rounded up to the cent. QBitFlow's fee is also taken on that
            line, so this gross-up leaves you at least the price and your lines, as if no fee
            were taken ($100 + $20 VAT at 0.99 % → a $1.20 fee, $121.20 charged, $120.00 kept).
            A marketplace's organization fee is not passed on. ``None``: the space's
            ``checkout.customerPaysProcessingFee`` setting decides (off by default; set in the
            dashboard). ``False`` turns it off for this checkout.
        items: Up to 10 lines of your own, shown in this order, before the processing fee.
    """

    processing_fee: Optional[bool] = None
    items: List[FeeItem] = field(default_factory=list)


def _validate_fees(v: Validator, fees: Any) -> None:
    """The ``fees`` rules (the docs' ``CheckoutFeesDto``), on their wire paths: at most 10 lines;
    each label the name rule, 1 to 40; each description the text rule, at most 200; each amount
    the usd rule. Reported last (after the session's other fields)."""
    if fees is None:
        return
    if not isinstance(fees, CheckoutFees):
        v.add("fees", "must be a CheckoutFees")
        return
    v.boolean("fees.processingFee", fees.processing_fee)
    items: Any = fees.items  # checked as given: a caller may pass anything
    if items is None:
        return
    if isinstance(items, (str, bytes)) or not isinstance(items, (list, tuple)):
        v.add("fees.items", "must be a list of FeeItem")
        return
    if len(items) > MAX_FEE_ITEMS:
        v.add("fees.items", f"must have at most {MAX_FEE_ITEMS} lines")
    item: Any
    for i, item in enumerate(items):
        path = f"fees.items[{i}]"
        if not isinstance(item, FeeItem):
            v.add(path, "must be a FeeItem")
            continue
        if v.required(f"{path}.label", item.label):
            v.name(f"{path}.label", item.label, 1, 40)
        v.text(f"{path}.description", item.description, 0, 200)
        if v.money_required(f"{path}.amountUsd", item.amount_usd):
            v.usd(f"{path}.amountUsd", item.amount_usd)


def fees_body(fees: CheckoutFees) -> Dict[str, Any]:
    """The fees' wire form: ``processingFee`` when set, ``items`` when any; each amount a JSON
    string (a ``Decimal`` as ``str(value)``)."""
    body: Dict[str, Any] = {}
    if fees.processing_fee is not None:
        body["processingFee"] = fees.processing_fee
    if fees.items:
        body["items"] = [
            compact(
                label=item.label,
                description=item.description,
                amountUsd=money(item.amount_usd),
            )
            for item in fees.items
        ]
    return body


def validate_terms(
    v: Validator,
    prefix: str,
    frequency: Any,
    trial_period: Any,
    min_periods: Any,
    frequency_required: bool,
) -> None:
    """The subscription terms' rules; ``prefix`` is the wire path (``subscription.`` on
    products, ``""`` on sessions)."""
    if frequency is not None:
        v.duration(prefix + "frequency", frequency, True)
    elif frequency_required:
        v.add(prefix + "frequency", "is required")
    if trial_period is not None:
        v.duration(prefix + "trialPeriod", trial_period, False)
    if min_periods is not None:
        v.int_range(prefix + "minPeriods", min_periods, 0, 1000)


def terms_body(
    frequency: Optional[Duration], trial_period: Optional[Duration], min_periods: Optional[int]
) -> Dict[str, Any]:
    """The terms' wire form, unset values left out."""
    body: Dict[str, Any] = {}
    if frequency is not None:
        body["frequency"] = duration_body(frequency)
    if trial_period is not None:
        body["trialPeriod"] = duration_body(trial_period)
    if min_periods is not None:
        body["minPeriods"] = min_periods
    return body


def _validate_subscription(
    v: Validator, subscription: Any, frequency_required: bool
) -> Optional[SubscriptionTermsParams]:
    if subscription is None:
        return None
    if not isinstance(subscription, SubscriptionTermsParams):
        v.add("subscription", "must be a SubscriptionTermsParams")
        return None
    validate_terms(
        v,
        "subscription.",
        subscription.frequency,
        subscription.trial_period,
        subscription.min_periods,
        frequency_required,
    )
    return subscription


def _clearable(value: Union[str, None, NotGiven]) -> Optional[str]:
    """A clearable update field's wire value: ``None`` when left out, ``""`` to clear."""
    if isinstance(value, NotGiven):
        return None
    return "" if value is None else value


def _given(value: Any) -> bool:
    """Whether an optional money input is set (``None`` and ``""`` are unset)."""
    return value is not None and value != ""


class ProductsService(Service):
    """Products: one-time products, and subscription products with their terms
    (``client.products``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_hidden: bool = False,
        subscription: Optional[bool] = None,
        reference: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Product]:
        """One page of the space's products (``GET /products``; newest first, page size 20 by
        default, at most 100). :meth:`iterate` walks every page.

        Args:
            limit: The page size (the API's default 20 when ``None``, at most 100).
            cursor: The previous page's ``next_cursor``, verbatim; ``None`` for the first page.
            include_hidden: List the hidden products too (``is_active`` False).
            subscription: Keep only the subscription products (True) or the one-time ones
                (False).
            reference: Keep only the product with this reference, hidden or not (a page of 0 or
                1 product; :meth:`get_by_reference` reads it).
        """
        v = Validator()
        v.page(limit, cursor)
        v.boolean("includeHidden", include_hidden)
        v.boolean("subscription", subscription)
        v.reference("reference", reference)
        v.check()
        query = (
            Query()
            .page(limit, cursor)
            .flag("includeHidden", include_hidden)
            .boolean("subscription", subscription)
            .string("reference", reference)
        )
        return self._call(Page[Product], Endpoint("GET", "/products", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_hidden: bool = False,
        subscription: Optional[bool] = None,
        reference: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Product]:
        """Every product :meth:`list` returns, fetching the pages lazily from ``cursor`` (or the
        first page) and keeping the filters and the page size."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                include_hidden=include_hidden,
                subscription=subscription,
                reference=reference,
                options=options,
            ),
            cursor,
        )

    def create(
        self,
        *,
        name: str,
        price_usd: Money,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        subscription: Optional[SubscriptionTermsParams] = None,
        metadata: Optional[Mapping[str, str]] = None,
        options: Optional[RequestOptions] = None,
    ) -> Product:
        """Create a product (``POST /products``, 201). Sends an ``Idempotency-Key``; retried on
        transient failures. A subscription product needs ``subscription.frequency``.

        Args:
            name: 2 to 100 characters, one line.
            price_usd: The price in USD, a decimal string (``"12.50"``) or a ``Decimal``: above
                0, at most 2 decimals, at most 1,000,000. The API also caps it at ``"5"`` in test
                mode (400 with ``details["max"]`` ``"5"``) and requires more than ``"0.25"`` for a
                live subscription product (``details["min"]``).
            description: 2 to 500 characters.
            reference: Your reference, unique per space and mode (1 to 100 of
                ``A-Z a-z 0-9 . _ : @ -``); the product's uuid when left out.
            subscription: Makes it a subscription product (``frequency`` required); ``None``: a
                one-time product.
            metadata: Your own data on the product (an id in your catalog): at most 50 keys of 1
                to 40 characters among ``A-Z a-z 0-9 _ - . :``, values of at most 500 characters
                without control or bidirectional characters. A key set to ``""`` is not stored.
                Never put secrets or personal data in it.

        Raises:
            ValidationError: an invalid input (nothing is sent), or the API's 400.
            ConflictError: 409 ``unique_violation`` on the reference (references are unique
                among the space's live products).
            PermissionDeniedError: a member's key needs the organization's ``members.products``
                policy, and ``members.subscriptions`` to give the product subscription terms (403
                ``policy_disabled``, ``details["policy"]`` names it).
        """
        v = Validator()
        if v.required("name", name):
            v.name("name", name, 2, 100)
        v.text("description", description, 2, 500)
        if v.money_required("priceUsd", price_usd):
            v.usd("priceUsd", price_usd)
        v.reference("reference", reference)
        terms = _validate_subscription(v, subscription, True)
        v.metadata("metadata", metadata)
        v.check()
        body = compact(
            name=name, description=description, priceUsd=money(price_usd), reference=reference
        )
        if terms is not None:
            body["subscription"] = terms_body(
                terms.frequency, terms.trial_period, terms.min_periods
            )
        metadata_body(body, metadata)
        endpoint = Endpoint("POST", "/products", body=body, idempotent=True)
        return self._call(Product, endpoint, options)

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Product:
        """A product by its uuid (``GET /products/:uuid``), hidden ones included. An unknown,
        deleted or another space's product is a :class:`~qbitflow.NotFoundError`."""
        check_path_uuid("uuid", uuid)
        return self._call(Product, Endpoint("GET", pathf("/products/{}", uuid)), options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Product:
        """The space's product with your reference, hidden or not: it runs :meth:`list`'s
        reference filter (``GET /products?reference=``) and returns its one product.

        Raises:
            ValidationError: the reference is not 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``
                (nothing is sent).
            NotFoundError: no product has that reference (status 404, code ``not_found``), as
                an unknown uuid is.
        """
        return self._get_by_reference(
            Product, "/products", "product", reference, lambda p: p.reference, options
        )

    def update(
        self,
        uuid: str,
        *,
        name: Optional[str] = None,
        description: Union[str, None, NotGiven] = NOT_GIVEN,
        price_usd: Optional[Money] = None,
        is_active: Optional[bool] = None,
        subscription: Optional[SubscriptionTermsParams] = None,
        remove_subscription: bool = False,
        metadata: Optional[Mapping[str, str]] = None,
        options: Optional[RequestOptions] = None,
    ) -> Product:
        """Update a product in place (``PATCH /products/:uuid``): only the arguments given
        change (none: a no-op that returns the product). The reference cannot change. A new
        price or new terms apply to new checkouts and new subscribers only: existing
        subscriptions and open checkout sessions keep theirs. Not retried.

        Args:
            name: The new name, 2 to 100 characters.
            description: The new description (2 to 500 characters); ``""`` (or ``None``) clears
                it, left out keeps it.
            price_usd: The new price in USD, a decimal string as at creation (``None`` or ``""``:
                unchanged).
            is_active: False hides the product from :meth:`list`, True lists it again.
            subscription: Sets (or changes) the subscription terms, field by field, for new
                subscribers only; a one-time product needs ``frequency``.
            remove_subscription: Makes it a one-time product again (not with ``subscription``).
            metadata: Merged into the product's: a key set to a value sets it, a key set to
                ``""`` deletes it, keys not named are kept (``None``: unchanged). At most 50 keys
                once merged.

        Raises:
            PermissionDeniedError: a member's key gives a product subscription terms only with
                the organization's ``members.subscriptions`` policy (403 ``policy_disabled``);
                ``remove_subscription`` and other edits never need it.
        """
        check_path_uuid("uuid", uuid)
        clear_description = _clearable(description)
        v = Validator()
        v.name("name", name, 2, 100)
        v.text("description", clear_description, 2, 500)
        if _given(price_usd):
            v.usd("priceUsd", price_usd)
        v.boolean("isActive", is_active)
        v.boolean("removeSubscription", remove_subscription)
        terms = _validate_subscription(v, subscription, False)
        v.exclusive(
            "subscription",
            subscription is not None,
            "removeSubscription",
            bool(remove_subscription),
        )
        v.metadata("metadata", metadata)
        v.check()
        body = compact(name=name, priceUsd=money(price_usd) if _given(price_usd) else None)
        if clear_description is not None:
            body["description"] = clear_description
        if is_active is not None:
            body["isActive"] = is_active
        if terms is not None:
            body["subscription"] = terms_body(
                terms.frequency, terms.trial_period, terms.min_periods
            )
        if remove_subscription:
            body["removeSubscription"] = True
        metadata_body(body, metadata)
        endpoint = Endpoint("PATCH", pathf("/products/{}", uuid), body=body)
        return self._call(Product, endpoint, options)

    def delete(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Delete a product (``DELETE /products/:uuid``, 204; a soft delete): it leaves every read
        and frees its reference. It does not stop its subscriptions (they keep billing at their
        price): cancel them with ``subscriptions.cancel`` if the product is gone for good. Not
        retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/products/{}", uuid)), options)


class CustomersService(Service):
    """Customers (``client.customers``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        email: Optional[str] = None,
        reference: Optional[str] = None,
        verified: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Customer]:
        """One page of the space's customers (``GET /customers``; newest first, page size 20 by
        default, at most 100). :meth:`iterate` walks every page.

        Args:
            limit: The page size (the API's default 20 when ``None``, at most 100).
            cursor: The previous page's ``next_cursor``, verbatim; ``None`` for the first page.
            email: Keep only the customers with this email, whatever its casing (several may
                share one: this is how to find customers by email).
            reference: Keep only the customer with this reference (a page of 0 or 1 customer;
                :meth:`get_by_reference` reads it).
            verified: Keep only the customers the merchant created (True) or those created from
                an email a payer typed at checkout (False).
        """
        v = Validator()
        v.page(limit, cursor)
        v.email("email", email)
        v.reference("reference", reference)
        v.boolean("verified", verified)
        v.check()
        query = (
            Query()
            .page(limit, cursor)
            .string("email", email)
            .string("reference", reference)
            .boolean("verified", verified)
        )
        return self._call(Page[Customer], Endpoint("GET", "/customers", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        email: Optional[str] = None,
        reference: Optional[str] = None,
        verified: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Customer]:
        """Every customer :meth:`list` returns, fetching the pages lazily from ``cursor`` (or the
        first page) and keeping the filters and the page size."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                email=email,
                reference=reference,
                verified=verified,
                options=options,
            ),
            cursor,
        )

    def create(
        self,
        *,
        first_name: str,
        email: str,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        address: Optional[str] = None,
        reference: Optional[str] = None,
        metadata: Optional[Mapping[str, str]] = None,
        options: Optional[RequestOptions] = None,
    ) -> Customer:
        """Create a customer (``POST /customers``, 201; verified). Sends an
        ``Idempotency-Key``; retried on transient failures. The email is stored lowercase and is
        not unique: several customers of a space may share one.

        Args:
            first_name: 2 to 100 characters, one line.
            email: At most 254 characters.
            last_name: 1 to 100 characters, one line.
            phone_number: At most 32 characters: digits and ``. - ( )`` space, an optional +.
            address: At most 500 characters.
            reference: Your reference (e.g. your own customer id), unique per space and mode: 1 to
                100 of ``A-Z a-z 0-9 . _ : @ -``.
            metadata: Your own data on the customer (a CRM key): at most 50 keys of 1 to 40
                characters among ``A-Z a-z 0-9 _ - . :``, values of at most 500 characters
                without control or bidirectional characters. A key set to ``""`` is not stored.

        Raises:
            ConflictError: 409 ``unique_violation`` when the reference is taken by another live
                customer of the space (``details["field"]`` ``"reference"``).
        """
        v = Validator()
        if v.required("firstName", first_name):
            v.name("firstName", first_name, 2, 100)
        v.name("lastName", last_name, 1, 100)
        if v.required("email", email):
            v.email("email", email)
        v.phone("phoneNumber", phone_number)
        v.text("address", address, 0, 500)
        v.reference("reference", reference)
        v.metadata("metadata", metadata)
        v.check()
        body = compact(
            firstName=first_name,
            lastName=last_name,
            email=email,
            phoneNumber=phone_number,
            address=address,
            reference=reference,
        )
        metadata_body(body, metadata)
        endpoint = Endpoint("POST", "/customers", body=body, idempotent=True)
        return self._call(Customer, endpoint, options)

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Customer:
        """A customer by its uuid (``GET /customers/:uuid``). An unknown, deleted or another
        space's customer is a :class:`~qbitflow.NotFoundError`."""
        check_path_uuid("uuid", uuid)
        return self._call(Customer, Endpoint("GET", pathf("/customers/{}", uuid)), options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Customer:
        """The space's customer with your reference: it runs :meth:`list`'s reference filter
        (``GET /customers?reference=``) and returns its one customer. To find customers by
        email, use :meth:`list` with ``email`` (an email may match several).

        Raises:
            ValidationError: the reference is not 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``
                (nothing is sent).
            NotFoundError: no customer has that reference (status 404, code ``not_found``).
        """
        return self._get_by_reference(
            Customer, "/customers", "customer", reference, lambda c: c.reference, options
        )

    def update(
        self,
        uuid: str,
        *,
        first_name: Optional[str] = None,
        last_name: Union[str, None, NotGiven] = NOT_GIVEN,
        email: Optional[str] = None,
        phone_number: Union[str, None, NotGiven] = NOT_GIVEN,
        address: Union[str, None, NotGiven] = NOT_GIVEN,
        metadata: Optional[Mapping[str, str]] = None,
        options: Optional[RequestOptions] = None,
    ) -> Customer:
        """Update a customer (``PATCH /customers/:uuid``): only the arguments given change. The
        first name and the email cannot be cleared; the reference cannot change. Not retried.

        Args:
            first_name: The new first name, 2 to 100 characters.
            last_name: The new last name (1 to 100 characters); ``""`` (or ``None``) clears it,
                left out keeps it.
            email: The new email.
            phone_number: The new phone number; ``""`` (or ``None``) clears it, left out keeps it.
            address: The new address; ``""`` (or ``None``) clears it, left out keeps it.
            metadata: Merged into the customer's: a key set to a value sets it, a key set to
                ``""`` deletes it, keys not named are kept (``None``: unchanged). At most 50 keys
                once merged.
        """
        check_path_uuid("uuid", uuid)
        last = _clearable(last_name)
        phone = _clearable(phone_number)
        addr = _clearable(address)
        v = Validator()
        v.name("firstName", first_name, 2, 100)
        v.name("lastName", last, 1, 100)
        v.email("email", email)
        v.phone("phoneNumber", phone)
        v.text("address", addr, 0, 500)
        v.metadata("metadata", metadata)
        v.check()
        body = compact(firstName=first_name, email=email)
        for key, value in (("lastName", last), ("phoneNumber", phone), ("address", addr)):
            if value is not None:
                body[key] = value
        metadata_body(body, metadata)
        endpoint = Endpoint("PATCH", pathf("/customers/{}", uuid), body=body)
        return self._call(Customer, endpoint, options)

    def delete(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Delete a customer (``DELETE /customers/:uuid``, 204; a soft delete): it leaves every
        read and frees its reference; its past payments keep naming it
        (:attr:`CustomerSummary.deleted`). Not retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/customers/{}", uuid)), options)


def _validate_session(
    v: Validator,
    reference: Any,
    product_uuid: Any,
    product_reference: Any,
    product_name: Any,
    description: Any,
    price_usd: Any,
    success_url: Any,
    cancel_url: Any,
    customer_uuid: Any,
    customer_reference: Any,
    expires_in_minutes: Any,
    metadata: Any,
) -> None:
    """A checkout session's rules: the product choice, names, texts, references, URLs, the price,
    the lifetime and the metadata."""
    v.reference("reference", reference)
    v.uuid("productUuid", product_uuid)
    v.reference("productReference", product_reference)
    v.name("productName", product_name, 2, 100)
    v.text("description", description, 2, 500)
    v.url("successUrl", success_url)
    v.url("cancelUrl", cancel_url)
    v.uuid("customerUuid", customer_uuid)
    v.reference("customerReference", customer_reference)
    if expires_in_minutes is not None and expires_in_minutes != 0:  # 0 = the default
        v.int_range("expiresInMinutes", expires_in_minutes, 10, 1440)
    v.metadata("metadata", metadata)

    # Exactly one of: productUuid, productReference, an inline product. Any inline field next to
    # productUuid or productReference counts as mixing.
    inline = bool(product_name) or _given(price_usd) or bool(description)
    chosen = sum(1 for given in (bool(product_uuid), bool(product_reference), inline) if given)
    if chosen != 1:
        v.add(
            "productUuid",
            "or productReference, or an inline product (productName and priceUsd), is required: "
            "exactly one of them",
        )
    elif inline:
        if not product_name:
            v.add("productName", "is required for an inline product")
        if not _given(price_usd):
            v.add("priceUsd", "is required for an inline product")
        else:
            v.usd("priceUsd", price_usd)


def _session_body(
    reference: Optional[str],
    product_uuid: Optional[str],
    product_reference: Optional[str],
    product_name: Optional[str],
    description: Optional[str],
    price_usd: Optional[Money],
    success_url: Optional[str],
    cancel_url: Optional[str],
    customer_uuid: Optional[str],
    customer_reference: Optional[str],
    expires_in_minutes: Optional[int],
    metadata: Optional[Mapping[str, str]],
) -> Dict[str, Any]:
    body = compact(
        reference=reference,
        productUuid=product_uuid,
        productReference=product_reference,
        productName=product_name,
        description=description,
        priceUsd=money(price_usd),
        successUrl=success_url,
        cancelUrl=cancel_url,
        customerUuid=customer_uuid,
        customerReference=customer_reference,
        expiresInMinutes=expires_in_minutes or None,
    )
    metadata_body(body, metadata)
    return body


class CheckoutSessionsService(Service):
    """Checkout sessions: hosted payment pages for one-time payments and subscriptions
    (``client.checkout_sessions``)."""

    def create_payment(
        self,
        *,
        reference: Optional[str] = None,
        product_uuid: Optional[str] = None,
        product_reference: Optional[str] = None,
        product_name: Optional[str] = None,
        description: Optional[str] = None,
        price_usd: Optional[Money] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        customer_reference: Optional[str] = None,
        expires_in_minutes: Optional[int] = None,
        metadata: Optional[Mapping[str, str]] = None,
        fees: Optional[CheckoutFees] = None,
        options: Optional[RequestOptions] = None,
    ) -> CreatedCheckoutSession:
        """Open a one-time payment checkout session (``POST /checkout-sessions/payment``, 201)
        and return its link, its ``pay@…`` id and its expiry: send the customer to its ``link``.
        Sends an ``Idempotency-Key``; retried on transient failures.

        The :class:`~qbitflow.Payment` exists, with the same id, once the customer's transaction
        is confirmed: fulfil on the ``payment.completed`` webhook (or :meth:`get` ``completed``),
        give up on ``checkout.expired``.

        Name the product with **exactly one** of ``product_uuid``, ``product_reference``, or an
        inline product (``product_name`` + ``price_usd``, ``description`` optional).

        Args:
            reference: Your reference for the payment (an order or invoice id), kept on it:
                unique per space (open sessions included), 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``.
            product_uuid: One of the space's products (unknown: 404).
            product_reference: Names the product by its reference instead (unknown: 404).
            product_name: An inline product's name (2 to 100 characters, one line): the payment
                keeps it as a snapshot, without ``product_uuid``.
            description: An inline product's description (2 to 500 characters), optional.
            price_usd: An inline product's price in USD, a decimal string (``"12.50"``) or a
                ``Decimal``: above 0, at most 2 decimals, at most 1,000,000. The API caps it at
                ``"5"`` in test mode (``details["max"]`` ``"5"``).
            success_url: Where the customer goes after paying, through QBitFlow's page for the
                payment (:data:`~qbitflow.PLACEHOLDER_UUID`: the session's id;
                :data:`~qbitflow.PLACEHOLDER_TRANSACTION_TYPE`: payment or createSubscription).
                Default: the space's ``checkout.defaults`` setting. https only in live mode.
                Reaching it is no proof of payment: fulfil on ``payment.completed``.
            cancel_url: Where the customer goes after a cancelled or failed payment (same
                placeholders).
            customer_uuid: One of the space's customers (unknown: 404); the checkout then asks
                the customer nothing.
            customer_reference: Your own reference of the customer, kept on the payment: the
                space's customer with this reference is linked if there is one (none is created).
                The checkout then asks the customer nothing.
            expires_in_minutes: How long the checkout can be paid, 10 to 1440 (``None`` or 0:
                the default lifetime; never longer than it).
            metadata: Your own data on the checkout (an order id, a CRM key): at most 50 keys of
                1 to 40 characters among ``A-Z a-z 0-9 _ - . :``, values of at most 500 characters
                without control or bidirectional characters (``""`` values are dropped). Copied
                onto the payment and into its webhooks (``payment.completed``,
                ``checkout.expired``); never shown to the customer. Never put secrets or personal
                data in it.
            fees: Amounts the customer pays on top of the price: up to 10 lines of your own (a
                tax, shipping) and QBitFlow's processing fee (:class:`CheckoutFees`), shown line
                by line. The payment's ``amount_usd`` is the price plus every line, QBitFlow's
                fee is taken on it, and the network fee comes on top. ``None``: no lines of your
                own, and the space's ``checkout.customerPaysProcessingFee`` setting decides the
                processing fee.

        Raises:
            ValidationError: an invalid input (nothing is sent); the API's 400
                ``validation_failed`` (test mode caps the amount, fees included, at ``"5"``,
                ``details["max"]``; live mode needs https URLs).
            NotFoundError: an unknown product or customer.
            ConflictError: 409 ``unique_violation`` on the reference; 409 ``merchant_not_ready``
                (``details["reason"]``) when the space's wallets accept no currency.
            GoneError: 410 ``merchant_closed`` for a removed member's or a closed
                organization's space.
        """
        v = Validator()
        _validate_session(
            v,
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price_usd,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
            metadata,
        )
        _validate_fees(v, fees)
        v.check()
        body = _session_body(
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price_usd,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
            metadata,
        )
        if fees is not None:
            body["fees"] = fees_body(fees)
        endpoint = Endpoint("POST", "/checkout-sessions/payment", body=body, idempotent=True)
        return self._call(CreatedCheckoutSession, endpoint, options)

    def create_subscription(
        self,
        *,
        reference: Optional[str] = None,
        product_uuid: Optional[str] = None,
        product_reference: Optional[str] = None,
        product_name: Optional[str] = None,
        description: Optional[str] = None,
        price_usd: Optional[Money] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        customer_reference: Optional[str] = None,
        expires_in_minutes: Optional[int] = None,
        metadata: Optional[Mapping[str, str]] = None,
        frequency: Optional[Duration] = None,
        trial_period: Optional[Duration] = None,
        min_periods: Optional[int] = None,
        fees: Optional[CheckoutFees] = None,
        options: Optional[RequestOptions] = None,
    ) -> CreatedCheckoutSession:
        """Open a subscription checkout session (``POST /checkout-sessions/subscription``, 201)
        and return its link, its ``sub@…`` id and its expiry: the payment session's arguments,
        plus the terms, each optional over a subscription product's (the merged terms are
        validated as a product's are; without a product's terms, ``frequency`` is required).
        Sends an ``Idempotency-Key``; retried on transient failures.

        The :class:`~qbitflow.Subscription` exists, with the same id, once the customer signed
        (a free trial) or paid: act on ``subscription.created``.

        Args:
            reference: Your reference for the subscription (an order or customer id), kept on
                it: unique per space.
            product_name: An inline product's name (2 to 100 characters): the subscription uses
                a hidden product, shared by the space's inline products of the same name,
                description and price.
            price_usd: An inline product's price per period in USD, a decimal string: above 0, at
                most 2 decimals, at most 1,000,000. The API caps it at ``"5"`` in test mode and
                requires more than ``"0.25"`` for a live subscription (inline or its product's;
                ``details["min"]``).
            metadata: Your own data on the checkout, copied onto the subscription (then changed
                with ``subscriptions.update``) and into its webhooks; the rules of
                :meth:`create_payment`'s ``metadata``.
            frequency: How often it bills: at least 1 unit, at most 1 year (the API also
                requires at least 1 hour in live mode, 5 minutes in test mode). Optional over a
                subscription product's.
            trial_period: A free trial before the first bill (``Duration(value=0)``: none,
                removing a product's).
            min_periods: The periods the customer commits to before cancelling, at most 1000 (0:
                none, removing a product's).
            fees: Amounts added to the price (a tax, shipping, QBitFlow's processing fee), as
                for :meth:`create_payment`, shown to the customer line by line and locked with
                the price: every bill (the first one, at creation, and each next one) charges the
                price plus every line. The subscription keeps them as its ``fees``, its
                ``price_usd`` staying the price. The maximum per period and the allowance the
                subscriber signs are sized on that amount, and QBitFlow's fee is taken on it.
                ``None``: no lines of your own.

            The other arguments are :meth:`create_payment`'s.

        Raises:
            ValidationError: as :meth:`create_payment`, plus the API's 400 on ``frequency`` /
                ``trialPeriod`` (the frequency minimum is 1 hour live, 5 minutes test) and on
                ``priceUsd`` for a live subscription at ``"0.25"`` or less (``details["min"]``).
            PermissionDeniedError: a member's key needs the ``members.subscriptions`` policy
                (403 ``policy_disabled``).
            ConflictError: as :meth:`create_payment`.
        """
        v = Validator()
        _validate_session(
            v,
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price_usd,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
            metadata,
        )
        validate_terms(v, "", frequency, trial_period, min_periods, False)
        _validate_fees(v, fees)
        v.check()
        body = _session_body(
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price_usd,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
            metadata,
        )
        body.update(terms_body(frequency, trial_period, min_periods))
        if fees is not None:
            body["fees"] = fees_body(fees)
        endpoint = Endpoint("POST", "/checkout-sessions/subscription", body=body, idempotent=True)
        return self._call(CreatedCheckoutSession, endpoint, options)

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> CheckoutSessionStatus:
        """Where a checkout session stands (``GET /checkout-sessions/:uuid``; ``uuid`` is the
        session's ``pay@…`` or ``sub@…`` id, or its bare UUID): ``created`` (waiting for its
        customer), ``waitingConfirmation``, ``completed`` or ``expired`` (the only final ones). It
        covers both phases: the session, then the payment or subscription it created.

        A failed attempt is ``created`` with ``last_attempt`` set: the customer may still pay
        from the same checkout, so never cancel an order on it. An expired session answers
        ``expired`` for as long as QBitFlow keeps the record, then 404 like an unknown id or
        another space's session.
        """
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint("GET", pathf("/checkout-sessions/{}", uuid))
        return self._call(CheckoutSessionStatus, endpoint, options)

    def wait_for_completion(
        self,
        uuid: str,
        *,
        timeout: float = 600,
        interval: float = 3,
        options: Optional[RequestOptions] = None,
    ) -> CheckoutSessionStatus:
        """Poll :meth:`get` until the session is ``completed`` or ``expired``, and return that
        status. For scripts, tests and back-office jobs: **fulfil orders from the webhooks**
        (``payment.completed``), never by keeping a request waiting on this.

        Args:
            uuid: The session (``pay@…`` or ``sub@…``).
            timeout: Seconds to wait at most (default 600; 0 or less means the default). When
                it elapses first, the **last status seen** is returned (not final: check
                ``.status``). The last wait is shortened to the time left, then one last poll is
                made at the deadline.
            interval: Seconds between two polls (default 3; less than 1 counts as 1).

        Raises:
            ValidationError: a malformed uuid, or a ``timeout``/``interval`` that is not a
                number.
            Any error of :meth:`get` (a 404 included), as is.
        """
        check_path_tx_id("uuid", uuid)
        for name, value in (("timeout", timeout), ("interval", interval)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
                raise field_error(name, "must be a number of seconds")
        pause = max(float(interval), 1.0)
        transport = self._client._transport
        deadline = transport.monotonic() + (float(timeout) if timeout > 0 else 600.0)
        final = (CheckoutSessionStatusValue.COMPLETED, CheckoutSessionStatusValue.EXPIRED)
        while True:
            status = self.get(uuid, options=options)
            if status.status in final:
                return status
            remaining = deadline - transport.monotonic()
            if remaining <= 0:
                return status
            transport.sleep(min(pause, remaining))

    def expire(
        self, uuid: str, *, options: Optional[RequestOptions] = None
    ) -> CheckoutSessionStatus:
        """End a checkout session now (``POST /checkout-sessions/:uuid/expire``) and return its
        status, ``expired``, with ``expires_at`` the time it was expired (``checkout.expired``
        follows). Not retried.

        Raises:
            ConflictError: 409 ``tx_already_sent`` once the customer paid or is paying.
        """
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint("POST", pathf("/checkout-sessions/{}/expire", uuid))
        return self._call(CheckoutSessionStatus, endpoint, options)
