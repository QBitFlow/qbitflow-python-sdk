"""A webhook endpoint in FastAPI: the WebhookRouter verifies, parses and dispatches each delivery.

pip install fastapi uvicorn
QBITFLOW_WEBHOOK_SECRET=whsec_… python examples/webhook_fastapi.py
# then point a webhook endpoint at http(s)://<host>:8080/webhooks/qbitflow

Flask and Django mount the same router: router.flask_view(), router.django_view().
"""

import os

from fastapi import FastAPI

import qbitflow


def mark_order_paid(reference: str, event_id: str) -> None:
    """Stands for your fulfilment code: idempotent, it skips an event id seen before."""
    print(f"order {reference} paid (event {event_id})")


# docs:start webhook-handler
router = qbitflow.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])


@router.on("payment.completed")  # the handler gets the typed data, then the event
def fulfil(data: qbitflow.PaymentCompleted, event: qbitflow.Event) -> None:
    # At least once: the same event can arrive twice, deduplicate on event.id.
    mark_order_paid(data.reference or data.uuid, event_id=event.id)


app = FastAPI()
# Verifies the QBitFlow-Signature header on the raw body, parses the event, runs the handler
# for its type, and answers the status QBitFlow expects (200, 400 or 500).
app.add_api_route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
# docs:end webhook-handler


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
