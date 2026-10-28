"""Refunds: list the pending refunds (customers' requests) and read one.

QBITFLOW_API_KEY=sk_… python examples/refunds.py

Refunds are read only in the SDK: they are answered, or sent, from the dashboard.
"""

from _common import new_client

import qbitflow


def list_refunds(client: qbitflow.QBitFlow) -> str:
    # docs:start refunds-list
    # The ones waiting for an answer (status None: every status).
    page = client.refunds.list(status=[qbitflow.RefundStatus.PENDING])
    for refund in page.items:
        print(refund.uuid, refund.tx_uuid, refund.initiated_by, refund.reason, refund.amount)
    # docs:end refunds-list
    return page.items[0].uuid if page.items else ""


def get_refund(client: qbitflow.QBitFlow, refund_uuid: str) -> None:
    # docs:start refunds-get
    refund = client.refunds.get(refund_uuid)  # refund@…
    # pending (a customer's request), approved or rejected.
    print(refund.uuid, refund.status, f"{refund.refund_percent}%", refund.amount)
    # docs:end refunds-get


def main() -> None:
    with new_client() as client:
        refund_uuid = list_refunds(client)
        if refund_uuid:
            get_refund(client, refund_uuid)


if __name__ == "__main__":
    main()
