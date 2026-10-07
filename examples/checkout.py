"""A one-time payment checkout: create it, poll its status, expire it.

QBITFLOW_API_KEY=sk_… python examples/checkout.py
"""

import time

from _common import new_client

from qbitflow import CheckoutSessionStatusValue


def main() -> None:
    with new_client() as client:
        session = client.checkout_sessions.create_payment(
            product_name="T-shirt",
            description="Blue, size M",
            price=4.99,
            reference=f"order-{int(time.time())}",
            success_url="https://shop.example.com/thanks?session={{UUID}}",
            cancel_url="https://shop.example.com/cart",
        )
        expires = session.expires_at.isoformat() if session.expires_at else "—"
        print(
            f"Send the customer to {session.link}\n(session {session.uuid}, expires at {expires})"
        )

        # Fulfil on the payment.completed webhook in production; polling is for this demo.
        for _ in range(3):
            status = client.checkout_sessions.get_status(session.uuid)
            print("status:", status.status)
            if status.last_attempt is not None:
                print("  last attempt failed:", status.last_attempt.code)  # not final
            if status.status == CheckoutSessionStatusValue.COMPLETED:
                payment = client.payments.get(session.uuid)  # the same id as the session
                print(f"paid: {payment.amount:.2f} USD, tx {payment.tx_hash}")
                return
            time.sleep(2)

        # Not paid: end it (an order cancelled on your side). checkout.expired follows.
        expired = client.checkout_sessions.expire(session.uuid)
        print("expired:", expired.status)


if __name__ == "__main__":
    main()
