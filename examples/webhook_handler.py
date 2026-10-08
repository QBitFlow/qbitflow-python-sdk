"""A webhook receiver (standard library only): a WebhookRouter verifies each delivery, runs the
handler of its type and gives the HTTP answer; the handlers deduplicate on the event id.

QBITFLOW_WEBHOOK_SECRET=whsec_… python examples/webhook_handler.py
# then point a webhook endpoint at http(s)://<host>:8080/webhooks/qbitflow

With Flask, Django or FastAPI, mount the same router instead of this server:
``router.flask_view()``, ``router.django_view()``, ``router.fastapi_endpoint()``.
"""

import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Set

from qbitflow import (
    CheckoutExpired,
    Event,
    MemberJoined,
    PaymentCompleted,
    SubscriptionStatusChanged,
    UnknownEvent,
    WebhookSignatureError,
    webhooks,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("webhooks")

SECRET = os.environ.get("QBITFLOW_WEBHOOK_SECRET", "")
# Stands for your database: deliveries are at least once, deduplicate on the event id.
processed: Set[str] = set()
lock = threading.Lock()


def first_time(event: Event) -> bool:
    """Record the event; False when it was already handled (a retry)."""
    with lock:
        if event.id in processed:
            return False
        processed.add(event.id)
        return True


def log_error(event: Any, exc: BaseException) -> None:
    # Every 400 (bad signature or body: event is None) and 500 (a handler raised: retried).
    log.error("delivery %s failed: %r", getattr(event, "id", "-"), exc)


router = webhooks.WebhookRouter(SECRET or "unset", on_error=log_error)


@router.on("payment.completed")
def fulfil(data: PaymentCompleted, event: Event) -> None:
    if first_time(event):
        amount = data.currency.format_amount(data.amount_min_units) if data.currency else "?"
        symbol = data.currency.symbol if data.currency else ""
        log.info("fulfil order %r (%s): %s %s", data.reference, data.uuid, amount, symbol)


@router.on("checkout.expired")
def release(data: CheckoutExpired, event: Event) -> None:
    if first_time(event):
        log.info("release order %r", data.reference)


@router.on("subscription.statusChanged")
def status_changed(data: SubscriptionStatusChanged, event: Event) -> None:
    if first_time(event):
        log.info(
            "%s: %s -> %s, access: %s",
            data.uuid,
            data.previous_status,
            data.status,
            data.has_access(),
        )


@router.on("member.joined")
def member_joined(data: MemberJoined, event: Event) -> None:
    log.info("invitation %s accepted by %s", data.invitation_uuid, data.user_uuid)


@router.on_unknown
def unknown(event: UnknownEvent) -> None:
    log.info("event type %s is newer than this SDK: acknowledged", event.type)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - the http.server API
        if self.path != "/webhooks/qbitflow":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > webhooks.MAX_BODY_BYTES:
            self.answer(413, {"error": "body too large"})
            return
        raw_body = self.rfile.read(length)  # the raw bytes: never re-serialize them
        result = router.handle(raw_body, self.headers.get(webhooks.SIGNATURE_HEADER))
        if result.status == 400:
            bad_signature = isinstance(result.error, WebhookSignatureError)
            self.answer(400, {"error": "invalid signature" if bad_signature else "invalid event"})
        elif result.status == 500:
            self.answer(500, {"error": "internal error"})
        else:
            # 2xx, also to the types without a handler.
            self.answer(200, {"received": True})

    def answer(self, status: int, body: Any) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    if not SECRET:
        sys.exit("set QBITFLOW_WEBHOOK_SECRET")
    server = ThreadingHTTPServer(("", 8080), Handler)
    log.info("listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
