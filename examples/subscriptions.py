"""A subscription checkout with a trial, a filtered list, the bills, a cancellation at period end.

QBITFLOW_API_KEY=sk_… python examples/subscriptions.py      # CANCEL=1 to stop one
"""

import os
from datetime import datetime, timedelta, timezone

from _common import new_client

from qbitflow import ConflictError, Duration, DurationUnit, SubscriptionStatus


def main() -> None:
    with new_client() as client:
        session = client.checkout_sessions.create_subscription(
            product_name="Pro plan",
            price=4.99,  # USD per period
            frequency=Duration(value=1, unit=DurationUnit.MONTHS),
            trial_period=Duration(value=14, unit=DurationUnit.DAYS),
            customer_reference="crm-42",
            success_url="https://app.example.com/billing?subscription={{UUID}}",
        )
        print(f"Send the customer to {session.link} (subscription {session.uuid} once signed)")

        now = datetime.now(timezone.utc)
        page = client.subscriptions.list(
            status=SubscriptionStatus.ACTIVE, created_after=now - timedelta(days=90), limit=10
        )
        for sub in page.items:
            # The access rule: grant access while now < current_period_end, whatever the status.
            access = sub.current_period_end is not None and now < sub.current_period_end
            print(
                f"{sub.uuid} {sub.status} (customer ref {sub.customer_reference!r}) access={access}"
            )
        if not page.items:
            print("no active subscription to show bills for")
            return

        sub = page.items[0]
        for bill in client.subscriptions.iterate_bills(sub.uuid, limit=50):
            start = bill.period_start.date() if bill.period_start else "—"
            end = bill.period_end.date() if bill.period_end else "—"
            print(f"  bill {bill.uuid}: {bill.amount:.2f} USD for {start} → {end}")

        if os.environ.get("CANCEL") != "1":
            print("set CANCEL=1 to stop", sub.uuid, "at the end of its period")
            return
        try:
            result = client.subscriptions.cancel(sub.uuid, immediate=False)
        except ConflictError as exc:
            print(f"not stopped: {exc.message} ({exc.code})")  # e.g. already stopped
            return
        if result.pending:
            print("stopping: still confirming on-chain")  # HTTP 202
        else:
            print("now", result.subscription.status)


if __name__ == "__main__":
    main()
