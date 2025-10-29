import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qbitflow import QBitFlow
from qbitflow.dto.transaction.status import TransactionStatusValue, TransactionType
from qbitflow.utils.duration import Duration


CUSTOMER_UUID = "<your_test_customer_uuid>" # Replace with your test customer UUID

if __name__ == "__main__":
    key = os.getenv("QBITFLOW_API_KEY")
    if not key:
        raise EnvironmentError("QBITFLOW_API_KEY environment variable not set")
    
    client = QBitFlow(api_key=key)


    #################### One-Time Payment ####################

    # Create a payment, process it, and retrieve its status
    payment = client.one_time_payments.create_session(
        product_id=1,
        customer_uuid=CUSTOMER_UUID
    )

    print(f"Payment link: {payment.link}")
    input("Press Enter after completing the payment...")

    # Retrieve payment status
    status = client.transaction_status.get(
        transaction_uuid=payment.uuid,
        transaction_type=TransactionType.ONE_TIME_PAYMENT
    )
    print(f"Payment Status: {status.status}")
    assert status.status == TransactionStatusValue.COMPLETED, "Payment was not completed successfully"

    # Retrieve from the database
    payment_details = client.one_time_payments.get(payment.uuid)
    print(f"Payment Amount: ${payment_details.amount}")
    print(f"Transaction Hash: {payment_details.transaction_hash}")



    
    #################### Subscription ####################

    sub = client.subscriptions.create_session(
        product_id=1,
        frequency=Duration(value=1, unit="months"),
        customer_uuid=CUSTOMER_UUID
    )
    print(f"Subscription link: {sub.link}")
    input("Press Enter after completing the subscription...")

    # Retrieve subscription status
    status = client.transaction_status.get(
        transaction_uuid=sub.uuid,
        transaction_type=TransactionType.CREATE_SUBSCRIPTION
    )
    print(f"Subscription Status: {status.status}")
    assert status.status == TransactionStatusValue.COMPLETED, "Subscription was not activated successfully"

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


    
    #################### Pay-as-you-go ####################

    payg = client.pay_as_you_go.create_session(
        product_id=1,
        frequency=Duration(value=1, unit="months"),
        free_credits=10.0,
        customer_uuid=CUSTOMER_UUID
    )
    print(f"PAYG link: {payg.link}")
    input("Press Enter after completing the PAYG subscription...")

    # Retrieve PAYG subscription status
    status = client.transaction_status.get(
        transaction_uuid=payg.uuid,
        transaction_type=TransactionType.CREATE_PAYG_SUBSCRIPTION
    )
    print(f"PAYG Subscription Status: {status.status}")
    assert status.status == TransactionStatusValue.COMPLETED, "PAYG Subscription was not activated successfully"

    # Retrieve PAYG subscription from the database
    payg_details = client.pay_as_you_go.get(payg.uuid)
    print(f"PAYG Subscription Product ID: {payg_details.product_id}")
    print(f"PAYG Subscription Status: {payg_details.subscription_status}")


    # Increase the usage
    client.pay_as_you_go.increase_units_current_period(
        subscription_uuid=payg.uuid,
        increase_amount=5.0 # product price is 9.99 USD, so 5 * 9.99 = 49.95 USD total usage (over the free credits of 10 USD)
    )

    input("Press enter after running the billing job...")

    # Retrieve PAYG payment history
    payg_payment_history = client.pay_as_you_go.get_payment_history(payg.uuid)
    assert len(payg_payment_history) > 0, "No payment history found for PAYG subscription"
    # print details of the payments
    for payment in payg_payment_history:
        print(f"PAYG Payment - Amount: ${payment.amount}, Date: {payment.created_at}")

    # Force cancel a PAYG subscription
    payg_cancel_response = client.pay_as_you_go.force_cancel(payg.uuid)
    print(f"PAYG Subscription cancelled: {payg_cancel_response.message}")

    # Try and retrieve the PAYG subscription again
    try:
        payg_details = client.pay_as_you_go.get(payg.uuid)
        print(f"PAYG Subscription Product ID: {payg_details.product_id}")
        print(f"PAYG Subscription Status: {payg_details.subscription_status}")
    except Exception as e:
        print(f"Error retrieving PAYG subscription: {e}")
    
