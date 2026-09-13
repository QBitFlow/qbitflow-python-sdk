import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qbitflow import QBitFlow  # noqa: E402
from qbitflow.dto.transaction.status import (  # noqa: E402
    TransactionStatusValue,
    TransactionType,
)
from qbitflow.utils.duration import Duration  # noqa: E402

CUSTOMER_UUID = "<your_test_customer_uuid>"  # Replace with your test customer UUID

if __name__ == "__main__":
    key = os.getenv("QBITFLOW_API_KEY")
    if not key:
        raise EnvironmentError("QBITFLOW_API_KEY environment variable not set")

    client = QBitFlow(api_key=key)

    # --- One-Time Payment ---

    # Create a payment, process it, and retrieve its status
    payment = client.one_time_payments.create_session(product_id=1, customer_uuid=CUSTOMER_UUID)

    print(f"Payment link: {payment.link}")
    input("Press Enter after completing the payment...")

    # Retrieve payment status
    status = client.transaction_status.get(
        transaction_uuid=payment.uuid, transaction_type=TransactionType.ONE_TIME_PAYMENT
    )
    print(f"Payment Status: {status.status}")
    assert (
        status.status == TransactionStatusValue.COMPLETED
    ), "Payment was not completed successfully"

    # Retrieve from the database
    payment_details = client.one_time_payments.get(payment.uuid)
    print(f"Payment Amount: ${payment_details.amount}")
    print(f"Transaction Hash: {payment_details.transaction_hash}")

    # --- Subscription ---

    sub = client.subscriptions.create_session(
        product_id=1, frequency=Duration(value=1, unit="months"), customer_uuid=CUSTOMER_UUID
    )
    print(f"Subscription link: {sub.link}")
    input("Press Enter after completing the subscription...")

    # Retrieve subscription status
    status = client.transaction_status.get(
        transaction_uuid=sub.uuid, transaction_type=TransactionType.CREATE_SUBSCRIPTION
    )
    print(f"Subscription Status: {status.status}")
    assert (
        status.status == TransactionStatusValue.COMPLETED
    ), "Subscription was not activated successfully"

    # Retrieve subscription from the database
    subscription_details = client.subscriptions.get(sub.uuid)
    print(f"Subscription Product ID: {subscription_details.product_id}")
    print(f"Subscription Status: {subscription_details.subscription_status}")

    input("Press enter after running the billing job...")

    # Retrieve payment history
    payment_history = client.subscriptions.get_payment_history(sub.uuid)
    assert len(payment_history) > 0, "No payment history found for subscription"

    # Force cancel a subscription
    cancel_response = client.subscriptions.force_cancel(sub.uuid)
    print(f"Subscription cancelled: {cancel_response.message}")

    # Try and retrieve the subscription again
    try:
        subscription_details = client.subscriptions.get(sub.uuid)
        print(f"Subscription Product ID: {subscription_details.product_id}")
        print(f"Subscription Status: {subscription_details.subscription_status}")
    except Exception as e:
        print(f"Error retrieving subscription: {e}")

    # --- Pay-as-you-go ---
    #
    # NOTE: creating PAYG sessions is currently disabled on the API, so there is no
    # client.pay_as_you_go.create_session(). Existing PAYG subscriptions can still be
    # retrieved and managed:
    #   client.pay_as_you_go.get(subscription_uuid)
    #   client.pay_as_you_go.get_payment_history(subscription_uuid)
    #   client.pay_as_you_go.force_cancel(subscription_uuid)
