"""Members, invitations, wallets, the accounting export and the currency catalog."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from .._transport import Endpoint, Query, RequestOptions, pathf
from .._validation import (
    Money,
    Validator,
    check_path_uuid,
    known,
)
from ..errors import field_error
from ..models.common import Currency, Page
from ..models.enums import InvitationStatus, Role
from ..models.resources import (
    AccountingEvent,
    CreatedInvitation,
    HeldFunds,
    Invitation,
    Member,
    MemberHeldFunds,
    Wallet,
)
from ._base import Service, iterate_pages, money

__all__ = [
    "MembersService",
    "InvitationsService",
    "WalletsService",
    "AccountingService",
    "CurrenciesService",
    "EXPORT_WINDOW_DAYS",
]


class MembersService(Service):
    """The organization's members (marketplace sellers), their trust and their held funds
    (``client.members``; organization key: 403 otherwise, also with ``on_behalf_of``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Member]:
        """One page of the organization's members in the key's mode (``GET /members``; by when
        they joined, page size 20 by default, at most 100). :meth:`iterate` walks every page."""
        v = Validator()
        v.page(limit, cursor)
        v.check()
        return self._call(
            Page[Member], Endpoint("GET", "/members", Query().page(limit, cursor)), options
        )

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Member]:
        """Every member :meth:`list` returns, fetching the pages lazily and keeping the page
        size."""
        return iterate_pages(lambda c: self.list(limit=limit, cursor=c, options=options), cursor)

    def get(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> Member:
        """A member by their user uuid (``GET /members/:userUuid``; :attr:`Member.user_uuid`,
        the value ``on_behalf_of`` takes). Someone who is not a member in the key's mode is a
        :class:`~qbitflow.NotFoundError`."""
        check_path_uuid("userUuid", user_uuid)
        return self._call(Member, Endpoint("GET", pathf("/members/{}", user_uuid)), options)

    def update(
        self,
        user_uuid: str,
        *,
        organization_fee_percent: Money,
        options: Optional[RequestOptions] = None,
    ) -> Member:
        """Change a member's organization fee in the key's mode (``PATCH /members/:userUuid``).
        A checkout already created keeps the fee it was created with; a running subscription's
        next bills take the new one. Not retried.

        Args:
            organization_fee_percent: The organization's fee on the member's payments from now
                on, a percent string from ``"0"`` to ``"50"`` with at most 2 decimals (or a
                ``Decimal``).
        """
        check_path_uuid("userUuid", user_uuid)
        v = Validator()
        if v.money_required("organizationFeePercent", organization_fee_percent):
            v.percent("organizationFeePercent", organization_fee_percent, 50)
        v.check()
        endpoint = Endpoint(
            "PATCH",
            pathf("/members/{}", user_uuid),
            body={"organizationFeePercent": money(organization_fee_percent)},
        )
        return self._call(Member, endpoint, options)

    def remove(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Remove a member from the key's mode (``DELETE /members/:userUuid``, 204): their API
        keys stop working at once and their checkouts stop taking payments; their data stays
        with the organization. Not retried.

        Raises:
            ConflictError: 409 ``held_funds_pending`` while the organization holds live funds for
                them (release them in the dashboard first).
        """
        check_path_uuid("userUuid", user_uuid)
        self._send(Endpoint("DELETE", pathf("/members/{}", user_uuid)), options)

    def trust(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> Member:
        """Make a member's new payments in the key's mode go to their own wallets
        (``POST /members/:userUuid/trust``) and return the member with ``trusted_at`` set. What
        the organization already holds for them stays held until released (in the dashboard).
        Not retried."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("POST", pathf("/members/{}/trust", user_uuid))
        return self._call(Member, endpoint, options)

    def list_held_funds(self, *, options: Optional[RequestOptions] = None) -> List[MemberHeldFunds]:
        """What the organization holds for each member in the key's mode, the longest held first
        (``GET /members/held-funds``; a bounded list)."""
        endpoint = Endpoint("GET", "/members/held-funds")
        return self._call_items(MemberHeldFunds, endpoint, options)

    def get_held_funds(
        self, user_uuid: str, *, options: Optional[RequestOptions] = None
    ) -> HeldFunds:
        """What the organization holds for one member in the key's mode, a removed member's too
        (``GET /members/:userUuid/held-funds``): the lines not paid out yet, oldest first, and
        their total in USD."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("GET", pathf("/members/{}/held-funds", user_uuid))
        return self._call(HeldFunds, endpoint, options)

    def get_own_held_funds(self, *, options: Optional[RequestOptions] = None) -> HeldFunds:
        """What the organization holds for the request's space (``GET /held-funds``): call it
        with a member's key, or ``on_behalf_of`` a member. Empty for the organization's own space
        (no ledgers, ``total_usd`` ``"0"``)."""
        return self._call(HeldFunds, Endpoint("GET", "/held-funds"), options)


class InvitationsService(Service):
    """Invitations to join the organization as a member (``client.invitations``; organization
    key). Team invitations are made from the dashboard."""

    def create(
        self,
        *,
        email: str,
        hold_funds: bool,
        organization_fee_percent: Optional[Money] = None,
        redirect_url: Optional[str] = None,
        send_email: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> CreatedInvitation:
        """Invite someone to join the organization as a member in the key's mode
        (``POST /invitations``, 201) and return the invitation with its ``link`` (also emailed,
        unless ``send_email`` is False). The SDK always sends ``role: user``: the team is invited
        from the dashboard. Sends an ``Idempotency-Key``; retried on transient failures. Rate
        limited (50 an hour per organization, emailed or not: beyond, a
        :class:`~qbitflow.RateLimitError` at once, the wait being over the SDK's 60 s retry cap).

        The person exists in the organization once they accepted: act on the ``member.joined``
        webhook (:attr:`MemberJoined.invitation_uuid`).

        Args:
            email: The person to invite, at most 254 characters.
            hold_funds: Required (always sent): True holds the member's payments until the
                organization trusts them (``members.trust``); False pays them directly.
            organization_fee_percent: The organization's fee on their payments, a percent string
                from ``"0"`` to ``"50"`` with at most 2 decimals (``None``: ``"0"``).
            redirect_url: Where the person goes once they accepted (with
                ``?invitationUuid=<uuid>``): a convenience, confirm with the ``member.joined``
                event.
            send_email: Whether QBitFlow emails the link to the person (``None``: True). False
                sends no invitation email: share the returned ``link`` yourself. Signing up
                through the link still emails the person a confirmation.

        Raises:
            ConflictError: 409 ``already_joined`` for someone already a member in that mode.
            RateLimitError: beyond 50 invitations an hour, emailed or not.
        """
        v = Validator()
        if v.required("email", email):
            v.email("email", email)
        given: Any = hold_funds  # checked as given: a caller may pass None
        if given is None:
            v.add("holdFunds", "is required")
        else:
            v.boolean("holdFunds", given)
        if organization_fee_percent is not None and organization_fee_percent != "":
            v.percent("organizationFeePercent", organization_fee_percent, 50)
        v.url("redirectUrl", redirect_url)
        v.boolean("sendEmail", send_email)
        v.check()
        body: Dict[str, Any] = {"email": email, "role": str(Role.USER), "holdFunds": hold_funds}
        fee = money(organization_fee_percent)
        if fee:
            body["organizationFeePercent"] = fee
        if redirect_url:
            body["redirectUrl"] = redirect_url
        if send_email is not None:
            body["sendEmail"] = send_email
        endpoint = Endpoint("POST", "/invitations", body=body, idempotent=True)
        return self._call(CreatedInvitation, endpoint, options)

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Union[InvitationStatus, str, None] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Invitation]:
        """One page of the organization's invitations (``GET /invitations``; newest first, page
        size 20 by default, at most 100), its team's (role ``admin``) included.

        Args:
            status: Keep only the invitations with this status (pending, accepted, revoked,
                expired).
        """
        v = Validator()
        v.page(limit, cursor)
        v.one_of("status", status, known(InvitationStatus))
        v.check()
        query = Query().page(limit, cursor).string("status", status)
        return self._call(Page[Invitation], Endpoint("GET", "/invitations", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Union[InvitationStatus, str, None] = None,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Invitation]:
        """Every invitation :meth:`list` returns, fetching the pages lazily and keeping the
        filter and the page size."""
        return iterate_pages(
            lambda c: self.list(limit=limit, cursor=c, status=status, options=options), cursor
        )

    def revoke(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Revoke an invitation (``DELETE /invitations/:uuid``, 204): its link no longer works.
        Not retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/invitations/{}", uuid)), options)


class WalletsService(Service):
    """The wallets and the currencies a space accepts (``client.wallets``). Wallets are added and
    removed in the dashboard."""

    def list(
        self, *, with_balances: bool = False, options: Optional[RequestOptions] = None
    ) -> List[Wallet]:
        """The request's space's wallets (``GET /wallets``; a bounded list), each with the
        currencies it accepts.

        Args:
            with_balances: Add each token wallet's balance, read on-chain (slower).
        """
        v = Validator()
        v.boolean("withBalances", with_balances)
        v.check()
        query = Query().flag("withBalances", with_balances)
        return self._call_items(Wallet, Endpoint("GET", "/wallets", query), options)

    def list_for_member(
        self, user_uuid: str, *, options: Optional[RequestOptions] = None
    ) -> List[Wallet]:
        """A member's wallets in the key's mode (``GET /members/:userUuid/wallets``; a bounded
        list). Organization key only (403 otherwise, also with ``on_behalf_of``); someone who is
        not a member is a :class:`~qbitflow.NotFoundError`."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("GET", pathf("/members/{}/wallets", user_uuid))
        return self._call_items(Wallet, endpoint, options)

    def list_accepted_currencies(
        self, *, user_uuid: Optional[str] = None, options: Optional[RequestOptions] = None
    ) -> List[Currency]:
        """The currencies the space's checkouts accept now
        (``GET /wallets/accepted-currencies``; a bounded list): check a seller is ready before
        opening their checkouts (none: their checkouts answer 409 ``merchant_not_ready``).

        Args:
            user_uuid: Read a member's (an organization key; 403 otherwise, also with
                ``on_behalf_of``); ``None`` for the request's space.
        """
        v = Validator()
        v.uuid("userUuid", user_uuid)
        v.check()
        query = Query().string("userUuid", user_uuid)
        endpoint = Endpoint("GET", "/wallets/accepted-currencies", query)
        return self._call_items(Currency, endpoint, options)


#: The most days one export request covers, both ends included: ``to <= from + 91 days``.
EXPORT_WINDOW_DAYS = 92


def _export_query(from_date: Union[str, date], to_date: Union[str, date], fmt: str) -> Query:
    """Check an export window (two ``YYYY-MM-DD`` dates, from <= to; the API enforces the 92-day
    maximum, both days included) and encode it with the format (json or csv)."""
    v = Validator()
    v.date_range("from", from_date, "to", to_date)
    v.check()
    start = from_date.isoformat() if isinstance(from_date, date) else from_date
    end = to_date.isoformat() if isinstance(to_date, date) else to_date
    return Query().string("from", start).string("to", end).string("format", fmt)


def _export_windows(
    from_date: Union[str, date], to_date: Union[str, date]
) -> List[Tuple[str, str]]:
    """Validate an export range like ``export_json``, then split it into consecutive windows of
    at most 92 days, both ends included (``[from, from + 91d]``, the next one starting the day
    after), on calendar dates (UTC, no time zones)."""
    v = Validator()
    v.date_range("from", from_date, "to", to_date)
    v.check()
    start = from_date if isinstance(from_date, date) else date.fromisoformat(from_date)
    end = to_date if isinstance(to_date, date) else date.fromisoformat(to_date)
    windows: List[Tuple[str, str]] = []
    while True:
        window_end = min(end, start + timedelta(days=EXPORT_WINDOW_DAYS - 1))
        windows.append((start.isoformat(), window_end.isoformat()))
        if window_end >= end:
            return windows
        start = window_end + timedelta(days=1)


def _csv_rows(text: str) -> str:
    """A CSV export without its header line (its line ending removed with it)."""
    newline = text.find("\n")
    return "" if newline < 0 else text[newline + 1 :]


class AccountingService(Service):
    """The accounting export (``client.accounting``)."""

    def export_json(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> List[AccountingEvent]:
        """The accounting events between two dates, both included
        (``GET /accounting/export?format=json``; a bounded list). The dates are the
        transactions' (their block's day, in UTC), so consecutive exports never miss nor repeat
        an event. Events are ordered by ``tx_time_utc``, then ``type``, then ``tx_uuid``.

        Args:
            from_date: The first day, ``YYYY-MM-DD`` (or a ``datetime.date``).
            to_date: The last day (included). The API allows at most 92 days, both included
                (400 ``validation_failed`` on ``to`` beyond, ``details["max"]`` 92:
                :meth:`export_json_range` splits longer ranges); the SDK checks the dates and
                ``from <= to`` before sending.
        """
        query = _export_query(from_date, to_date, "json")
        endpoint = Endpoint("GET", "/accounting/export", query)
        return self._call_items(AccountingEvent, endpoint, options)

    def export_csv(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> str:
        """The same export as :meth:`export_json`, as CSV text
        (``GET /accounting/export?format=csv``): the header row (:class:`AccountingEvent`'s wire
        keys, in its field order), then one row per event; nothing in range gives the header
        only. Amounts are plain numbers; an absent value is an empty cell; a cell starting with
        ``= + - @``, a tab or a CR gets a leading ``'``. Read the columns by header name. Errors
        are still JSON, and typed as usual."""
        query = _export_query(from_date, to_date, "csv")
        endpoint = Endpoint("GET", "/accounting/export", query, accept="text/csv, application/json")
        return self._send(endpoint, options).body.decode("utf-8", errors="replace")

    def export_json_range(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> List[AccountingEvent]:
        """:meth:`export_json` over any range: it checks the dates like :meth:`export_json`,
        splits the range into consecutive windows of at most 92 days, both ends included
        (``[from, from + 91d]``, the next one starting the day after; on calendar dates, UTC),
        requests them in order and returns every window's events, in order. A range of 92 days
        or less is one request. ``2026-01-01`` to ``2026-12-31`` is four: ``[01-01, 04-02]``
        ``[04-03, 07-03]`` ``[07-04, 10-03]`` ``[10-04, 12-31]``.

        Raises:
            ValidationError: a malformed date, or ``to_date`` before ``from_date`` (nothing is
                sent). The first API error of a window stops the export and is raised.
        """
        events: List[AccountingEvent] = []
        for start, end in _export_windows(from_date, to_date):
            events.extend(self.export_json(start, end, options=options))
        return events

    def export_csv_range(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> str:
        """:meth:`export_csv` over any range, split like :meth:`export_json_range`: the first
        window's header line once, then every window's rows, with the line endings the API sent
        (a window with only its header adds nothing)."""
        text = ""
        for start, end in _export_windows(from_date, to_date):
            part = self.export_csv(start, end, options=options)
            if text == "":
                text = part
                continue
            rows = _csv_rows(part)
            if rows and not text.endswith("\n"):
                # The previous window's last row had no line ending: give it this window's.
                text += "\r\n" if part[: len(part) - len(rows)].endswith("\r\n") else "\n"
            text += rows
        return text


class CurrenciesService(Service):
    """The currency catalog (``client.currencies``; public routes, the key is sent anyway).
    Rate limited to 60 requests a minute per IP: cache the list."""

    def list(
        self,
        *,
        test: bool = False,
        main: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> List[Currency]:
        """The currency catalog (``GET /currencies``; a bounded list).

        Args:
            test: List the test networks' currencies (whatever the key's mode); False: mainnet.
            main: List only the chains' native coins (ETH, BASE, SOL), no tokens.
        """
        v = Validator()
        v.boolean("test", test)
        v.boolean("main", main)
        v.check()
        query = Query().flag("test", test).flag("main", main)
        return self._call_items(Currency, Endpoint("GET", "/currencies", query), options)

    def get(self, id: int, *, options: Optional[RequestOptions] = None) -> Currency:
        """A currency by its id (``GET /currencies/:id``), e.g. a token's
        ``main_currency_id``. Ids are unique across test and live."""
        if isinstance(id, bool) or not isinstance(id, int) or id <= 0:
            raise field_error("id", "must be a currency id (above 0)")
        return self._call(Currency, Endpoint("GET", pathf("/currencies/{}", id)), options)
