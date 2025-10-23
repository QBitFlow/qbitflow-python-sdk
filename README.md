# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The official Python SDK for [QBitFlow](https://qbitflow.app) - a comprehensive cryptocurrency payment processing platform that enables seamless integration of crypto payments, recurring subscriptions, and pay-as-you-go models into your applications.

## Features

-   💳 **One-Time Payments**: Accept cryptocurrency payments with ease
-   🔄 **Recurring Subscriptions**: Automated recurring billing in cryptocurrency
-   📊 **Pay-as-You-Go**: Usage-based billing with cryptocurrency
-   👥 **Customer Management**: Create and manage customer profiles
-   🛍️ **Product Management**: Organize your products and pricing
-   📈 **Transaction Tracking**: Real-time transaction status updates
-   🔔 **Webhook Support**: Get notified of payment events
-   🔐 **Secure Authentication**: API key-based authentication
-   🎯 **Type-Safe**: Full type hints for better IDE support
-   📝 **Comprehensive Documentation**: Detailed docstrings and examples

## Installation

Install the SDK using pip:

```bash
pip install qbitflow
```

Or install from source:

```bash
git clone https://github.com/qbitflow/qbitflow-python-sdk.git
cd qbitflow-python-sdk
pip install -e .
```

## Requirements

-   Python 3.8 or higher
-   Dependencies:
    -   `httpx` - HTTP client
    -   `pydantic` - Data validation

## Quick Start

### 1. Get Your API Key

Sign up at [QBitFlow](https://qbitflow.app) and obtain your API key from the dashboard.

### 2. Initialize the Client

```python
from qbitflow import QBitFlow

# Initialize the client with your API key
client = QBitFlow(api_key="your_api_key_here")
```

### 3. Create a One-Time Payment

```python
# Create a payment session
response = client.one_time_payments.create_session(
    product_id=1,
    customer_uuid="customer-uuid-here",
    webhook_url="https://your-domain.com/webhook",
    success_url="https://your-domain.com/success",
    cancel_url="https://your-domain.com/cancel"
)

print(f"Payment link: {response.link}")
print(f"Session UUID: {response.uuid}")

# Send the payment link to your customer
# They will complete the payment using their preferred cryptocurrency
```

### 4. Create a Recurring Subscription

```python
from qbitflow import Duration

# Create a monthly subscription
response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),  # Optional 7-day trial
    customer_uuid="customer-uuid-here",
    webhook_url="https://your-domain.com/webhook"
)

print(f"Subscription link: {response.link}")
```

### 5. Check Transaction Status

```python
from qbitflow.dto.transaction.status import TransactionType, TransactionStatusValue

# Get transaction status
status = client.transaction_status.get(
    transaction_uuid="transaction-uuid",
    transaction_type=TransactionType.ONE_TIME_PAYMENT
)

if status.status == TransactionStatusValue.COMPLETED:
    print(f"Payment completed! Transaction hash: {status.tx_hash}")
elif status.status == TransactionStatusValue.FAILED:
    print(f"Payment failed: {status.message}")
```

## Configuration

### Environment Variables

You can configure the SDK using environment variables:

```bash
# Set custom API base URL (useful for testing)
export QBITFLOW_BASE_URL="https://api.qbitflow.app"
```

### Programmatic Configuration

```python
from qbitflow import config

# Set custom base URL
config.set_base_url("http://localhost:3001")  # For local testing

# Configure timeout and retries
client = QBitFlow(
    api_key="your_api_key",
    timeout=60,  # Request timeout in seconds
    max_retries=5  # Maximum retry attempts
)
```

## Usage Examples

### Customer Management

```python
from qbitflow.dto.customer import CreateCustomerDto, UpdateCustomerDto

# Create a new customer
customer_data = CreateCustomerDto(
    name="John",
    last_name="Doe",
    email="john@example.com",
    phone_number="+1234567890",
    reference="CRM-12345"
)
customer = client.customers.create(customer_data)
print(f"Customer created: {customer.uuid}")

# Get customer by UUID
customer = client.customers.get("customer-uuid")
print(f"{customer.name} {customer.last_name} - {customer.email}")

# Get customer by email
customer = client.customers.get_by_email("john@example.com")

# Update customer
update_data = UpdateCustomerDto(
	name="John",
    last_name="Doe",
    email="john.doe@example.com",
    phone_number="+9876543210"
)
customer = client.customers.update("customer-uuid", update_data)

# Get all customers
customers = client.customers.get_all()
for customer in customers:
    print(f"- {customer.name} ({customer.email})")

# Delete customer
response = client.customers.delete("customer-uuid")
print(response.message)
```

### Product Management

```python
from qbitflow.dto.product import CreateProductDto, UpdateProductDto

# Create a product
product_data = CreateProductDto(
    name="Premium Subscription",
    description="Access to all premium features",
    price=29.99,
    reference="PROD-PREMIUM"
)
product = client.products.create(product_data)
print(f"Product created: ID {product.id}")

# Get product by ID
product = client.products.get(1)
print(f"{product.name}: ${product.price}")

# Get all products
products = client.products.get_all()

# Update product
update_data = UpdateProductDto(
    name="Premium Plus",
    description="Enhanced premium features",
    price=39.99
)
product = client.products.update(1, update_data)

# Delete product
response = client.products.delete(1)
```

### One-Time Payments

```python
# Create payment session with product ID
response = client.one_time_payments.create_session(
    product_id=1,
    customer_uuid="customer-uuid",
    webhook_url="https://example.com/webhook",
    success_url="https://example.com/success?uuid={{UUID}}&type={{TRANSACTION_TYPE}}",
    cancel_url="https://example.com/cancel"
)

# Or create payment session with product details
response = client.one_time_payments.create_session(
    product_name="Custom Product",
    description="One-time purchase",
    price=99.99,
    customer_uuid="customer-uuid"
)

# Get payment session details
session = client.one_time_payments.get_session("session-uuid")
print(f"Product: {session.product_name}")
print(f"Price: ${session.price} USD")

# Get completed payment details
payment = client.one_time_payments.get("payment-uuid")
print(f"Amount: ${payment.amount}")
print(f"Currency: {payment.currency.name}")
print(f"Transaction Hash: {payment.transaction_hash}")

# List all payments with pagination
page = client.one_time_payments.get_all(limit=10)
for payment in page.items:
    print(f"- {payment.uuid}: ${payment.amount}")

# Get next page if available
if page.has_more():
    next_page = client.one_time_payments.get_all(
        limit=10,
        cursor=page.next_cursor
    )

# Get combined payments (one-time + subscription)
combined = client.one_time_payments.get_all_combined(limit=10)
for payment in combined.items:
    print(f"- {payment.uuid} (source: {payment.source})")
```

### Recurring Subscriptions

```python
from qbitflow import Duration

# Create subscription with monthly billing
response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=14, unit="days"),
    customer_uuid="customer-uuid",
    webhook_url="https://example.com/webhook"
)

# Get subscription details
subscription = client.subscriptions.get("subscription-uuid")
print(f"Status: {subscription.subscription_status.value}")
print(f"Next billing: {subscription.next_billing_date}")
print(f"Allowance: ${subscription.allowance}")

# Get subscription payment history
history = client.subscriptions.get_payment_history("subscription-uuid")
for payment in history:
    print(f"- {payment.created_at}: ${payment.allowance}")

# Execute test billing cycle (test mode only)
status_response = client.subscriptions.execute_test_billing_cycle("subscription-uuid")
print(f"Test billing executed: {status_response.message}")

# Force cancel subscription (use with caution!)
response = client.subscriptions.force_cancel("subscription-uuid")
```

### Pay-as-You-Go Subscriptions

```python
from qbitflow import Duration

# Create PAYG subscription
response = client.pay_as_you_go.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    free_credits=10.0,
    min_periods=3,
    customer_uuid="customer-uuid"
)

# Get PAYG subscription details
payg = client.pay_as_you_go.get("subscription-uuid")
print(f"Usage this period: {payg.units_current_period} units")
print(f"Max spending: ${payg.max_spending_per_period}")
print(f"Free credits: ${payg.free_credits}")

# Increase usage units
payg = client.pay_as_you_go.increase_units_current_period(
    subscription_uuid="subscription-uuid",
    increase_amount=5.0
)
print(f"New usage: {payg.units_current_period} units")
```

### Webhook Handling

Create a webhook endpoint to receive payment notifications:

```python
from fastapi import FastAPI
from qbitflow import QBitFlow
from qbitflow.dto.transaction.session import SessionWebhookResponse
from qbitflow.dto.transaction.status import TransactionStatusValue

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.post("/webhook")
def handle_webhook(event: SessionWebhookResponse):
    """Handle webhook events from QBitFlow."""
    print(f"Received event for session: {event.uuid}")
    print(f"Transaction status: {event.status.status.value}")

    if event.status.status == TransactionStatusValue.COMPLETED:
        # Payment completed successfully
        session = event.session
        print(f"Payment completed: {session.product_name}")
        print(f"Customer: {session.customer_uuid}")
        print(f"Amount: ${session.price}")

        # Process successful payment
        # - Grant access to product/service
        # - Update database
        # - Send confirmation email
        # etc.

    elif event.status.status == TransactionStatusValue.FAILED:
        # Payment failed
        print(f"Payment failed: {event.status.message}")

        # Handle failed payment
        # - Notify customer
        # - Log for review
        # etc.

    return {"received": True}
```

### Redirect URL Handling

Handle success and cancel redirects:

```python
from fastapi import FastAPI
from qbitflow import QBitFlow
from qbitflow.dto.transaction.status import (
    TransactionType,
    TransactionStatusValue
)

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.get("/success")
def handle_success(uuid: str, transactionType: TransactionType):
    """Handle successful payment redirect."""
    # Check transaction status
    status = client.transaction_status.get(uuid, transactionType)

    if status.status == TransactionStatusValue.COMPLETED:
        # Get payment/subscription details
        if transactionType == TransactionType.ONE_TIME_PAYMENT:
            session = client.one_time_payments.get_session(uuid)
            return {
                "status": "success",
                "product": session.product_name,
                "amount": session.price
            }

    return {"status": status.status.value}

@app.get("/cancel")
def handle_cancel():
    """Handle payment cancellation."""
    print("Payment was cancelled by the user")
    return {"status": "cancelled"}
```

## Error Handling

The SDK provides comprehensive error handling with custom exception classes:

```python
from qbitflow import QBitFlow
from qbitflow.exceptions import (
    QBitFlowError,
    AuthenticationError,
    NotFoundException,
    ValidationError,
    RateLimitError,
    NetworkError,
    APIError
)

client = QBitFlow(api_key="your_api_key")

try:
    payment = client.one_time_payments.get("non-existent-uuid")
except AuthenticationError:
    print("Invalid API key or authentication failed")
except NotFoundException as e:
    print(f"Payment not found: {e.message}")
except ValidationError as e:
    print(f"Validation error: {e.message}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e.message}")
    if e.response and 'retry_after' in e.response:
        print(f"Retry after {e.response['retry_after']} seconds")
except NetworkError as e:
    print(f"Network error: {e.message}")
except APIError as e:
    print(f"API error: {e.message} (status: {e.status_code})")
except QBitFlowError as e:
    # Catch all SDK errors
    print(f"SDK error: {e.message}")
```

## API Reference

### Main Client

-   `QBitFlow(api_key, timeout=None, max_retries=None)` - Initialize the client

### Customer Methods

-   `customers.create(data)` - Create a new customer
-   `customers.get(customer_uuid)` - Get customer by UUID
-   `customers.get_by_email(email)` - Get customer by email
-   `customers.get_all()` - Get all customers
-   `customers.update(customer_uuid, data)` - Update customer
-   `customers.delete(customer_uuid)` - Delete customer

### Product Methods

-   `products.create(data)` - Create a new product
-   `products.get(product_id)` - Get product by ID
-   `products.get_all()` - Get all products
-   `products.get_by_reference(reference)` - Get product by reference
-   `products.update(product_id, data)` - Update product
-   `products.delete(product_id)` - Delete product

### Payment Methods

-   `one_time_payments.create_session(...)` - Create payment session
-   `one_time_payments.get_session(session_uuid)` - Get session details
-   `one_time_payments.get(payment_uuid)` - Get completed payment
-   `one_time_payments.get_all(limit, cursor)` - List payments with pagination
-   `one_time_payments.get_all_combined(limit, cursor)` - List all payments

### Subscription Methods

-   `subscriptions.create_session(...)` - Create subscription session
-   `subscriptions.get_session(session_uuid)` - Get session details
-   `subscriptions.get(subscription_uuid)` - Get subscription
-   `subscriptions.get_payment_history(subscription_uuid)` - Get payment history
-   `subscriptions.force_cancel(subscription_uuid)` - Force cancel subscription
-   `subscriptions.execute_test_billing_cycle(subscription_uuid)` - Test billing

### Pay-as-You-Go Methods

-   `pay_as_you_go.create_session(...)` - Create PAYG session
-   `pay_as_you_go.get(subscription_uuid)` - Get PAYG subscription
-   `pay_as_you_go.increase_units_current_period(...)` - Increase usage units

### Transaction Status Methods

-   `transaction_status.get(transaction_uuid, transaction_type)` - Get status

## Testing

Run the integration tests:

```bash
# Set your test API key
export QBITFLOW_API_KEY="your_test_api_key"
export QBITFLOW_BASE_URL="http://localhost:3001"  # If using local test server

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=qbitflow --cov-report=html
```

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/qbitflow/qbitflow-python-sdk.git
cd qbitflow-python-sdk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
flake8 qbitflow tests

# Format code
black qbitflow tests
```

### Project Structure

```
qbitflow-python-sdk/
├── qbitflow/              # Main package
│   ├── __init__.py       # Package initialization
│   ├── client.py         # Main QBitFlow client
│   ├── config.py         # Configuration
│   ├── dto/              # Data Transfer Objects
│   ├── exceptions/       # Custom exceptions
│   ├── requests/         # API request handlers
│   └── utils/            # Utility functions
├── tests/                # Integration tests
├── examples/             # Example scripts
├── docs/                 # Documentation
├── setup.py              # Package setup
├── pyproject.toml        # Build configuration
├── README.md             # This file
└── LICENSE               # MIT License
```

## Support

-   📖 [Documentation](https://qbitflow.app/docs)
-   💬 [Community Forum](https://community.qbitflow.app)
-   📧 [Email Support](mailto:support@qbitflow.app)
-   🐛 [Issue Tracker](https://github.com/qbitflow/qbitflow-python-sdk/issues)

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes in each version.

## Security

For security issues, please email security@qbitflow.app instead of using the issue tracker.

## Acknowledgments

-   Built with ❤️ by the QBitFlow team
-   Powered by [httpx](https://www.python-httpx.org/) and [Pydantic](https://pydantic-docs.helpmanual.io/)

---

Made with ❤️ by [QBitFlow](https://qbitflow.app)
