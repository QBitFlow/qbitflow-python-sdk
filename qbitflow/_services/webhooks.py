"""Webhook verification, endpoints and the event log."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List, Optional, Sequence, Union

from .. import webhooks as _webhooks
from .._transport import Endpoint, Query, RequestOptions, as_webhook_signature_error, pathf
from .._validation import Validator, check_path_required, check_path_uuid, known
from ..errors import BadRequestError, WebhookSignatureReason, field_error, signature_error
from ..models.common import Page
from ..models.enums import EventType, WebhookPayloadVersion
from ..models.events import Event, EventDetail
from ..models.resources import WebhookEndpoint, WebhookEndpointCreated
from ._base import NOT_GIVEN, NotGiven, Service, compact, iterate_pages

if TYPE_CHECKING:  # pragma: no cover
    from .._client import QBitFlow

__all__ = ["WebhooksService", "WebhookEndpointsService", "WebhookEventsService"]


class WebhookEndpointsService(Service):
    """The space's webhook endpoints (``client.webhooks.endpoints``). A member's key needs the
    organization's ``members.webhooks`` policy (403 ``policy_disabled``)."""

    def list(self, *, options: Optional[RequestOptions] = None) -> List[WebhookEndpoint]:
        """The space's endpoints (``GET /webhooks/endpoints``; at most 10, not paginated)."""
        return self._call(List[WebhookEndpoint], Endpoint("GET", "/webhooks/endpoints"), options)

    def create(
        self,
        *,
        url: str,
        events: Optional[Sequence[Union[EventType, str]]] = None,
        include_members: Optional[bool] = None,
        description: Optional[str] = None,
        options: Optional[RequestOptions] = None,
    ) -> WebhookEndpointCreated:
        """Add a webhook endpoint (``POST /webhooks/endpoints``, 201). The answer carries the
        endpoint's ``secret`` (``whsec_…``), shown only this once: store it. Sends an
        ``Idempotency-Key``; retried on transient failures.

        Args:
            url: Where the events are posted (https and a public host in live mode).
            events: The event types to receive (at most 20, not ``webhook.test``); ``None``:
                every type, including the ones added later.
            include_members: Whether an organization endpoint also receives its members' events
                (``None``: True for an organization endpoint, False for a member's).
            description: A note for the dashboard (at most 200 characters).

        Raises:
            ConflictError: 409 ``conflict`` beyond 10 endpoints per space and mode.
        """
        v = Validator()
        if v.required("url", url):
            v.url("url", url)
        v.endpoint_events("events", events)
        v.boolean("includeMembers", include_members)
        v.text("description", description, 0, 200)
        v.check()
        body = compact(url=url, description=description)
        if events:
            body["events"] = [str(e) for e in events]
        if include_members is not None:
            body["includeMembers"] = include_members
        endpoint = Endpoint("POST", "/webhooks/endpoints", body=body, idempotent=True)
        return self._call(WebhookEndpointCreated, endpoint, options)

    def get(self, uuid: str, *, options: Optional[RequestOptions] = None) -> WebhookEndpoint:
        """An endpoint (``GET /webhooks/endpoints/:uuid``). Its secret is never returned again
        (rotate it in the dashboard)."""
        check_path_uuid("uuid", uuid)
        endpoint = Endpoint("GET", pathf("/webhooks/endpoints/{}", uuid))
        return self._call(WebhookEndpoint, endpoint, options)

    def update(
        self,
        uuid: str,
        *,
        url: Optional[str] = None,
        events: Optional[Sequence[Union[EventType, str]]] = None,
        include_members: Optional[bool] = None,
        description: Union[str, None, NotGiven] = NOT_GIVEN,
        payload_version: Union[WebhookPayloadVersion, str, None] = None,
        enabled: Optional[bool] = None,
        options: Optional[RequestOptions] = None,
    ) -> WebhookEndpoint:
        """Change an endpoint (``PUT /webhooks/endpoints/:uuid``): only the arguments given
        change. Not retried.

        Args:
            events: Replaces the event types; ``[]`` means every type, ``None`` keeps them.
            description: The new note; ``""`` (or ``None``) clears it, left out keeps it.
            payload_version: ``v2`` moves an endpoint migrated from v1 to the event envelope
                (never back).
            enabled: False pauses the endpoint; True enables it again.
        """
        check_path_uuid("uuid", uuid)
        clear_description = None if isinstance(description, NotGiven) else (description or "")
        v = Validator()
        v.url("url", url)
        v.endpoint_events("events", events)
        v.boolean("includeMembers", include_members)
        v.text("description", clear_description, 0, 200)
        v.one_of("payloadVersion", payload_version, [str(WebhookPayloadVersion.V2)])
        v.boolean("enabled", enabled)
        v.check()
        body = compact(url=url, payloadVersion=payload_version)
        if events is not None:
            body["events"] = [str(e) for e in events]
        if include_members is not None:
            body["includeMembers"] = include_members
        if clear_description is not None:
            body["description"] = clear_description
        if enabled is not None:
            body["enabled"] = enabled
        endpoint = Endpoint("PUT", pathf("/webhooks/endpoints/{}", uuid), body=body)
        return self._call(WebhookEndpoint, endpoint, options)

    def delete(self, uuid: str, *, options: Optional[RequestOptions] = None) -> None:
        """Delete an endpoint (``DELETE /webhooks/endpoints/:uuid``). Not retried."""
        check_path_uuid("uuid", uuid)
        self._send(Endpoint("DELETE", pathf("/webhooks/endpoints/{}", uuid)), options)


class WebhookEventsService(Service):
    """The space's event log (``client.webhooks.events``)."""

    def list(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        type: Union[EventType, str, None] = None,
        include_members: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Page[Event]:
        """One page of the event log (``GET /webhooks/events``; newest first, page size 20, at
        most 100; the cursor is an event id, ``evt_…``).

        Args:
            type: Keep only the events of this type.
            include_members: Add the members' events (organization key).
        """
        v = Validator()
        v.page(limit, cursor)
        v.one_of("type", type, known(EventType))
        v.boolean("includeMembers", include_members)
        v.check()
        query = (
            Query().page(limit, cursor).string("type", type).flag("includeMembers", include_members)
        )
        return self._call(Page[Event], Endpoint("GET", "/webhooks/events", query), options)

    def iterate(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        type: Union[EventType, str, None] = None,
        include_members: bool = False,
        options: Optional[RequestOptions] = None,
    ) -> Iterator[Event]:
        """Every event :meth:`list` returns, fetching the pages lazily."""
        return iterate_pages(
            lambda c: self.list(
                limit=limit, cursor=c, type=type, include_members=include_members, options=options
            ),
            cursor,
        )

    def get(self, id: str, *, options: Optional[RequestOptions] = None) -> EventDetail:
        """An event of the log with its deliveries to the space's endpoints
        (``GET /webhooks/events/:id``; ``id`` is ``evt_…``)."""
        check_path_required("id", id)
        return self._call(EventDetail, Endpoint("GET", pathf("/webhooks/events/{}", id)), options)


class WebhooksService(Service):
    """Webhook verification, plus the endpoints (``endpoints``) and the event log (``events``)
    (``client.webhooks``). The local checks are also module functions of
    :mod:`qbitflow.webhooks`, usable without a client."""

    def __init__(self, client: "QBitFlow") -> None:
        super().__init__(client)
        #: The webhook endpoints.
        self.endpoints = WebhookEndpointsService(client)
        #: The event log.
        self.events = WebhookEventsService(client)

    def verify(
        self,
        raw_body: _webhooks.RawBody,
        signature_header: Optional[str],
        secret: str,
        *,
        tolerance: float = _webhooks.DEFAULT_TOLERANCE,
        now: Optional[_webhooks.Clock] = None,
    ) -> None:
        """Check a webhook delivery's signature locally (:func:`qbitflow.webhooks.verify`)."""
        _webhooks.verify(raw_body, signature_header, secret, tolerance=tolerance, now=now)

    def construct_event(
        self,
        raw_body: _webhooks.RawBody,
        signature_header: Optional[str],
        secret: str,
        *,
        tolerance: float = _webhooks.DEFAULT_TOLERANCE,
        now: Optional[_webhooks.Clock] = None,
    ) -> Event:
        """Verify and parse a webhook delivery (:func:`qbitflow.webhooks.construct_event`)."""
        return _webhooks.construct_event(
            raw_body, signature_header, secret, tolerance=tolerance, now=now
        )

    def parse_event(self, raw_body: _webhooks.RawBody) -> Event:
        """Parse a webhook body without verifying it (:func:`qbitflow.webhooks.parse_event`)."""
        return _webhooks.parse_event(raw_body)

    def verify_remote(
        self,
        endpoint_uuid: str,
        raw_body: _webhooks.RawBody,
        signature_header: Optional[str],
        *,
        options: Optional[RequestOptions] = None,
    ) -> None:
        """Have the API check a webhook delivery's signature (``POST /webhooks/verify``), with
        the endpoint's current secret (useful when you do not store it). Not retried. Parse the
        verified body with :meth:`parse_event`.

        Raises:
            WebhookSignatureError: a mismatch, a malformed header, or a timestamp more than 5
                minutes from the server's clock (400 ``invalid_signature``: reason
                ``invalidSignature``); an empty header (reason ``missingHeader``, nothing sent).
            NotFoundError: another space's endpoint.
        """
        check_path_uuid("endpointUuid", endpoint_uuid)
        if isinstance(raw_body, str):
            text = raw_body
            size = len(raw_body.encode("utf-8", errors="surrogatepass"))
        elif isinstance(raw_body, (bytes, bytearray, memoryview)):
            data = bytes(raw_body)
            size = len(data)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None  # reported below, after the size checks
        else:
            raise field_error("body", "must be the raw body (bytes or str)")
        if size == 0:
            raise field_error("body", "is required")
        if size > _webhooks.MAX_BODY_BYTES:
            raise field_error("body", "must be at most 1 MiB")
        if text is None:
            raise field_error("body", "must be valid UTF-8")
        if not signature_header:
            raise signature_error(
                WebhookSignatureReason.MISSING_HEADER, "missing QBitFlow-Signature header"
            )
        body = {"endpointUuid": endpoint_uuid, "body": text, "signature": signature_header}
        try:
            self._send(Endpoint("POST", "/webhooks/verify", body=body), options)
        except BadRequestError as exc:
            converted = as_webhook_signature_error(exc)
            if converted is exc:
                raise
            raise converted from None
