"""Webhook endpoints and the event log: register an endpoint, list the recent events.

QBITFLOW_API_KEY=sk_… [CREATE_ENDPOINT=1] python examples/webhook_endpoints.py
"""

import os

from _common import new_client

import qbitflow


def create_endpoint(client: qbitflow.QBitFlow) -> None:
    # docs:start webhook-endpoint-create
    created = client.webhooks.endpoints.create(
        url="https://shop.example.com/webhooks/qbitflow",
        events=[  # None: every type, including the ones added later
            qbitflow.EventType.PAYMENT_COMPLETED,
            qbitflow.EventType.CHECKOUT_EXPIRED,
            qbitflow.EventType.SUBSCRIPTION_STATUS_CHANGED,
        ],
        description="Order fulfilment",
    )
    # The whsec_… secret is returned only this once: put it in your secret store now
    # (QBITFLOW_WEBHOOK_SECRET for your webhook handler).
    print(created.uuid, created.secret)
    # docs:end webhook-endpoint-create


def list_events(client: qbitflow.QBitFlow) -> None:
    # docs:start events-list
    page = client.webhooks.events.list(type=qbitflow.EventType.PAYMENT_COMPLETED, limit=20)
    for event in page.items:  # newest first
        print(event.id, event.type, event.created_at)
    # docs:end events-list


def main() -> None:
    with new_client() as client:
        if os.environ.get("CREATE_ENDPOINT") == "1":
            create_endpoint(client)
        list_events(client)


if __name__ == "__main__":
    main()
