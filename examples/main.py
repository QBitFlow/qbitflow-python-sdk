"""
QBitFlow SDK Usage Examples

This script demonstrates various use cases of the QBitFlow Python SDK,
including one-time payments, subscriptions, customers and transaction status.

Run with:
    export QBITFLOW_API_KEY="<your_api_key>"
    export QBITFLOW_BASE_URL="https://api.qbitflow.app/v1"   # optional
    export QBITFLOW_CUSTOMER_UUID="<a customer uuid>"         # optional
    python examples/main.py
"""

import os
from datetime import date, timedelta

from qbitflow import Duration, QBitFlow
from qbitflow.dto.customer import CreateCustomerDto
from qbitflow.dto.transaction.status import TransactionStatusValue, TransactionType
from qbitflow.exceptions import NotFoundException, QBitFlowError

# Your QBitFlow API key - get this from your dashboard. Never hardcode it.
API_KEY = os.environ["QBITFLOW_API_KEY"]

# Optional: a bare customer UUID (from client.customers) to pre-fill the checkout. Leave it
# unset to let the customer enter their details during checkout.
CUSTOMER_UUID = os.getenv("QBITFLOW_CUSTOMER_UUID") or None

# Your application URLs (see examples/server.py)
MY_URL = "http://localhost:8001"

# Initialize the QBitFlow client (QBITFLOW_BASE_URL, when set, selects the API server)
client = QBitFlow(api_key=API_KEY, base_url=os.getenv("QBITFLOW_BASE_URL"))

print("=" * 60)
print("QBitFlow SDK Examples")
print("=" * 60)

# ============================================================================
# Example 1: Create a One-Time Payment Session
# (Webhook notifications are configured in the QBitFlow dashboard settings)
# ============================================================================
print("\n1. Creating one-time payment...")

response_one_time = client.one_time_payments.create_session(
    product_id=1,  # Use an existing product from your dashboard
    customer_uuid=CUSTOMER_UUID,
)

print("✓ Payment session created!")
print(f"  - Session UUID: {response_one_time.uuid}")
print(f"  - Payment Link: {response_one_time.link}")
print("\nSend this link to your customer to complete the payment.")

# ============================================================================
# Example 2: Create a One-Time Payment with Redirect URLs
# ============================================================================
print("\n2. Creating one-time payment with redirect URLs...")

# You can use placeholders in redirect URLs:
# - {{UUID}}: Replaced with the payment session UUID
# - {{TRANSACTION_TYPE}}: Replaced with the transaction type
response = client.one_time_payments.create_session(
    product_id=1,
    success_url=f"{MY_URL}/success?uuid={{{{UUID}}}}&transaction_type={{{{TRANSACTION_TYPE}}}}",
    cancel_url=f"{MY_URL}/cancel",
    customer_uuid=CUSTOMER_UUID,
)

print("✓ Payment session created with redirects!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Payment Link: {response.link}")

# ============================================================================
# Example 3: Create a One-Time Payment without Pre-created Product
# ============================================================================
print("\n3. Creating one-time payment with custom product details...")

response = client.one_time_payments.create_session(
    product_name="Premium Feature Access",
    description="One-time access to premium features",
    price=49.99,  # Price in USD, must be greater than 0
)

print("✓ Custom payment session created!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Payment Link: {response.link}")

# ============================================================================
# Example 4: Create a Monthly Subscription
# ============================================================================
print("\n4. Creating monthly subscription...")

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),  # Bill every month
    trial_period=Duration(value=7, unit="days"),  # 7-day free trial (optional)
    customer_uuid=CUSTOMER_UUID,
)

print("✓ Subscription session created!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Subscription Link: {response.link}")
print("  - Includes 7-day free trial")

# ============================================================================
# Example 5: Create a Weekly Subscription without Trial
# ============================================================================
print("\n5. Creating weekly subscription...")

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="weeks"),  # Bill every week
    min_periods=3,  # The customer commits to at least 3 weeks
    success_url=f"{MY_URL}/success?uuid={{{{UUID}}}}&transaction_type={{{{TRANSACTION_TYPE}}}}",
    cancel_url=f"{MY_URL}/cancel",
)

print("✓ Weekly subscription session created!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Subscription Link: {response.link}")

# ============================================================================
# Example 6: Get Payment Session Details
# ============================================================================
print("\n6. Retrieving payment session details...")

session_uuid = response_one_time.uuid  # Using UUID from the first example
session = client.one_time_payments.get_session(session_uuid)

print("✓ Session details retrieved!")
print(f"  - Product: {session.product_name}")
print(f"  - Description: {session.description}")
print(f"  - Price: ${session.price} USD")
print(f"  - Organization: {session.organization_name}")
print(f"  - Available Currencies: {len(session.available_currencies)}")

# ============================================================================
# Example 7: Check Transaction Status
# ============================================================================
print("\n7. Checking transaction status...")

try:
    # This will work once the customer has started the payment
    status = client.transaction_status.get(
        transaction_uuid=session_uuid, transaction_type=TransactionType.ONE_TIME_PAYMENT
    )

    print("✓ Transaction status retrieved!")
    print(f"  - Status: {status.status}")

    if status.status == TransactionStatusValue.COMPLETED:
        print(f"  - Transaction Hash: {status.tx_hash}")
    elif status.status == TransactionStatusValue.FAILED:
        print(f"  - Error Message: {status.message}")

except NotFoundException:
    print("⚠ Status not available yet (the customer has not started the payment)")

# ============================================================================
# Example 8: List All Payments with Pagination
# ============================================================================
print("\n8. Listing recent payments...")

page = client.one_time_payments.get_all(limit=5)

print(f"✓ Retrieved {len(page.items)} payment(s)")
for payment in page.items:
    print(f"  - {payment.uuid}: ${payment.amount} ({payment.currency.symbol})")

if page.has_more():
    print(f"  - More payments available (cursor: {page.next_cursor})")
else:
    print("  - No more payments")

# ============================================================================
# Example 9: Accounting export for the last month
# ============================================================================
print("\n9. Exporting last month's accounting events...")

today = date.today()
events = client.accounting.export(
    (today - timedelta(days=30)).isoformat(), today.isoformat(), "json"
)
print(f"✓ {len(events)} accounting event(s)")

# ============================================================================
# Example 10: Customer Management
# ============================================================================
print("\n10. Customer management...")

try:
    new_customer = client.customers.create(
        CreateCustomerDto(
            name="Alice",
            last_name="Johnson",
            email=f"alice+{os.urandom(3).hex()}@example.com",
            phone_number="+1234567890",
            reference=f"DEMO-CUST-{os.urandom(3).hex()}",  # Optional, unique per owner
        )
    )
    print("✓ Customer created!")
    print(f"  - UUID: {new_customer.uuid}")
    print(f"  - Name: {new_customer.name} {new_customer.last_name}")
    print(f"  - Email: {new_customer.email}")

except QBitFlowError as e:
    print(f"⚠ Could not create customer: {e}")

client.close()

print("\n" + "=" * 60)
print("Examples completed! Check your QBitFlow dashboard for details.")
print("=" * 60)
