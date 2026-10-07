"""Products, customers and checkout sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Union

from .._transport import Endpoint, Query, RequestOptions, pathf
from .._validation import Validator, check_path_required, check_path_tx_id, check_path_uuid
from ..models.checkout import CheckoutSession, CheckoutSessionStatus
from ..models.common import Duration, Page
from ..models.resources import Customer, Product
from ._base import NOT_GIVEN, NotGiven, Service, compact, duration_body, iterate_pages

__all__ = [
    "SubscriptionTermsParams",
    "ProductsService",
    "CustomersService",
    "CheckoutSessionsService",
]


@dataclass
class SubscriptionTermsParams:
    """A subscription product's terms (``products.create`` / ``products.update``).

    Attributes:
        frequency: How often it bills: at least 1 unit, at most 1 year (the API also requires
            at least 1 hour in live mode, 5 minutes in test mode). Required on a create.
        trial_period: A free trial before the first bill (``Duration(0)``: none, removing one).
        min_periods: The periods the customer commits to before cancelling, at most 1000
            (0: none).
    """

    frequency: Optional[Duration] = None
    trial_period: Optional[Duration] = None
    min_periods: Optional[int] = None


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


class ProductsService(Service):
    """Products: one-time products, and subscription products with their terms
    (``client.products``)."""

    def list(
        self,
        *,
        include_hidden: bool = False,
        subscription: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> List[Product]:
        """The space's products (``GET /product``; not paginated).

        Args:
            include_hidden: List the hidden products too (``is_active`` False).
            subscription: Keep only the subscription products (True) or the one-time ones
                (False).
        """
        v = Validator()
        v.boolean("includeHidden", include_hidden)
        v.boolean("subscription", subscription)
        v.check()
        query = Query().flag("includeHidden", include_hidden).boolean("subscription", subscription)
        return self._call(List[Product], Endpoint("GET", "/product", query), options)

    def create(
        self,
        *,
        name: str,
        price: float,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        subscription: Optional[SubscriptionTermsParams] = None,
        options: Optional[RequestOptions] = None,
    ) -> Product:
        """Create a product (``POST /product``). Sends an ``Idempotency-Key``; retried on
        transient failures.

        Args:
            name: 2 to 100 characters, one line.
            price: In USD, above 0 (at most 5 in test mode).
            description: 2 to 500 characters.
            reference: Your reference, unique per space; generated when left out.
            subscription: Makes it a subscription product (``frequency`` required).

        Raises:
            ValidationError: an invalid input (nothing is sent), or the API's 400.
            ConflictError: 409 ``unique_violation`` (``details["field"]``: the reference).
        """
        v = Validator()
        if v.required("name", name):
            v.name("name", name, 2, 100)
        v.text("description", description, 2, 500)
        v.price("price", price)
        v.reference("reference", reference)
        terms = _validate_subscription(v, subscription, True)
        v.check()
        body = compact(name=name, description=description, price=price, reference=reference)
        body["name"], body["price"] = name, price
        if terms is not None:
            body["subscription"] = terms_body(
                terms.frequency, terms.trial_period, terms.min_periods
            )
        endpoint = Endpoint("POST", "/product", body=body, idempotent=True)
        return self._call(Product, endpoint, options)

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Product:
        """A product by its uuid (``GET /product/uuid/:uuid``)."""
        check_path_uuid("uuid", uuid)
        return self._call(Product, Endpoint("GET", pathf("/product/uuid/{}", uuid)), options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Product:
        """A product by its reference (``GET /product/reference/:reference``)."""
        check_path_required("reference", reference)
        endpoint = Endpoint("GET", pathf("/product/reference/{}", reference))
        return self._call(Product, endpoint, options)

    def update(
        self,
        uuid: str,
        *,
        name: Optional[str] = None,
        description: Union[str, None, NotGiven] = NOT_GIVEN,
        price: Optional[float] = None,
        is_active: Optional[bool] = None,
        subscription: Optional[SubscriptionTermsParams] = None,
        remove_subscription: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Product:
        """Update a product (``PUT /product/:uuid``): only the arguments given change. Not
        retried.

        Args:
            name: The new name.
            description: The new description; ``""`` (or ``None``) clears it, left out keeps it.
            price: The new price in USD, above 0: for new checkouts and subscribers only.
            is_active: False hides the product from ``products.list``, True lists it again.
            subscription: Sets (or changes) the subscription terms; a one-time product needs
                ``frequency``.
            remove_subscription: Makes it a one-time product (not with ``subscription``).
        """
        check_path_uuid("uuid", uuid)
        clear_description = _clearable(description)
        v = Validator()
        v.name("name", name, 2, 100)
        v.text("description", clear_description, 2, 500)
        if price is not None:
            v.price("price", price)
        v.boolean("isActive", is_active)
        v.boolean("removeSubscription", remove_subscription)
        terms = _validate_subscription(v, subscription, False)
        v.exclusive(
            "subscription",
            subscription is not None,
            "removeSubscription",
            bool(remove_subscription),
        )
        v.check()
        body = compact(name=name, price=price)
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
        endpoint = Endpoint("PUT", pathf("/product/{}", uuid), body=body)
        return self._call(Product, endpoint, options)

    def delete(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Delete a product (``DELETE /product/:uuid``). Its subscriptions go on: cancel them
        with ``subscriptions.cancel`` if the product is gone for good. Not retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/product/{}", uuid)), options)


class CustomersService(Service):
    """Customers (``client.customers``)."""

    def create(
        self,
        *,
        name: str,
        email: str,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        address: Optional[str] = None,
        reference: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Customer:
        """Create a customer (``POST /customer``). Sends an ``Idempotency-Key``; retried on
        transient failures.

        Args:
            name: The first name, 2 to 100 characters, one line.
            email: Stored lowercase, at most 254 characters.
            last_name: 1 to 100 characters, one line.
            phone_number: At most 32 characters: digits and ``. - ( )`` space, an optional +.
            address: At most 500 characters.
            reference: Your reference (e.g. your own customer id), unique per space.
        """
        v = Validator()
        if v.required("name", name):
            v.name("name", name, 2, 100)
        v.name("lastName", last_name, 1, 100)
        if v.required("email", email):
            v.email("email", email)
        v.phone("phoneNumber", phone_number)
        v.text("address", address, 0, 500)
        v.reference("reference", reference)
        v.check()
        body = compact(
            name=name,
            lastName=last_name,
            email=email,
            phoneNumber=phone_number,
            address=address,
            reference=reference,
        )
        endpoint = Endpoint("POST", "/customer", body=body, idempotent=True)
        return self._call(Customer, endpoint, options)

    def update(
        self,
        uuid: str,
        *,
        name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone_number: Union[str, None, NotGiven] = NOT_GIVEN,
        address: Union[str, None, NotGiven] = NOT_GIVEN,
        options: Optional[RequestOptions] = None,
    ) -> Customer:
        """Update a customer (``PUT /customer/:uuid``): only the arguments given change; the
        reference cannot be changed. Not retried.

        Args:
            phone_number: The new phone number; ``""`` (or ``None``) clears it, left out keeps it.
            address: The new address; ``""`` (or ``None``) clears it, left out keeps it.
        """
        check_path_uuid("uuid", uuid)
        phone = _clearable(phone_number)
        addr = _clearable(address)
        v = Validator()
        v.name("name", name, 2, 100)
        v.name("lastName", last_name, 1, 100)
        v.email("email", email)
        v.phone("phoneNumber", phone)
        v.text("address", addr, 0, 500)
        v.check()
        body = compact(name=name, lastName=last_name, email=email)
        if phone is not None:
            body["phoneNumber"] = phone
        if addr is not None:
            body["address"] = addr
        endpoint = Endpoint("PUT", pathf("/customer/{}", uuid), body=body)
        return self._call(Customer, endpoint, options)

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        email: Optional[str] = None,
        verified: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Customer]:
        """One page of the space's customers (``GET /customer/all``; page size 10 by default,
        at most 100).

        Args:
            email: Keep only the customers with this email, whatever its casing.
            verified: Keep only the customers the merchant created (True) or those created at
                checkout (False).
        """
        v = Validator()
        v.page(limit, cursor)
        v.email("email", email)
        v.boolean("verified", verified)
        v.check()
        query = Query().page(limit, cursor).string("email", email).boolean("verified", verified)
        return self._call(Page[Customer], Endpoint("GET", "/customer/all", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        email: Optional[str] = None,
        verified: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Customer]:
        """Every customer :meth:`list` returns, fetching the pages lazily and keeping the
        filters and the page size."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit, cursor=c, email=email, verified=verified, options=options
            ),
            cursor,
        )

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Customer:
        """A customer by its uuid (``GET /customer/uuid/:uuid``)."""
        check_path_uuid("uuid", uuid)
        return self._call(Customer, Endpoint("GET", pathf("/customer/uuid/{}", uuid)), options)

    def get_by_email(self, email: str, *, options: Optional[RequestOptions] = None) -> Customer:
        """A customer by its email (``GET /customer/email/:email``)."""
        check_path_required("email", email)
        endpoint = Endpoint("GET", pathf("/customer/email/{}", email))
        return self._call(Customer, endpoint, options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Customer:
        """A customer by its reference (``GET /customer/reference/:reference``)."""
        check_path_required("reference", reference)
        endpoint = Endpoint("GET", pathf("/customer/reference/{}", reference))
        return self._call(Customer, endpoint, options)

    def delete(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Delete a customer (``DELETE /customer/uuid/:uuid``). Not retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/customer/uuid/{}", uuid)), options)


def _validate_session(
    v: Validator,
    reference: Any,
    product_uuid: Any,
    product_reference: Any,
    product_name: Any,
    description: Any,
    price: Any,
    success_url: Any,
    cancel_url: Any,
    customer_uuid: Any,
    customer_reference: Any,
    expires_in_minutes: Any,
) -> None:
    """A checkout session's rules: the product choice, names, texts, references, URLs, the price
    and the lifetime."""
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

    # Exactly one of: productUuid, productReference, an inline product (any inline field counts).
    inline = bool(product_name) or price is not None or bool(description)
    chosen = sum(1 for given in (bool(product_uuid), bool(product_reference), inline) if given)
    if chosen != 1:
        v.add(
            "productUuid",
            "or productReference, or an inline product (productName and price), is required: "
            "exactly one of them",
        )
    elif inline:
        if not product_name:
            v.add("productName", "is required for an inline product")
        if price is None:
            v.add("price", "is required for an inline product")
        else:
            v.price("price", price)


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
        price: Optional[float] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        customer_reference: Optional[str] = None,
        expires_in_minutes: Optional[int] = None,
        options: Optional[RequestOptions] = None,
    ) -> CheckoutSession:
        """Create a one-time payment checkout session
        (``POST /transaction/session-checkout/new/payment``): send the customer to its ``link``.
        Sends an ``Idempotency-Key``; retried on transient failures.

        Name the product with **exactly one** of ``product_uuid``, ``product_reference``, or an
        inline product (``product_name`` + ``price``, ``description`` optional).

        Args:
            reference: Your reference for the payment (an order id): unique per space, 1 to 100
                of ``A-Z a-z 0-9 . _ : @ -``.
            success_url: Where the customer goes after paying (``{{UUID}}``: the session's id;
                ``{{TRANSACTION_TYPE}}``: payment or createSubscription).
            cancel_url: Where the customer goes after a cancelled or failed payment.
            customer_uuid: One of the space's customers.
            customer_reference: Your reference of the customer, kept on the payment.
            expires_in_minutes: The session's lifetime, 10 to 1440 (``None`` or 0: the default).

        Raises:
            ConflictError: 409 ``merchant_not_ready`` (``details["reason"]``), 409
                ``unique_violation`` (the reference).
        """
        v = Validator()
        _validate_session(
            v,
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
        )
        v.check()
        body = compact(
            reference=reference,
            productUuid=product_uuid,
            productReference=product_reference,
            productName=product_name,
            description=description,
            price=price,
            successUrl=success_url,
            cancelUrl=cancel_url,
            customerUuid=customer_uuid,
            customerReference=customer_reference,
            expiresInMinutes=expires_in_minutes or None,
        )
        endpoint = Endpoint(
            "POST", "/transaction/session-checkout/new/payment", body=body, idempotent=True
        )
        return self._call(CheckoutSession, endpoint, options)

    def create_subscription(
        self,
        *,
        reference: Optional[str] = None,
        product_uuid: Optional[str] = None,
        product_reference: Optional[str] = None,
        product_name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[float] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        customer_reference: Optional[str] = None,
        expires_in_minutes: Optional[int] = None,
        frequency: Optional[Duration] = None,
        trial_period: Optional[Duration] = None,
        min_periods: Optional[int] = None,
        options: Optional[RequestOptions] = None,
    ) -> CheckoutSession:
        """Create a subscription checkout session
        (``POST /transaction/session-checkout/new/subscription``): the payment session's
        arguments, plus the terms, each optional over a subscription product's. Sends an
        ``Idempotency-Key``; retried on transient failures.

        Args:
            frequency: How often it bills: at least 1 unit, at most 1 year (the API also
                requires at least 1 hour in live mode, 5 minutes in test mode).
            trial_period: A free trial before the first bill (``Duration(0)``: none, removing a
                product's).
            min_periods: The periods the customer commits to before cancelling, at most 1000.
        """
        v = Validator()
        _validate_session(
            v,
            reference,
            product_uuid,
            product_reference,
            product_name,
            description,
            price,
            success_url,
            cancel_url,
            customer_uuid,
            customer_reference,
            expires_in_minutes,
        )
        validate_terms(v, "", frequency, trial_period, min_periods, False)
        v.check()
        body = compact(
            reference=reference,
            productUuid=product_uuid,
            productReference=product_reference,
            productName=product_name,
            description=description,
            price=price,
            successUrl=success_url,
            cancelUrl=cancel_url,
            customerUuid=customer_uuid,
            customerReference=customer_reference,
            expiresInMinutes=expires_in_minutes or None,
        )
        body.update(terms_body(frequency, trial_period, min_periods))
        endpoint = Endpoint(
            "POST", "/transaction/session-checkout/new/subscription", body=body, idempotent=True
        )
        return self._call(CheckoutSession, endpoint, options)

    def get_status(
        self, uuid: str, *, options: Optional[RequestOptions] = None
    ) -> CheckoutSessionStatus:
        """A checkout session's status (``GET /transaction/session-checkout/:uuid/status``;
        ``uuid`` is ``pay@…`` or ``sub@…``)."""
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint("GET", pathf("/transaction/session-checkout/{}/status", uuid))
        return self._call(CheckoutSessionStatus, endpoint, options)

    def expire(
        self, uuid: str, *, options: Optional[RequestOptions] = None
    ) -> CheckoutSessionStatus:
        """End a session early (``POST /transaction/session-checkout/:uuid/expire``); it answers
        its status and ``checkout.expired`` follows. Once the customer paid or is paying: 409
        ``tx_already_sent``. Not retried."""
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint("POST", pathf("/transaction/session-checkout/{}/expire", uuid))
        return self._call(CheckoutSessionStatus, endpoint, options)
