"""A one-time payment checkout: create it, read its status, wait for it, expire it.

QBITFLOW_API_KEY=sk_… python examples/checkout.py           # WAIT=1 to wait for the payment
"""

import os

from _common import new_client

import qbitflow


def create_checkout(client: qbitflow.QBitFlow) -> qbitflow.CheckoutSession:
    # docs:start checkout-create-payment
    session = client.checkout_sessions.create_payment(
        product_name="T-shirt",
        description="Blue, size M",
        price=4.99,  # USD
        reference="order-1042",  # your order id: unique per space
        # QBitFlow replaces the placeholder with the session's id when it redirects the customer.
        success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
        cancel_url="https://shop.example.com/orders/cancel",
    )
    # Redirect the customer to the hosted checkout page.
    print("Send the customer to", session.link)
    # docs:end checkout-create-payment
    return session


def show_status(client: qbitflow.QBitFlow, session_uuid: str) -> None:
    # docs:start checkout-status
    status = client.checkout_sessions.get_status(session_uuid)  # pay@… or sub@…
    if status.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
        print("paid, tx", status.tx_hash)  # the payment (or subscription) has the session's id
    elif status.status == qbitflow.CheckoutSessionStatusValue.EXPIRED:
        print("expired unpaid")
    elif status.last_attempt is not None:
        print("last attempt failed:", status.last_attempt.code)  # not final: they can try again
    else:
        print("waiting:", status.status)  # created or waitingConfirmation
    # docs:end checkout-status


def wait_for_payment(client: qbitflow.QBitFlow, session_uuid: str) -> str:
    # docs:start wait-for-completion
    # For scripts and back-office jobs: fulfil orders on the payment.completed webhook.
    final = client.checkout_sessions.wait_for_completion(session_uuid, timeout=600, interval=3)
    if final.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
        print("paid")
    else:
        print("not paid:", final.status)  # expired, or still open when the timeout elapsed
    # docs:end wait-for-completion
    return final.status


def expire_checkout(client: qbitflow.QBitFlow, session_uuid: str) -> None:
    # docs:start checkout-expire
    # An order cancelled on your side: the checkout can no longer be paid.
    expired = client.checkout_sessions.expire(session_uuid)
    print(expired.status)  # expired; checkout.expired follows
    # docs:end checkout-expire


def main() -> None:
    with new_client() as client:
        session = create_checkout(client)
        session_uuid = session.uuid
        show_status(client, session_uuid)
        if os.environ.get("WAIT") == "1":
            final = wait_for_payment(client, session_uuid)
            if final in (
                qbitflow.CheckoutSessionStatusValue.COMPLETED,
                qbitflow.CheckoutSessionStatusValue.EXPIRED,
            ):
                return
        # Not paid: end it, which also frees order-1042 for the next run.
        expire_checkout(client, session_uuid)


if __name__ == "__main__":
    main()
