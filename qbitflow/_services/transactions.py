"""Payments, the transactions feed, failures, subscriptions and refunds."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Union

from .._transport import Endpoint, Query, RequestOptions, decode, pathf
from .._validation import Money, Validator, check_path_tx_id, known
from ..models.common import Page
from ..models.enums import (
    FailureCategory,
    FailureKind,
    RefundStatus,
    SubscriptionStatus,
    TransactionKind,
)
from ..models.payments import Bill, Failure, Payment, Transaction
from ..models.resources import Refund
from ..models.subscriptions import Subscription, SubscriptionCancellation, TestBill
from ._base import Service, compact, iterate_pages, metadata_body, money

__all__ = [
    "PaymentsService",
    "TransactionsService",
    "FailuresService",
    "SubscriptionsService",
    "RefundsService",
]

#: The most statuses ``refunds.list(status=…)`` may name.
MAX_REFUND_STATUSES = 5


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
    """The options of the reads by id that can reach a member's row."""
    v = Validator()
    v.boolean("includeMembers", include_members)
    v.check()
    return Query().flag("includeMembers", include_members)


class PaymentsService(Service):
    """One-time payments (``client.payments``). The feed of payments and bills together is
    ``client.transactions``."""

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
        reference: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Payment]:
        """One page of the space's confirmed one-time payments (``GET /payments``; newest first,
        page size 20 by default, at most 100). A payment exists once its transaction is
        confirmed. :meth:`iterate` walks every page.

        Args:
            limit: The page size (the API's default 20 when ``None``, at most 100).
            cursor: The previous page's ``next_cursor``, verbatim; ``None`` for the first page.
            customer_uuid: Keep only this customer's.
            product_uuid: Keep only this product's.
            created_after: Keep only those created after this instant (excluded; an aware
                datetime).
            created_before: Keep only those created before this instant (excluded).
            include_members: Add the members' rows (organization key without ``on_behalf_of``);
                not with ``user_uuid``.
            user_uuid: Read one member's rows (organization key); not with ``include_members``.
            reference: Keep only the payment with this reference (set on its checkout): a page of
                0 or 1 payment per space read (:meth:`get_by_reference` reads it).
            refunded: Keep only the payments with (True) or without (False) an approved refund.
        """
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.reference("reference", reference)
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
            .string("reference", reference)
            .boolean("refunded", refunded)
        )
        return self._call(Page[Payment], Endpoint("GET", "/payments", query), options)

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
        reference: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Payment]:
        """Every payment :meth:`list` returns, fetching the pages lazily from ``cursor`` (or the
        first page) and keeping the filters and the page size."""
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
                reference=reference,
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
        """A one-time payment by its id (``GET /payments/:uuid``; ``pay@…`` or the bare UUID).
        A payment not confirmed yet (read its checkout session), or another space's, is a
        :class:`~qbitflow.NotFoundError`.

        Args:
            include_members: Read a member's payment from the organization's space
                (organization key without ``on_behalf_of``; 400 from a member's space).
        """
        check_path_tx_id("uuid", uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/payments/{}", uuid), query)
        return self._call(Payment, endpoint, options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Payment:
        """The space's one-time payment with the reference given to its checkout session: it
        runs :meth:`list`'s reference filter (``GET /payments?reference=``) and returns its one
        payment.

        Raises:
            ValidationError: the reference is not 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``
                (nothing is sent).
            NotFoundError: no payment has that reference (none, or not confirmed yet: status
                404, code ``not_found``).
        """
        return self._get_by_reference(
            Payment, "/payments", "payment", reference, lambda p: p.reference, options
        )


class TransactionsService(Service):
    """The transactions feed: the one-time payments and the subscriptions' bills together, each
    row with its ``type`` (``client.transactions``)."""

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
        type: Union[TransactionKind, str, None] = None,
        subscription_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Transaction]:
        """One page of the transactions feed (``GET /transactions``; newest first, page size 20
        by default, at most 100): the one-time payments and the subscriptions' bills together,
        each row with its ``type`` (``payment`` or ``bill``). It takes
        :meth:`PaymentsService.list`'s filters (``reference`` excepted) plus ``type``,
        ``subscription_uuid`` and ``refunded``. :meth:`iterate` walks every page.

        Args:
            type: Keep only the one-time payments (``payment``) or only the subscriptions' bills
                (``bill``).
            subscription_uuid: Keep only this subscription's bills (``sub@…`` or the bare UUID).
            refunded: Keep only the rows with (True) or without (False) an approved refund.
        """
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.one_of("type", type, known(TransactionKind))
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
            .string("type", type)
            .string("subscriptionUuid", subscription_uuid)
            .boolean("refunded", refunded)
        )
        return self._call(Page[Transaction], Endpoint("GET", "/transactions", query), options)

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
        type: Union[TransactionKind, str, None] = None,
        subscription_uuid: Optional[str] = None,
        refunded: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Transaction]:
        """Every row :meth:`list` returns, fetching the pages lazily and keeping the filters and
        the page size."""
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
                type=type,
                subscription_uuid=subscription_uuid,
                refunded=refunded,
                options=options,
            ),
            cursor,
        )


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
        """One page of the failed payment attempts (``GET /payment-failures``; newest first, page
        size 20 by default, at most 100): :meth:`PaymentsService.list`'s filters (``reference``
        and ``refunded`` excepted) plus ``kind``, ``category`` and ``subscription_uuid``.

        Args:
            kind: Keep only one kind: ``payment``, ``subscriptionCheckout`` or ``bill``.
            category: Keep only one category (:class:`~qbitflow.FailureCategory`).
            subscription_uuid: Keep only this subscription's bills (``sub@…``).
        """
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
        return self._call(Page[Failure], Endpoint("GET", "/payment-failures", query), options)

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
        """Every failure :meth:`list` returns, fetching the pages lazily and keeping the filters
        and the page size."""
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
    """Subscriptions and their bills (``client.subscriptions``): read them, update their
    metadata, cancel them, and run a test bill. Grant access while
    ``now < current_period_end``, whatever the status (:meth:`Subscription.has_access`)."""

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
        """One page of the space's subscriptions (``GET /subscriptions``; newest first,
        cancelled ones included, page size 20 by default, at most 100). A checkout not completed
        yet is no subscription. :meth:`PaymentsService.list`'s filters (``refunded`` excepted)
        plus ``status``.

        Args:
            status: Keep only those in this status (cancelled ones are listed unless filtered
                out). Not checked against the known statuses: a newer one is sent as is.
            reference: Keep only the one with this reference (a page of 0 or 1 subscription;
                :meth:`get_by_reference` reads it).
        """
        v = Validator()
        v.page(limit, cursor)
        v.list_filters(
            customer_uuid, product_uuid, created_after, created_before, include_members, user_uuid
        )
        v.string("status", status)
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
        return self._call(Page[Subscription], Endpoint("GET", "/subscriptions", query), options)

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
        """Every subscription :meth:`list` returns, fetching the pages lazily and keeping the
        filters and the page size."""
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
        """A subscription by its id (``GET /subscriptions/:uuid``; ``sub@…`` or the bare UUID),
        whatever its status (a cancelled one too). Before its checkout completes it is a
        :class:`~qbitflow.NotFoundError`: read the checkout session instead.

        Args:
            include_members: Read a member's from the organization's space (organization key
                without ``on_behalf_of``).
        """
        check_path_tx_id("uuid", uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/subscriptions/{}", uuid), query)
        return self._call(Subscription, endpoint, options)

    def get_by_reference(
        self, reference: str, *, options: Optional[RequestOptions] = None
    ) -> Subscription:
        """The space's subscription with the reference given to its checkout session, whatever
        its status: it runs :meth:`list`'s reference filter (``GET /subscriptions?reference=``)
        and returns its one subscription.

        Raises:
            ValidationError: the reference is not 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``
                (nothing is sent).
            NotFoundError: no subscription has that reference (status 404, code ``not_found``).
        """
        return self._get_by_reference(
            Subscription,
            "/subscriptions",
            "subscription",
            reference,
            lambda s: s.reference,
            options,
        )

    def update(
        self,
        uuid: str,
        *,
        metadata: Optional[Mapping[str, str]] = None,
        options: Optional[RequestOptions] = None,
    ) -> Subscription:
        """Change a subscription's metadata (``PATCH /subscriptions/:uuid``), cancelled ones too,
        and return the subscription. Its price and terms are locked at signup; its status changes
        through its actions (:meth:`cancel`, its customer's pause and resume). Not retried.

        Args:
            metadata: Merged into the subscription's: a key set to a value sets it, a key set to
                ``""`` deletes it, keys not named are kept (``None``: unchanged). At most 50 keys
                once merged (the API's check); each key 1 to 40 of ``A-Z a-z 0-9 _ - . :``, each
                value at most 500 characters without control or bidirectional characters.

        Raises:
            PermissionDeniedError: a member's key needs the organization's
                ``members.subscriptions`` policy (403 ``policy_disabled``).
        """
        check_path_tx_id("uuid", uuid)
        v = Validator()
        v.metadata("metadata", metadata)
        v.check()
        body: Dict[str, Any] = {}
        metadata_body(body, metadata)
        endpoint = Endpoint("PATCH", pathf("/subscriptions/{}", uuid), body=body)
        return self._call(Subscription, endpoint, options)

    def list_bills(
        self,
        uuid: str,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Bill]:
        """One page of a subscription's paid bills (``GET /subscriptions/:uuid/bills``; newest
        first, page size 20 by default, at most 100). :meth:`iterate_bills` walks every page."""
        check_path_tx_id("uuid", uuid)
        v = Validator()
        v.page(limit, cursor)
        v.check()
        endpoint = Endpoint(
            "GET", pathf("/subscriptions/{}/bills", uuid), Query().page(limit, cursor)
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
        """Every bill of a subscription, fetching the pages lazily and keeping the page size."""
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
        """One bill by its id (``GET /bills/:uuid``; ``sub-hist@…`` or the bare UUID).

        Args:
            include_members: Read a member's from the organization's space.
        """
        check_path_tx_id("billUuid", bill_uuid)
        query = _read_query(include_members)
        endpoint = Endpoint("GET", pathf("/bills/{}", bill_uuid), query)
        return self._call(Bill, endpoint, options)

    def cancel(
        self,
        uuid: str,
        *,
        immediate: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> SubscriptionCancellation:
        """Cancel a subscription without its customer signing
        (``POST /subscriptions/:uuid/cancel``). Not retried.

        Args:
            immediate: ``None`` or True (the default) cancels it at once (status ``cancelled``,
                ``cancellation_reason`` ``merchant``); False stops it now (status ``stopped``,
                never billed again) and cancels it when its paid period ends
                (``next_billing_at``). A trial is cancelled immediately only (False: 400).

        Returns:
            The subscription as the cancellation left it, and ``pending`` True when the API
            answered 202: the on-chain cancel is still confirming, the status is not updated
            yet, and ``subscription.statusChanged`` tells the end (the cancellation goes on
            whatever happens).

        Raises:
            NotFoundError: a cancelled or another space's subscription.
            ConflictError: 409 ``subscription_already_stopped_or_inactive`` (``immediate=False``
                on a stopped one); 409 ``tx_already_sent`` while a cancellation runs.
            BadRequestError: ``immediate=False`` on a trial.
        """
        check_path_tx_id("uuid", uuid)
        v = Validator()
        v.boolean("immediate", immediate)
        v.check()
        endpoint = Endpoint(
            "POST",
            pathf("/subscriptions/{}/cancel", uuid),
            Query().boolean("immediate", immediate),
        )
        resp = self._send(endpoint, options)
        subscription = decode(Subscription, resp)
        return SubscriptionCancellation(subscription=subscription, pending=resp.status == 202)

    def test_bill(self, uuid: str, *, options: Optional[RequestOptions] = None) -> TestBill:
        """Bill a test subscription now (``POST /subscriptions/:uuid/test-bill``) and return
        where the test bill stands once its attempt settled (done, waiting after a failure, or
        still running after 2 minutes). Its events are a live bill's. Not retried.

        Raises:
            BadRequestError: a live subscription (400 ``test_mode_only``: test mode only).
            ConflictError: 409 ``payment_not_due``, a bill not due yet.
        """
        check_path_tx_id("uuid", uuid)
        endpoint = Endpoint("POST", pathf("/subscriptions/{}/test-bill", uuid))
        return self._call(TestBill, endpoint, options)


def _validate_statuses(v: Validator, status: Any) -> None:
    """``refunds.list``'s ``status``: at most 5 of the known statuses (``status[i]`` for each
    failing entry)."""
    if status is None:
        return
    if isinstance(status, (str, bytes)) or not isinstance(status, (list, tuple)):
        v.add("status", "must be a list of refund statuses")
        return
    if len(status) > MAX_REFUND_STATUSES:
        v.add("status", f"must name at most {MAX_REFUND_STATUSES} statuses")
    allowed = known(RefundStatus)
    for i, entry in enumerate(status):
        field = f"status[{i}]"
        if entry is None or entry == "":
            v.add(field, "is required")
        else:
            v.one_of(field, entry, allowed)


class RefundsService(Service):
    """Refunds (``client.refunds``): list, read, and create them."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[Sequence[Union[RefundStatus, str]]] = None,
        tx_uuid: Optional[str] = None,
        held: Optional[bool] = None,
        include_members: Optional[bool] = None,
        user_uuid: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Refund]:
        """One page of the space's refunds (``GET /refunds``; newest first, page size 20 by
        default, at most 100). :meth:`iterate` walks every page.

        Args:
            limit: The page size (the API's default 20 when ``None``, at most 100).
            cursor: The previous page's ``next_cursor``, verbatim; ``None`` for the first page.
            status: Keep only the refunds in one of these statuses (at most 5 of pending,
                approved, rejected, cancelled, failed; sent as repeated ``?status=``); ``None`` or
                empty: every status. ``[RefundStatus.PENDING]`` lists the ones awaiting an
                answer.
            tx_uuid: Keep only the refund of this transaction (``pay@…``, ``sub-hist@…``, or the
                bare UUID).
            held: Keep only the refunds of payments held for a member (True: the ones the
                organization decides and sends), or only the others (False).
            include_members: Add the members' refunds, each naming its member: the API's default
                is True from the organization's space (False from a member's, where True is
                refused). Not with ``user_uuid``.
            user_uuid: Read one member's refunds (organization space only).
        """
        v = Validator()
        v.page(limit, cursor)
        _validate_statuses(v, status)
        v.tx_id("txUuid", tx_uuid)
        v.boolean("held", held)
        v.boolean("includeMembers", include_members)
        v.uuid("userUuid", user_uuid)
        v.exclusive("includeMembers", include_members is True, "userUuid", bool(user_uuid))
        v.check()
        query = (
            Query()
            .page(limit, cursor)
            .many("status", list(status) if status else None)
            .string("txUuid", tx_uuid)
            .boolean("held", held)
            .boolean("includeMembers", include_members)
            .string("userUuid", user_uuid)
        )
        return self._call(Page[Refund], Endpoint("GET", "/refunds", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[Sequence[Union[RefundStatus, str]]] = None,
        tx_uuid: Optional[str] = None,
        held: Optional[bool] = None,
        include_members: Optional[bool] = None,
        user_uuid: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Refund]:
        """Every refund :meth:`list` returns, fetching the pages lazily and keeping the filters
        and the page size."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit,
                cursor=c,
                status=status,
                tx_uuid=tx_uuid,
                held=held,
                include_members=include_members,
                user_uuid=user_uuid,
                options=options,
            ),
            cursor,
        )

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Refund:
        """A refund by its id (``GET /refunds/:uuid``; ``refund@…`` or the bare UUID). Another
        space's refund is a :class:`~qbitflow.NotFoundError`."""
        check_path_tx_id("uuid", uuid)
        return self._call(Refund, Endpoint("GET", pathf("/refunds/{}", uuid)), options)

    def create(
        self,
        *,
        tx_uuid: str,
        refund_percent: Optional[Money] = None,
        reason: Optional[str] = None,
        merchant_message: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Refund:
        """Start a refund of a payment (``pay@…``) or a bill (``sub-hist@…``) of the space
        (``POST /refunds``, 201). Sends an ``Idempotency-Key``; retried on transient failures.

        It creates a **pending** refund, a draft that blocks nothing: no money moves until you
        sign the transfer in the dashboard, and a new refund of the same transaction replaces it.
        ``refund_percent`` (default ``"100"``) applies to everything the customer paid, network
        fee included, rounded down.

        Args:
            tx_uuid: The payment or bill to refund (``pay@…``, ``sub-hist@…``, or its bare UUID).
            refund_percent: The share of what the customer paid to send back, a percent string
                (``"50"``) or a ``Decimal``: above 0, at most 100, at most 2 decimals (``None``:
                ``"100"``, everything the customer paid, network fee included).
            reason: Why you refund (at most 500 characters).
            merchant_message: A note to the customer (at most 500 characters).

        Raises:
            NotFoundError: a transaction outside the space.
            ValidationError: an invalid input (nothing is sent); the API's 400 (a refund
                rounding to nothing).
            ConflictError: 409 ``refund_already_exists`` (``details["refundUuid"]``: one refund
                per transaction, whatever it became; only an unsent draft gives way) or
                ``held_funds_released`` (a held payment already released to its member).
            PermissionDeniedError: a member's key needs the ``members.refunds`` policy (403
                ``policy_disabled``).
        """
        v = Validator()
        if v.required("txUuid", tx_uuid):
            v.tx_id("txUuid", tx_uuid)
        if refund_percent is not None and refund_percent != "":
            v.percent("refundPercent", refund_percent, 100, True)
        v.text("reason", reason, 0, 500)
        v.text("merchantMessage", merchant_message, 0, 500)
        v.check()
        body = compact(
            txUuid=tx_uuid,
            refundPercent=money(refund_percent),
            reason=reason,
            merchantMessage=merchant_message,
        )
        endpoint = Endpoint("POST", "/refunds", body=body, idempotent=True)
        return self._call(Refund, endpoint, options)
