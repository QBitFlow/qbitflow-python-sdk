"""A subscription checkout with a trial; then one subscription: access, bills, test billing, cancel.

QBITFLOW_API_KEY=sk_… python examples/subscriptions.py
QBITFLOW_API_KEY=sk_… SUBSCRIPTION_UUID=sub@… [TEST_BILL=1] [CANCEL=1] \\
    python examples/subscriptions.py
"""

import os

from _common import new_client

import qbitflow


def create_subscription_checkout(client: qbitflow.QBitFlow) -> qbitflow.CheckoutSession:
    # docs:start checkout-create-subscription
    session = client.checkout_sessions.create_subscription(
        product_name="T-shirt",
        description="Blue, size M",
        price=4.99,  # USD per period
        frequency=qbitflow.Duration(value=1, unit=qbitflow.DurationUnit.MONTHS),
        trial_period=qbitflow.Duration(value=7, unit=qbitflow.DurationUnit.DAYS),
        reference="order-1043",
        success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
        cancel_url="https://shop.example.com/orders/cancel",
    )
    print("Send the customer to", session.link)  # sub@…: the subscription's id once signed
    # docs:end checkout-create-subscription
    return session


def show_subscription(client: qbitflow.QBitFlow, subscription_uuid: str) -> None:
    # docs:start subscriptions-get
    subscription = client.subscriptions.get(subscription_uuid)  # sub@…, cancelled ones too
    print(subscription.status, "paid until", subscription.current_period_end)
    # docs:end subscriptions-get


def check_access(client: qbitflow.QBitFlow, subscription_uuid: str) -> None:
    # docs:start has-access
    subscription = client.subscriptions.get(subscription_uuid)
    # current_period_end is set and now is before it, whatever the status.
    if subscription.has_access():
        print("grant access")
    else:
        print("no access")
    # docs:end has-access


def bill_now(client: qbitflow.QBitFlow, subscription_uuid: str) -> None:
    # docs:start subscriptions-test-bill
    # Test mode only: run the next billing now instead of on its due date.
    state = client.subscriptions.execute_test_billing(subscription_uuid)
    print(state.stage, state.outcome, state.failure_code)
    # docs:end subscriptions-test-bill


def cancel_at_period_end(client: qbitflow.QBitFlow, subscription_uuid: str) -> None:
    # docs:start subscriptions-cancel
    result = client.subscriptions.cancel(subscription_uuid, immediate=False)  # at period end
    if result.pending:
        # HTTP 202: still confirming on-chain; subscription.statusChanged tells the end.
        print("cancellation confirming")
    else:
        print("now", result.subscription.status)  # stopped, cancelled at the period's end
    # docs:end subscriptions-cancel


def main() -> None:
    with new_client() as client:
        subscription_uuid = os.environ.get("SUBSCRIPTION_UUID", "")
        if not subscription_uuid:
            try:
                create_subscription_checkout(client)
            except qbitflow.ConflictError as exc:
                if exc.code != "unique_violation":
                    raise
                print("order-1043 already has an open checkout or a subscription")
            print("once subscribed, run again with SUBSCRIPTION_UUID=sub@…")
            return

        show_subscription(client, subscription_uuid)
        check_access(client, subscription_uuid)
        for bill in client.subscriptions.iterate_bills(subscription_uuid, limit=50):
            print(f"  bill {bill.uuid}: {bill.amount:.2f} USD until {bill.period_end}")

        if os.environ.get("TEST_BILL") == "1":
            try:
                bill_now(client, subscription_uuid)
            except qbitflow.ConflictError as exc:
                print("not billed:", exc.code)  # payment_not_due before next_billing_date
        if os.environ.get("CANCEL") == "1":
            try:
                cancel_at_period_end(client, subscription_uuid)
            except qbitflow.ConflictError as exc:
                print("not cancelled:", exc.code)  # e.g. already stopped


if __name__ == "__main__":
    main()
