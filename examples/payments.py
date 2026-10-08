"""Payments: one page with a filter, one payment, every payment, and exact amounts.

QBITFLOW_API_KEY=sk_… [PAYMENT_UUID=pay@…] python examples/payments.py
"""

import os

from _common import new_client

import qbitflow


def list_payments(client: qbitflow.QBitFlow) -> None:
    # docs:start payments-list
    page = client.payments.list(refunded=False, limit=20)  # newest first
    for payment in page.items:
        print(payment.uuid, payment.reference, f"{payment.amount:.2f} USD")
    if page.has_more:
        print("next page: cursor =", page.next_cursor)  # pass it back as cursor=
    # docs:end payments-list


def get_payment(client: qbitflow.QBitFlow, payment_uuid: str) -> None:
    # docs:start payments-get
    payment = client.payments.get(payment_uuid)  # pay@…, the id of its checkout session
    print(payment.reference, f"{payment.amount:.2f} USD", payment.tx_hash)

    by_reference = client.payments.get_by_reference("order-1042")  # your order id
    print(by_reference.uuid)
    # docs:end payments-get


def every_payment(client: qbitflow.QBitFlow) -> None:
    # docs:start pagination-iterate
    # Fetches one page at a time, only as the loop consumes it; break stops the fetching.
    for payment in client.payments.iterate(limit=50):
        print(payment.uuid, f"{payment.amount:.2f} USD")
    # docs:end pagination-iterate


def amounts() -> None:
    # docs:start amounts-display
    # Amounts in a token's smallest unit are decimal strings: never convert them through a float.
    shown = qbitflow.format_amount("4990000", 6)  # "4.99" (6 decimals, like USDC)
    min_units = qbitflow.parse_amount("4.99", 6)  # "4990000"
    print(shown, min_units)
    # docs:end amounts-display


def main() -> None:
    amounts()
    with new_client() as client:
        list_payments(client)
        every_payment(client)
        payment_uuid = os.environ.get("PAYMENT_UUID", "")
        if not payment_uuid:
            print("set PAYMENT_UUID=pay@… to read one payment")
            return
        try:
            get_payment(client, payment_uuid)
        except qbitflow.NotFoundError as exc:
            print("not found:", exc.message)  # e.g. no payment has the reference order-1042


if __name__ == "__main__":
    main()
