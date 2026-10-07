"""Payments, failures, subscriptions and refunds."""

from __future__ import annotations

from datetime import datetime
from typing import Iterator, List, Optional, Union

from .._transport import Endpoint, Query, RequestOptions, decode, pathf
from .._validation import Validator, check_path_required, check_path_tx_id, known
from ..models.common import Page
from ..models.enums import (
    CombinedPaymentSource,
    FailureCategory,
    FailureKind,
    SubscriptionStatus,
)
from ..models.payments import Bill, CombinedPayment, Failure, Payment
from ..models.resources import Refund
from ..models.subscriptions import BillingState, Subscription, SubscriptionCancellation
from ._base import Service, compact, iterate_pages

__all__ = ["PaymentsService", "FailuresService", "SubscriptionsService", "RefundsService"]


def _filters(
    query: Query,
    customer_uuid: Optional[str],
    product_uuid: Optional[str],
    created_after: Optional[datetime],
    created_before: Optional[datetime],
    include_members: bool,
    user_uuid: Optional[str],
) -> Query:
    """The filters every transaction list shares."""
    return (
        query.string("customerUuid", customer_uuid)
        .string("productUuid", product_uuid)
        .time("createdAfter", created_after)
        .time("createdBefore", created_before)
        .flag("includeMembers", include_members)
        .string("userUuid", user_uuid)
    )


def _read_query(include_members: bool) -> Query:
    v = Validator()
    v.boolean("includeMembers", include_members)
    v.check()
    return Query().flag("includeMembers", include_members)


class PaymentsService(Service):
    """One-time payments, and the combined feed of payments and bills (``client.payments``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Payment]:
        """One page of the confirmed one-time payments (``GET /transaction/payments``; newest
        first, page size 10 by default, at most 50).

        Args:
            customer_uuid: Keep only this customer's.
            product_uuid: Keep only this product's.
            created_after: Keep only those created after this instant (excluded; aware datetime).
            created_before: Keep only those created before this instant (excluded).
            include_members: Add the members' rows (organization key); not with ``user_uuid``.
            user_uuid: Read one member's rows (organization key); not with ``include_members``.
            refunded: Keep only the payments with (True) or without (False) an approved refund.
        """
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.boolean("refunded", refunded)
        v.check()
        query = _filters(
            Query().page(limit, cursor),
            customer_uuid,
            product_uuid,
            created_after,
            created_before,
            include_members,
            user_uuid,
        ).boolean("refunded", refunded)
        return self._call(Page[Payment], Endpoint("GET", "/transaction/payments", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Payment]:
        """Every payment :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                customer_uuid=customer_uuid,
                product_uuid=product_uuid,
                created_after=created_after,
                created_before=created_before,
                include_members=include_members,
                user_uuid=user_uuid,
                refunded=refunded,
                options=options,
            ),
            cursor,
        )

    def list_combined(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        source: Union[CombinedPaymentSource, str, None] = None,
        subscription_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[CombinedPayment]:
        """One page of the combined feed of one-time payments and subscription bills
        (``GET /transaction/payments/combined``; newest first, page size 10, at most 50): the
        :meth:`list` filters plus ``source`` (``payment`` or ``subscriptionHistory``) and
        ``subscription_uuid`` (one subscription's bills, ``sub@…``)."""
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.one_of("source", source, known(CombinedPaymentSource))
        v.tx_id("subscriptionUuid", subscription_uuid)
        v.boolean("refunded", refunded)
        v.check()
        query = (
            _filters(
                Query().page(limit, cursor),
                customer_uuid,
                product_uuid,
                created_after,
                created_before,
                include_members,
                user_uuid,
            )
            .string("source", source)
            .string("subscriptionUuid", subscription_uuid)
            .boolean("refunded", refunded)
        )
        endpoint = Endpoint("GET", "/transaction/payments/combined", query)
        return self._call(Page[CombinedPayment], endpoint, options)

    def iterate_combined(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        source: Union[CombinedPaymentSource, str, None] = None,
        subscription_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[CombinedPayment]:
        """Every row :meth:`list_combined` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list_combined(
                limit=limit,
                cursor=c,
                customer_uuid=customer_uuid,
                product_uuid=product_uuid,
                created_after=created_after,
                created_before=created_before,
                include_members=include_members,
                user_uuid=user_uuid,
                source=source,
                subscription_uuid=subscription_uuid,
                refunded=refunded,
                options=options,
            ),
            cursor,
        )

    def get(
        self,
        uuid: str,
        *,
        include_members: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Payment:
        """A payment by its id (``GET /transaction/payment/:uuid``; ``pay@…``).

        Args:
            include_members: Read a member's payment from the organization's space
                (organization key without ``on_behalf_of``).
        """
        check_path_tx_id("uuid", uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/transaction/payment/{}", uuid), query)
        return self._call(Payment, endpoint, options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Payment:
        """A payment by its checkout's reference
        (``GET /transaction/payment/reference/:reference``)."""
        check_path_required("reference", reference)
        endpoint = Endpoint("GET", pathf("/transaction/payment/reference/{}", reference))
        return self._call(Payment, endpoint, options)


class FailuresService(Service):
    """The failed attempts to pay a checkout or a bill (``client.failures``). They never moved
    money and are not final: the customer can try again."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        kind: Union[FailureKind, str, None] = None,
        category: Union[FailureCategory, str, None] = None,
        subscription_uuid: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Failure]:
        """One page of the failures log (``GET /transaction/failures``; newest first, page size
        10, at most 50): the payment filters plus ``kind``, ``category`` and
        ``subscription_uuid``."""
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.one_of("kind", kind, known(FailureKind))
        v.one_of("category", category, known(FailureCategory))
        v.tx_id("subscriptionUuid", subscription_uuid)
        v.check()
        query = (
            _filters(
                Query().page(limit, cursor),
                customer_uuid,
                product_uuid,
                created_after,
                created_before,
                include_members,
                user_uuid,
            )
            .string("kind", kind)
            .string("category", category)
            .string("subscriptionUuid", subscription_uuid)
        )
        return self._call(Page[Failure], Endpoint("GET", "/transaction/failures", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        kind: Union[FailureKind, str, None] = None,
        category: Union[FailureCategory, str, None] = None,
        subscription_uuid: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Failure]:
        """Every failure :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                customer_uuid=customer_uuid,
                product_uuid=product_uuid,
                created_after=created_after,
                created_before=created_before,
                include_members=include_members,
                user_uuid=user_uuid,
                kind=kind,
                category=category,
                subscription_uuid=subscription_uuid,
                options=options,
            ),
            cursor,
        )


class SubscriptionsService(Service):
    """Subscriptions and their bills (``client.subscriptions``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        status: Union[SubscriptionStatus, str, None] = None,
        reference: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Subscription]:
        """One page of the subscriptions (``GET /transaction/subscriptions``; page size 20, at
        most 100): the payment filters plus ``status`` and ``reference``."""
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.one_of("status", status, known(SubscriptionStatus))
        v.reference("reference", reference)
        v.check()
        query = (
            _filters(
                Query().page(limit, cursor),
                customer_uuid,
                product_uuid,
                created_after,
                created_before,
                include_members,
                user_uuid,
            )
            .string("status", status)
            .string("reference", reference)
        )
        endpoint = Endpoint("GET", "/transaction/subscriptions", query)
        return self._call(Page[Subscription], endpoint, options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        product_uuid: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        include_members: bool = False,
        user_uuid: Optional[str] = None,
        status: Union[SubscriptionStatus, str, None] = None,
        reference: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Subscription]:
        """Every subscription :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                customer_uuid=customer_uuid,
                product_uuid=product_uuid,
                created_after=created_after,
                created_before=created_before,
                include_members=include_members,
                user_uuid=user_uuid,
                status=status,
                reference=reference,
                options=options,
            ),
            cursor,
        )

    def get(
        self,
        uuid: str,
        *,
        include_members: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Subscription:
        """A subscription by its id (``GET /transaction/subscription/:uuid``; ``sub@…``), in any
        status, cancelled ones included. Before its checkout completes it is a 404."""
        check_path_tx_id("uuid", uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/transaction/subscription/{}", uuid), query)
        return self._call(Subscription, endpoint, options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Subscription:
        """A subscription by its checkout's reference
        (``GET /transaction/subscription/reference/subscription/:reference``)."""
        check_path_required("reference", reference)
        endpoint = Endpoint(
            "GET", pathf("/transaction/subscription/reference/subscription/{}", reference)
        )
        return self._call(Subscription, endpoint, options)

    def list_bills(
        self,
        uuid: str,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Bill]:
        """One page of a subscription's paid bills, newest first
        (``GET /transaction/subscription/:uuid/bills``; page size 20, at most 100)."""
        check_path_tx_id("uuid", uuid)
        v = Validator()
        v.page(limit, cursor)
        v.check()
        endpoint = Endpoint(
            "GET", pathf("/transaction/subscription/{}/bills", uuid), Query().page(limit, cursor)
        )
        return self._call(Page[Bill], endpoint, options)

    def iterate_bills(
        self,
        uuid: str,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Bill]:
        """Every bill :meth:`list_bills` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list_bills(uuid, limit=limit, cursor=c, options=options), cursor
        )

    def get_bill(
        self,
        bill_uuid: str,
        *,
        include_members: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Bill:
        """A bill by its id (``GET /transaction/subscription/bill/:uuid``; ``sub-hist@…``)."""
        check_path_tx_id("billUuid", bill_uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/transaction/subscription/bill/{}", bill_uuid), query)
        return self._call(Bill, endpoint, options)

    def get_public_history(
        self, subscription_uuid: str, *, options: Optional[RequestOptions] = None
    ) -> List[Bill]:
        """The 10 latest bills as the customer's page shows them
        (``GET /transaction/subscription/history/:subscriptionUuid``, a public route). The fields
        only the merchant sees (``metadata``, ``customer_uuid``, ``customer_reference``,
        ``user_uuid``, ``paid_min_units``, ``refund``…) are empty here: use :meth:`list_bills`
        for full bills."""
        check_path_tx_id("subscriptionUuid", subscription_uuid)
        endpoint = Endpoint("GET", pathf("/transaction/subscription/history/{}", subscription_uuid))
        return self._call(List[Bill], endpoint, options)

    def cancel(
        self,
        uuid: str,
        *,
        immediate: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> SubscriptionCancellation:
        """Cancel a subscription without its customer signing
        (``POST /transaction/subscription/processing/force-cancel/:uuid``). Not retried.

        Args:
            immediate: True (the default) cancels now (``cancelled``, reason ``merchant``);
                False stops it now and cancels it at the end of the period paid for.

        Returns:
            The subscription, and ``pending`` True when the API answered 202: the on-chain
            cancellation is still confirming and the status is not updated yet.
        """
        check_path_tx_id("uuid", uuid)
        v = Validator()
        v.boolean("immediate", immediate)
        v.check()
        endpoint = Endpoint(
            "POST",
            pathf("/transaction/subscription/processing/force-cancel/{}", uuid),
            Query().boolean("immediate", immediate),
        )
        resp = self._send(endpoint, options)
        subscription = decode(Subscription, resp)
        return SubscriptionCancellation(subscription=subscription, pending=resp.status == 202)

    def execute_test_billing(
        self, uuid: str, *, options: Optional[RequestOptions] = None
    ) -> BillingState:
        """Bill a test-mode subscription now
        (``POST /transaction/subscription/processing/execute-billing/:uuid``): test mode only
        (400 for a live subscription; 409 ``payment_not_due`` before its next billing date). Not
        retried."""
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint(
            "POST", pathf("/transaction/subscription/processing/execute-billing/{}", uuid)
        )
        return self._call(BillingState, endpoint, options)


def _refund_query(
    include_members: Optional[bool], user_uuid: Optional[str], held: Optional[bool]
) -> Query:
    v = Validator()
    v.boolean("includeMembers", include_members)
    v.uuid("userUuid", user_uuid)
    v.boolean("held", held)
    v.exclusive("includeMembers", include_members is True, "userUuid", bool(user_uuid))
    v.check()
    return (
        Query()
        .boolean("includeMembers", include_members)
        .string("userUuid", user_uuid)
        .boolean("held", held)
    )


class RefundsService(Service):
    """Refunds (``client.refunds``)."""

    def list(
        self,
        *,
        include_members: Optional[bool] = None,
        user_uuid: Optional[str] = None,
        held: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> List[Refund]:
        """The refunds waiting for an answer (``GET /transaction/refunds/all``; not paginated).

        Args:
            include_members: Add the members' refunds: the API's default is True from the
                organization's space (False from a member's, where True is refused). Not with
                ``user_uuid``.
            user_uuid: Read one member's refunds (organization key).
            held: Keep only the refunds of held (True) or not held (False) transactions.
        """
        query = _refund_query(include_members, user_uuid, held)
        return self._call(List[Refund], Endpoint("GET", "/transaction/refunds/all", query), options)

    def list_inactive(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_members: Optional[bool] = None,
        user_uuid: Optional[str] = None,
        held: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Refund]:
        """One page of the answered refunds, approved or rejected
        (``GET /transaction/refunds/all/inactive``; page size 10, at most 50)."""
        v = Validator()
        v.page(limit, cursor)
        v.check()
        query = _refund_query(include_members, user_uuid, held).page(limit, cursor)
        endpoint = Endpoint("GET", "/transaction/refunds/all/inactive", query)
        return self._call(Page[Refund], endpoint, options)

    def iterate_inactive(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_members: Optional[bool] = None,
        user_uuid: Optional[str] = None,
        held: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Refund]:
        """Every refund :meth:`list_inactive` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list_inactive(
                limit=limit,
                cursor=c,
                include_members=include_members,
                user_uuid=user_uuid,
                held=held,
                options=options,
            ),
            cursor,
        )

    def initiate(
        self,
        *,
        tx_uuid: str,
        refund_percent: Optional[float] = None,
        reason: Optional[str] = None,
        merchant_message: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Refund:
        """Start a refund of a payment (``pay@…``) or a bill (``sub-hist@…``)
        (``POST /transaction/refunds/initiate``). It creates a **pending** refund: no money moves
        until you sign the transfer in the dashboard. Sends an ``Idempotency-Key``; retried on
        transient failures.

        Args:
            tx_uuid: The payment or bill to refund.
            refund_percent: The share of what the customer paid to send back: above 0, at most
                100, at most 2 decimals (``None`` = 100).
            reason: Why you refund (at most 500 characters).
            merchant_message: A note to the customer (at most 500 characters).

        Raises:
            ConflictError: 409 ``refund_already_exists`` (``details["refundUuid"]``), 409
                ``held_funds_released``.
        """
        v = Validator()
        if v.required("txUuid", tx_uuid):
            v.tx_id("txUuid", tx_uuid)
        if refund_percent is not None:
            v.percent("refundPercent", refund_percent, 100, True)
        v.text("reason", reason, 0, 500)
        v.text("merchantMessage", merchant_message, 0, 500)
        v.check()
        body = compact(
            txUuid=tx_uuid,
            refundPercent=refund_percent,
            reason=reason,
            merchantMessage=merchant_message,
        )
        endpoint = Endpoint("POST", "/transaction/refunds/initiate", body=body, idempotent=True)
        return self._call(Refund, endpoint, options)
