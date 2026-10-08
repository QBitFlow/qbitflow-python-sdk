"""The lower level of webhooks: verify the signature and parse the event with construct_event.

Offline: it signs a sample delivery with webhooks.sign, as QBitFlow does, then tampers with it.

QBITFLOW_WEBHOOK_SECRET=whsec_… python examples/webhook_verify.py   # a sample secret when unset
"""

import json
import os
from typing import Optional

import qbitflow


def handle_delivery(raw_body: bytes, signature_header: Optional[str]) -> int:
    """Returns the HTTP status to answer."""
    # docs:start webhook-verify
    try:
        event = qbitflow.webhooks.construct_event(
            raw_body,  # the raw bytes as received, never re-serialized
            signature_header,  # the QBitFlow-Signature header
            os.environ["QBITFLOW_WEBHOOK_SECRET"],
        )
    except qbitflow.WebhookSignatureError as exc:
        print("rejected:", exc.reason)  # e.g. noMatchingSignature, timestampOutsideTolerance
        return 400
    except qbitflow.ValidationError:
        return 400  # not a v2 event
    if isinstance(event, qbitflow.PaymentCompletedEvent):  # narrow the union by class
        print("fulfil order", event.data.reference)
    return 200  # acknowledge every other type too, or QBitFlow retries it
    # docs:end webhook-verify


def main() -> None:
    os.environ.setdefault("QBITFLOW_WEBHOOK_SECRET", "whsec_example_secret")
    secret = os.environ["QBITFLOW_WEBHOOK_SECRET"]
    body = json.dumps(
        {
            "id": "evt_1",
            "version": "v2",
            "type": "webhook.test",
            "createdAt": "2026-10-01T12:00:00Z",
            "test": True,
            "data": {"endpointUuid": "", "message": "hello"},
        }
    ).encode()
    header = qbitflow.webhooks.sign(body, secret)
    print("signed delivery:", handle_delivery(body, header))
    print("tampered delivery:", handle_delivery(body.replace(b"hello", b"hacked"), header))


if __name__ == "__main__":
    main()
