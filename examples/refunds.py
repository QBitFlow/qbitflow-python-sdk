"""Refunds: refund half of a payment, then list the active refunds.

QBITFLOW_API_KEY=sk_… [PAYMENT_UUID=pay@…] python examples/refunds.py
"""

import os

from _common import new_client

import qbitflow


def refund_payment(client: qbitflow.QBitFlow, payment_uuid: str) -> None:
    # docs:start refunds-create
    refund = client.refunds.initiate(
        tx_uuid=payment_uuid,  # pay@… (or a bill's sub-hist@…)
        refund_percent=50,  # of what the customer paid; None refunds everything
        reason="Damaged item",
    )
    # A pending refund: no money moves until you sign the transfer in the dashboard.
    print(refund.uuid, refund.status)
    # docs:end refunds-create


def list_refunds(client: qbitflow.QBitFlow) -> None:
    # docs:start refunds-list
    for refund in client.refunds.list():  # the active refunds
        print(refund.uuid, refund.tx_uuid, refund.status, refund.reason)
    # docs:end refunds-list


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
        list_refunds(client)


if __name__ == "__main__":
    main()
