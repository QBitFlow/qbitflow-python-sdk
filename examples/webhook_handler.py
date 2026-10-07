"""A webhook receiver (standard library only): verify, deduplicate, dispatch on the event type.

QBITFLOW_WEBHOOK_SECRET=whsec_… python examples/webhook_handler.py
# then point a webhook endpoint at http(s)://<host>:8080/webhooks/qbitflow
"""

import logging
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Set

from qbitflow import (
    CheckoutExpiredEvent,
    MemberJoinedEvent,
    PaymentCompletedEvent,
    SubscriptionStatusChangedEvent,
    ValidationError,
    WebhookSignatureError,
    webhooks,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("webhooks")

SECRET = os.environ.get("QBITFLOW_WEBHOOK_SECRET", "")
# Stands for your database: deliveries are at least once, deduplicate on the event id.
processed: Set[str] = set()
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - the http.server API
        if self.path != "/webhooks/qbitflow":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > webhooks.MAX_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        raw_body = self.rfile.read(length)  # the raw bytes: never re-serialize them
        try:
            event = webhooks.construct_event(
                raw_body, self.headers.get(webhooks.SIGNATURE_HEADER), SECRET
            )
        except WebhookSignatureError as exc:
            log.warning("rejected delivery: %s", exc.reason)
            self.send_response(400)
            self.end_headers()
            return
        except ValidationError as exc:
            log.warning("not a v2 event: %s", exc)  # an endpoint still on v1
            self.send_response(400)
            self.end_headers()
            return

        with lock:
            duplicate = event.id in processed
            processed.add(event.id)
        if not duplicate:
            handle(event)
        # Answer 2xx fast, also to the types you ignore.
        self.send_response(200)
        self.end_headers()


def handle(event: object) -> None:
    if isinstance(event, PaymentCompletedEvent):
        p = event.data
        log.info("fulfil order %r (%s): %.2f USD", p.reference, p.uuid, p.amount)
    elif isinstance(event, CheckoutExpiredEvent):
        log.info("release order %r", event.data.reference)
    elif isinstance(event, SubscriptionStatusChangedEvent):
        s = event.data
        now = datetime.now(timezone.utc)
        access = s.current_period_end is not None and now < s.current_period_end
        log.info("%s: %s -> %s, access: %s", s.uuid, s.previous_status, s.status, access)
    elif isinstance(event, MemberJoinedEvent):
        log.info("invitation %s accepted by %s", event.data.invitation_uuid, event.data.user_uuid)
    # Any other type (or one added after this SDK): acknowledged, nothing to do.


def main() -> None:
    if not SECRET:
        sys.exit("set QBITFLOW_WEBHOOK_SECRET")
    server = ThreadingHTTPServer(("", 8080), Handler)
    log.info("listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
