"""Members, invitations, wallets, the accounting export and the currency catalog."""

from __future__ import annotations

from datetime import date
from typing import Iterator, List, Optional, Union

from .._transport import Endpoint, Query, RequestOptions, pathf
from .._validation import Validator, check_path_uuid, known
from ..errors import field_error
from ..models.common import Currency, Page
from ..models.enums import InvitationStatus, Role
from ..models.resources import (
    AccountingEvent,
    HeldFunds,
    Invitation,
    InvitationCreated,
    Member,
    MemberHeldFundsSummary,
    Wallet,
)
from ._base import Service, iterate_pages

__all__ = [
    "MembersService",
    "InvitationsService",
    "WalletsService",
    "AccountingService",
    "CurrenciesService",
]


class MembersService(Service):
    """The organization's members (marketplace sellers), their trust and their held funds
    (``client.members``; organization key)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Member]:
        """One page of the members in the key's mode (``GET /members``; page size 20, at most
        100; the cursor is a member's ``userUuid``)."""
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
        """Every member :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(lambda c: self.list(limit=limit, cursor=c, options=options), cursor)

    def get(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> Member:
        """A member (``GET /members/:userUuid``)."""
        check_path_uuid("userUuid", user_uuid)
        return self._call(Member, Endpoint("GET", pathf("/members/{}", user_uuid)), options)

    def update(
        self,
        user_uuid: str,
        *,
        organization_fee_percent: float,
        options: Optional[RequestOptions] = None,
    ) -> Member:
        """Change a member's terms (``PUT /members/:userUuid``). Not retried.

        Args:
            organization_fee_percent: The organization's fee on the member's payments from now
                on: 0 to 50, at most 2 decimals (a checkout already created keeps its fee).
        """
        check_path_uuid("userUuid", user_uuid)
        v = Validator()
        v.percent("organizationFeePercent", organization_fee_percent, 50, False)
        v.check()
        endpoint = Endpoint(
            "PUT",
            pathf("/members/{}", user_uuid),
            body={"organizationFeePercent": organization_fee_percent},
        )
        return self._call(Member, endpoint, options)

    def remove(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """End a member's membership in the key's mode (``DELETE /members/:userUuid``): their
        keys stop working and their checkouts close. 409 ``held_funds_pending`` while you hold
        their live funds. Not retried."""
        check_path_uuid("userUuid", user_uuid)
        self._send(Endpoint("DELETE", pathf("/members/{}", user_uuid)), options)

    def trust(self, user_uuid: str, *, options: Optional[RequestOptions] = None) -> Member:
        """Stop holding a member's funds (``POST /members/:userUuid/trust``): their new payments
        go to their own wallets. What is held stays held until released from the dashboard. Not
        retried."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("POST", pathf("/members/{}/trust", user_uuid))
        return self._call(Member, endpoint, options)

    def list_held_funds(
        self, *, options: Optional[RequestOptions] = None
    ) -> List[MemberHeldFundsSummary]:
        """Every member the organization holds funds for (``GET /members/held-funds``)."""
        endpoint = Endpoint("GET", "/members/held-funds")
        return self._call(List[MemberHeldFundsSummary], endpoint, options)

    def get_held_funds(
        self, user_uuid: str, *, options: Optional[RequestOptions] = None
    ) -> HeldFunds:
        """What the organization holds for a member (``GET /members/:userUuid/held-funds``)."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("GET", pathf("/members/{}/held-funds", user_uuid))
        return self._call(HeldFunds, endpoint, options)

    def get_own_held_funds(self, *, options: Optional[RequestOptions] = None) -> HeldFunds:
        """What the organization holds for the request's member (``GET /user/held-funds``): for
        a member's key or ``on_behalf_of``; empty for the organization."""
        return self._call(HeldFunds, Endpoint("GET", "/user/held-funds"), options)


class InvitationsService(Service):
    """Invitations to join the organization as a member (``client.invitations``; organization
    key). Team invitations are made from the dashboard."""

    def create(
        self,
        *,
        email: str,
        trust_layer: bool = False,
        organization_fee_percent: Optional[float] = None,
        redirect_url: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> InvitationCreated:
        """Invite a member (``POST /invitations``; the SDK always sends ``role: user``). Sends
        an ``Idempotency-Key``; retried on transient failures.

        Args:
            email: The person to invite.
            trust_layer: True holds the member's payments until the organization trusts them
                (``members.trust``); False pays them directly.
            organization_fee_percent: The organization's fee on their payments: 0 to 50, at most
                2 decimals (``None`` = 0).
            redirect_url: Where the person goes once they accepted (with
                ``?invitationUuid=<uuid>``).

        Raises:
            ConflictError: 409 ``already_joined``.
            RateLimitError: beyond 50 invitations an hour.
        """
        v = Validator()
        if v.required("email", email):
            v.email("email", email)
        v.boolean("trustLayer", trust_layer)
        if organization_fee_percent is not None:
            v.percent("organizationFeePercent", organization_fee_percent, 50, False)
        v.url("redirectUrl", redirect_url)
        v.check()
        body = {"email": email, "role": str(Role.USER), "trustLayer": bool(trust_layer)}
        if organization_fee_percent is not None:
            body["organizationFeePercent"] = organization_fee_percent
        if redirect_url:
            body["redirectUrl"] = redirect_url
        endpoint = Endpoint("POST", "/invitations", body=body, idempotent=True)
        return self._call(InvitationCreated, endpoint, options)

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Union[InvitationStatus, str, None] = None,
        options: Optional[RequestOptions] = None,
    ) -> Page[Invitation]:
        """One page of the invitations (``GET /invitations``; page size 20, at most 100),
        optionally filtered by ``status``."""
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
        """Every invitation :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list(limit=limit, cursor=c, status=status, options=options), cursor
        )

    def revoke(self, uuid: str, *, options: Optional[RequestOptions] = None) -> Invitation:
        """Revoke an invitation (``DELETE /invitations/:uuid``). Not retried."""
        check_path_uuid("uuid", uuid)
        return self._call(Invitation, Endpoint("DELETE", pathf("/invitations/{}", uuid)), options)


class WalletsService(Service):
    """The wallets and the currencies a space accepts (``client.wallets``). Wallets are added and
    removed in the dashboard, by their owner only."""

    def list(
        self, *, with_balances: bool = False, options: Optional[RequestOptions] = None
    ) -> List[Wallet]:
        """The space's wallets (``GET /wallet/user``).

        Args:
            with_balances: Add each token wallet's balance.
        """
        v = Validator()
        v.boolean("withBalances", with_balances)
        v.check()
        query = Query().flag("withBalances", with_balances)
        return self._call(List[Wallet], Endpoint("GET", "/wallet/user", query), options)

    def list_for_member(
        self, user_uuid: str, *, options: Optional[RequestOptions] = None
    ) -> List[Wallet]:
        """A member's wallets (``GET /wallet/user/:userUuid``; organization key)."""
        check_path_uuid("userUuid", user_uuid)
        endpoint = Endpoint("GET", pathf("/wallet/user/{}", user_uuid))
        return self._call(List[Wallet], endpoint, options)

    def list_supported_currencies(
        self, *, user_uuid: Optional[str] = None, options: Optional[RequestOptions] = None
    ) -> List[Currency]:
        """The currencies a space's checkouts accept (``GET /wallet/supported-currencies``):
        none means its checkouts answer 409 ``merchant_not_ready``.

        Args:
            user_uuid: Read a member's (organization key); ``None`` for the request's space.
        """
        v = Validator()
        v.uuid("userUuid", user_uuid)
        v.check()
        query = Query().string("userUuid", user_uuid)
        endpoint = Endpoint("GET", "/wallet/supported-currencies", query)
        return self._call(List[Currency], endpoint, options)


def _export_query(from_date: Union[str, date], to_date: Union[str, date], fmt: str) -> Query:
    """Check an export window (two ``YYYY-MM-DD`` dates, from <= to; the API enforces the 95-day
    maximum) and encode it."""
    v = Validator()
    v.date_range("from", from_date, "to", to_date)
    v.check()
    start = from_date.isoformat() if isinstance(from_date, date) else from_date
    end = to_date.isoformat() if isinstance(to_date, date) else to_date
    return Query().string("from", start).string("to", end).string("format", fmt)


class AccountingService(Service):
    """The accounting export (``client.accounting``)."""

    def export_json(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> List[AccountingEvent]:
        """Every payment, bill, refund and fee between two dates, both included
        (``GET /accounting/export?format=json``).

        Args:
            from_date: The first day, ``YYYY-MM-DD`` (or a ``datetime.date``).
            to_date: The last day; the API allows at most 95 days per export.
        """
        query = _export_query(from_date, to_date, "json")
        return self._call(
            List[AccountingEvent], Endpoint("GET", "/accounting/export", query), options
        )

    def export_csv(
        self,
        from_date: Union[str, date],
        to_date: Union[str, date],
        *,
        options: Optional[RequestOptions] = None,
    ) -> str:
        """The same export as CSV text (``GET /accounting/export?format=csv``). Errors are still
        parsed as JSON errors."""
        query = _export_query(from_date, to_date, "csv")
        endpoint = Endpoint("GET", "/accounting/export", query, accept="text/csv, application/json")
        return self._send(endpoint, options).body.decode("utf-8", errors="replace")


class CurrenciesService(Service):
    """The currency catalog (``client.currencies``; public routes, the key is sent anyway).
    Limited to 60 requests a minute per IP: cache the list."""

    def list_available(
        self, *, test: bool = False, options: Optional[RequestOptions] = None
    ) -> List[Currency]:
        """Every currency checkouts can take (``GET /utils/all-available-currencies``).

        Args:
            test: List the testnet currencies (whatever the key's mode).
        """
        v = Validator()
        v.boolean("test", test)
        v.check()
        query = Query().flag("test", test)
        endpoint = Endpoint("GET", "/utils/all-available-currencies", query)
        return self._call(List[Currency], endpoint, options)

    def list_main(
        self, *, test: bool = False, options: Optional[RequestOptions] = None
    ) -> List[Currency]:
        """The chains' native coins (``GET /utils/all-main-currencies``)."""
        v = Validator()
        v.boolean("test", test)
        v.check()
        query = Query().flag("test", test)
        endpoint = Endpoint("GET", "/utils/all-main-currencies", query)
        return self._call(List[Currency], endpoint, options)

    def get(self, id: int, *, options: Optional[RequestOptions] = None) -> Currency:
        """A currency by its id (``GET /utils/currency/id/:id``)."""
        if isinstance(id, bool) or not isinstance(id, int) or id <= 0:
            raise field_error("id", "must be a currency id (above 0)")
        return self._call(Currency, Endpoint("GET", pathf("/utils/currency/id/{}", id)), options)
