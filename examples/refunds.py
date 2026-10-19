"""Refunds: refund half of a payment, list the pending refunds, and read one.

QBITFLOW_API_KEY=sk_… [PAYMENT_UUID=pay@…] python examples/refunds.py
"""

import os

from _common import new_client

import qbitflow


def refund_payment(client: qbitflow.QBitFlow, payment_uuid: str) -> None:
    # docs:start refunds-create
    refund = client.refunds.create(
        tx_uuid=payment_uuid,  # pay@… (or a bill's sub-hist@…)
        refund_percent="50",  # a percent string, of what the customer paid; None refunds all
        reason="Damaged item",
    )
    # Pending: no money moves until you sign the transfer in the dashboard (refund.approved).
    print(refund.uuid, refund.status, refund.amount, refund.currency.symbol)
    # docs:end refunds-create


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
    # pending, approved, rejected or cancelled (a merchant's draft dropped before it was sent).
    print(refund.uuid, refund.status, f"{refund.refund_percent}%", refund.amount)
    # docs:end refunds-get


def main() -> None:
    with new_client() as client:
        payment_uuid = os.environ.get("PAYMENT_UUID", "")
        if payment_uuid:
            try:
                refund_payment(client, payment_uuid)
            except qbitflow.ConflictError as exc:
                print("not refunded:", exc.code)  # e.g. refund_already_exists
        else:
            print("set PAYMENT_UUID=pay@… to refund half of a payment")
        refund_uuid = list_refunds(client)
        if refund_uuid:
            get_refund(client, refund_uuid)


if __name__ == "__main__":
    main()
