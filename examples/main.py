"""
QBitFlow SDK Usage Examples

This script demonstrates various use cases of the QBitFlow Python SDK,
including one-time payments, subscriptions, and pay-as-you-go models.
"""

from qbitflow import QBitFlow, Duration
from qbitflow.dto.transaction.status import TransactionType, TransactionStatusValue

# Your QBitFlow API key - get this from your dashboard
API_KEY = "<your_api_key_here>"

# Your application URLs
MY_URL = "http://localhost:8001"

# Initialize the QBitFlow client
client = QBitFlow(api_key=API_KEY)

print("=" * 60)
print("QBitFlow SDK Examples")
print("=" * 60)

# ============================================================================
# Example 1: Create a One-Time Payment Session with Webhook
# ============================================================================
print("\n1. Creating one-time payment with webhook...")

response_one_time = client.one_time_payments.create_session(
    product_id=1,  # Use an existing product from your dashboard
    webhook_url=f"{MY_URL}/webhook",  # Webhook URL for payment notifications
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695",  # Customer UUID
)

print(f"✓ Payment session created!")
print(f"  - Session UUID: {response_one_time.uuid}")
print(f"  - Payment Link: {response_one_time.link}")
print(f"  - Expires At: {response_one_time.expires_at}")
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
    success_url=f"{MY_URL}/success?uuid={{{{UUID}}}}&transactionType={{{{TRANSACTION_TYPE}}}}",
    cancel_url=f"{MY_URL}/cancel",
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695",
)

print(f"✓ Payment session created with redirects!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Payment Link: {response.link}")

# ============================================================================
# Example 3: Create a One-Time Payment without Pre-created Product
# ============================================================================
print("\n3. Creating one-time payment with custom product details...")

response = client.one_time_payments.create_session(
    product_name="Premium Feature Access",
    description="One-time access to premium features",
    price=49.99,  # Price in USD
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695",
    webhook_url=f"{MY_URL}/webhook",
)

print(f"✓ Custom payment session created!")
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
    webhook_url=f"{MY_URL}/webhook",
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695"
)

print(f"✓ Subscription session created!")
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
    trial_period=None,  # No trial period
    webhook_url=f"{MY_URL}/webhook",
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695",
    success_url=f"{MY_URL}/success?uuid={{{{UUID}}}}",
    cancel_url=f"{MY_URL}/cancel"
)

print(f"✓ Weekly subscription session created!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Subscription Link: {response.link}")

# ============================================================================
# Example 6: Create a Pay-as-You-Go Subscription
# ============================================================================
print("\n6. Creating pay-as-you-go subscription...")

response = client.pay_as_you_go.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),  # Billing cycle
    free_credits=10.0,  # $10 free credits (optional)
    webhook_url=f"{MY_URL}/webhook",
    customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695"
)

print(f"✓ Pay-as-you-go subscription created!")
print(f"  - Session UUID: {response.uuid}")
print(f"  - Subscription Link: {response.link}")
print(f"  - Free Credits: $10.00")
print(f"  - Minimum Periods: 3")

# ============================================================================
# Example 7: Get Payment Session Details
# ============================================================================
print("\n7. Retrieving payment session details...")

session_uuid = response_one_time.uuid  # Using UUID from previous example
session = client.one_time_payments.get_session(session_uuid)

print(f"✓ Session details retrieved!")
print(f"  - Product: {session.product_name}")
print(f"  - Description: {session.description}")
print(f"  - Price: ${session.price} USD")
print(f"  - Organization: {session.organization_name}")
print(f"  - Available Currencies: {len(session.available_currencies)}")

# ============================================================================
# Example 8: Check Transaction Status
# ============================================================================
print("\n8. Checking transaction status...")

try:
    # This will work once the customer completes the payment
    status = client.transaction_status.get(
        transaction_uuid=session_uuid,
        transaction_type=TransactionType.ONE_TIME_PAYMENT
    )
    
    print(f"✓ Transaction status retrieved!")
    print(f"  - Type: {status.type.value}")
    print(f"  - Status: {status.status.value}")
    
    if status.status == TransactionStatusValue.COMPLETED:
        print(f"  - Transaction Hash: {status.tx_hash}")
    elif status.status == TransactionStatusValue.FAILED:
        print(f"  - Error Message: {status.message}")
        
except Exception as e:
    print(f"⚠ Status not available yet (payment not started): {e}")

# ============================================================================
# Example 9: List All Payments with Pagination
# ============================================================================
print("\n9. Listing recent payments...")

try:
    # Get first page of payments
    page = client.one_time_payments.get_all(limit=5)
    
    print(f"✓ Retrieved {len(page.items)} payment(s)")
    for payment in page.items:
        print(f"  - {payment.uuid}: ${payment.amount} ({payment.currency.symbol})")
    
    # Check if there are more pages
    if page.has_more():
        print(f"  - More payments available (cursor: {page.next_cursor})")
    else:
        print("  - No more payments")
        
except Exception as e:
    print(f"⚠ Could not retrieve payments: {e}")

# ============================================================================
# Example 10: Customer Management
# ============================================================================
print("\n10. Customer management...")

from qbitflow.dto.customer import CreateCustomerDto

try:
    # Create a new customer
    customer_data = CreateCustomerDto(
        name="Alice",
        last_name="Johnson",
        email="alice@example.com",
        phone_number="+1234567890",
        reference="DEMO-CUST-001" # Optional reference ID
    )
    
    new_customer = client.customers.create(customer_data)
    print(f"✓ Customer created!")
    print(f"  - UUID: {new_customer.uuid}")
    print(f"  - Name: {new_customer.name} {new_customer.last_name}")
    print(f"  - Email: {new_customer.email}")
    
except Exception as e:
    print(f"⚠ Could not create customer: {e}")

print("\n" + "=" * 60)
print("Examples completed! Check your QBitFlow dashboard for details.")
print("=" * 60)
