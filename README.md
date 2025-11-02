# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MPL-2.0](https://img.shields.io/pypi/l/qtwebview2)](https://opensource.org/licenses/MPL-2.0)

Official Python SDK for [QBitFlow](https://qbitflow.app) - a comprehensive cryptocurrency payment processing platform that enables seamless integration of crypto payments, recurring subscriptions, and pay-as-you-go models into your applications.

## Features

-   🔐 **Type-Safe**: Full type hints for better IDE support
-   🚀 **Easy to Use**: Simple, intuitive API design
-   🔄 **Automatic Retries**: Built-in retry logic for failed requests
-   ⚡ **Real-time Updates**: WebSocket support for transaction status monitoring
-   🧪 **Well Tested**: Comprehensive test coverage
-   📚 **Great Documentation**: Detailed docs with examples
-   🔌 **Webhook Support**: Handle payment notifications easily
-   💳 **One-Time Payments**: Accept cryptocurrency payments with ease
-   🔄 **Recurring Subscriptions**: Automated recurring billing in cryptocurrency
-   📊 **Pay-as-You-Go**: Usage-based billing with cryptocurrency
-   👥 **Customer Management**: Create and manage customer profiles
-   🛍️ **Product Management**: Organize your products and pricing
-   📈 **Transaction Tracking**: Real-time transaction status updates
-   🔐 **Secure Authentication**: API key-based authentication
-   📝 **Comprehensive Documentation**: Detailed docstrings and examples

## Table of Contents

-   [Features](#features)
-   [Installation](#installation)
-   [Quick Start](#quick-start)
    -   [1. Get Your API Key](#1-get-your-api-key)
    -   [2. Initialize the Client](#2-initialize-the-client)
    -   [3. Create a One-Time Payment](#3-create-a-one-time-payment)
    -   [4. Create a Recurring Subscription](#4-create-a-recurring-subscription)
    -   [5. Check Transaction Status](#5-check-transaction-status)
-   [Configuration](#configuration)
-   [One-Time Payments](#one-time-payments)
    -   [Create a Payment Session](#create-a-payment-session)
    -   [With Redirect URLs](#with-redirect-urls)
    -   [Get Payment Session](#get-payment-session)
    -   [Get Completed Payment](#get-completed-payment)
    -   [List All Payments](#list-all-payments)
    -   [List Combined Payments](#list-combined-payments)
-   [Subscriptions](#subscriptions)
    -   [Create a Subscription](#create-a-subscription)
    -   [Frequency Units](#frequency-units)
    -   [Get Subscription](#get-subscription)
    -   [Get all payments for subscription](#get-all-payments-for-subscription)
-   [Pay-As-You-Go Subscriptions](#pay-as-you-go-subscriptions)
    -   [Create PAYG Subscription](#create-payg-subscription)
    -   [Get PAYG Subscription](#get-payg-subscription)
    -   [Get all payments for PAYG subscription](#get-all-payments-for-payg-subscription)
    -   [Increase units current period](#increase-units-current-period)
-   [Transaction Status](#transaction-status)
    -   [Check Status](#check-status)
    -   [Transaction Types](#transaction-types)
    -   [Status Values](#status-values)
-   [Customer Management](#customer-management)
    -   [Create a Customer](#create-a-customer)
    -   [Get Customer by UUID](#get-customer-by-uuid)
    -   [Update Customer](#update-customer)
    -   [Delete Customer](#delete-customer)
-   [Product Management](#product-management)
    -   [Create a Product](#create-a-product)
    -   [Update Product](#update-product)
    -   [Delete Product](#delete-product)
-   [Webhook Handling](#webhook-handling)
    -   [FastAPI Example](#fastapi-example)
-   [Error Handling](#error-handling)
-   [API Reference](#api-reference)
    -   [QBitFlow](#qbitflow)
        -   [Constructor](#constructor)
        -   [Properties](#properties)
-   [License](#license)
-   [Support](#support)
-   [Changelog](#changelog)

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

## Quick Start

### 1. Get Your API Key

Sign up at [QBitFlow](https://qbitflow.app) and obtain your API key from the dashboard.

### 2. Initialize the Client

```python
from qbitflow import QBitFlow

# Initialize the client
client = QBitFlow(api_key="your_api_key_here")
```

### 3. Create a One-Time Payment

```python
# Create a payment session
response = client.one_time_payments.create_session(
	product_id=1,
	customer_uuid="customer-uuid",
	webhook_url="https://your-domain.com/webhook",
	success_url="https://your-domain.com/success",
	cancel_url="https://your-domain.com/cancel"
)

print(f"Payment link: {response.link}")
# Send this link to your customer
```

### 4. Create a Recurring Subscription

```python
from qbitflow import Duration

# Create a monthly subscription
response = client.subscriptions.create_session(
	product_id=1,
	frequency=Duration(value=1, unit="months"),
	trial_period=Duration(value=7, unit="days"),  # Optional 7-day trial
	customer_uuid="customer-uuid",
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

### Configuration Options

| Option        | Type   | Default                    | Description                                  |
| ------------- | ------ | -------------------------- | -------------------------------------------- |
| `api_key`     | string | (required)                 | Your QBitFlow API key                        |
| `base_url`    | string | `https://api.qbitflow.app` | API base URL                                 |
| `timeout`     | int    | `30`                       | Request timeout in seconds                   |
| `max_retries` | int    | `3`                        | Number of retry attempts for failed requests |

## One-Time Payments

### Create a Payment Session

Create a payment session for a one-time purchase:

```python
# Create a payment from an existing product
response = client.one_time_payments.create_session(
	product_id=1,
	customer_uuid="customer-uuid",  # optional
	webhook_url="https://your-domain.com/webhook",
)

# Or create a custom payment
response = client.one_time_payments.create_session(
	product_name="Custom Product",
	description="Product description",
	price=99.99,  # USD
	customer_uuid="customer-uuid",
	webhook_url="https://your-domain.com/webhook",
)

print(response.uuid)  # Session UUID
print(response.link)  # Payment link for customer
```

### With Redirect URLs

You can provide redirect URLs for success and cancellation:

```python
response = client.one_time_payments.create_session(
	product_id=1,
	success_url="https://your-domain.com/success?uuid={{UUID}}&type={{TRANSACTION_TYPE}}",
	cancel_url="https://your-domain.com/cancel",
	customer_uuid="customer-uuid",
)
```

**Available Placeholders:**

-   `{{UUID}}`: The session UUID
-   `{{TRANSACTION_TYPE}}`: The transaction type (e.g., "payment", "subscription", "payAsYouGo")

### Get Payment Session

Retrieve details of a payment session:

```python
session = client.one_time_payments.get_session("session-uuid")
print(session.product_name, session.price)
```

### Get Completed Payment

Retrieve details of a completed payment:

```python
payment = client.one_time_payments.get("payment-uuid")
print(payment.transaction_hash, payment.amount)
```

### List All Payments

List all one-time payments with pagination:

```python
page = client.one_time_payments.get_all(limit=10)

print(page.items)  # Array of payments
print(page.has_more())  # Whether there are more pages
print(page.next_cursor)  # Cursor for next page

# Fetch next page
if page.has_more():
	next_page = client.one_time_payments.get_all(
		limit=10,
		cursor=page.next_cursor
	)
```

### List Combined Payments

Get all payments (one-time and subscription payments combined):

```python
combined = client.one_time_payments.get_all_combined(limit=20)
for payment in combined.items:
	print(payment.source)  # "payment" or "subscription_history"
	print(payment.amount)
```

## Subscriptions

### Create a Subscription

Create a recurring subscription:

```python
response = client.subscriptions.create_session(
	product_id=1,
	frequency=Duration(value=1, unit="months"),  # Bill monthly
	trial_period=Duration(value=7, unit="days"),  # 7-day trial (optional)
	webhook_url="https://your-domain.com/webhook",
	customer_uuid="customer-uuid",
)

print(response.link)  # Send to customer
```

### Frequency Units

Available units for `frequency` and `trial_period`:

-   `seconds`
-   `minutes`
-   `hours`
-   `days`
-   `weeks`
-   `months`

### Get Subscription

Retrieve subscription details:

```python
subscription = client.subscriptions.get("subscription-uuid")
print(subscription.status, subscription.next_billing_date)
```

### Get all payments for subscription

```python
history = client.subscriptions.get_payment_history("subscription-uuid")
for record in history:
	print(record.uuid, record.amount, record.created_at)
```

## Pay-As-You-Go Subscriptions

PAYG subscriptions allow customers to pay based on usage with a billing cycle.

### Create PAYG Subscription

```python
response = client.pay_as_you_go.create_session(
	product_id=1,
	frequency=Duration(value=1, unit="months"),  # Bill monthly
	free_credits=100,  # Initial free credits (optional)
	webhook_url="https://your-domain.com/webhook",
	customer_uuid="customer-uuid",
)

print(response.link)
```

### Get PAYG Subscription

```python
payg = client.pay_as_you_go.get("payg-uuid")
print(payg.allowance, payg.units_current_period)
```

### Get all payments for PAYG subscription

```python
history = client.pay_as_you_go.get_payment_history("payg-uuid")
for record in history:
	print(record.uuid, record.amount, record.created_at)
```

### Increase units current period

Increase the number of units for the current billing period:

```python
# For example, the product is billed per hour of usage, and the customer consumed 5 additional hours
response = client.pay_as_you_go.increase_units_current_period("payg-uuid", 5)
print(f"New units this period: {response.units_current_period}")
```

## Transaction Status

### Check Status

Get the current status of a transaction:

```python
from qbitflow import TransactionType

status = client.transaction_status.get(
	"transaction-uuid",
	TransactionType.ONE_TIME_PAYMENT
)

print(status.status)  # "created", "pending", "completed", etc.
print(status.tx_hash)  # Blockchain transaction hash
```

### Transaction Types

```python
class TransactionType:
	# One-time payment transaction
	ONE_TIME_PAYMENT = 'payment'
	# Create subscription transaction
	CREATE_SUBSCRIPTION = 'createSubscription'
	# Cancel subscription transaction
	CANCEL_SUBSCRIPTION = 'cancelSubscription'
	# Execute subscription payment transaction
	EXECUTE_SUBSCRIPTION_PAYMENT = 'executeSubscription'
	# Create pay-as-you-go subscription transaction
	CREATE_PAYG_SUBSCRIPTION = 'createPAYGSubscription'
	# Cancel pay-as-you-go subscription transaction
	CANCEL_PAYG_SUBSCRIPTION = 'cancelPAYGSubscription'
	# Increase allowance transaction
	INCREASE_ALLOWANCE = 'increaseAllowance'
	# Update max amount transaction
	UPDATE_MAX_AMOUNT = 'updateMaxAmount'
```

### Status Values

```python
class TransactionStatusValue:
	# Transaction has been created but not yet processed
	CREATED = 'created'
	# Waiting for blockchain confirmation
	WAITING_CONFIRMATION = 'waitingConfirmation'
	# Transaction is pending processing
	PENDING = 'pending'
	# Transaction has been successfully completed
	COMPLETED = 'completed'
	# Transaction has failed
	FAILED = 'failed'
	# Transaction has been cancelled
	CANCELLED = 'cancelled'
	# Transaction has expired
	EXPIRED = 'expired'
```

## Customer Management

### Create a Customer

```python
customer_data = CreateCustomerDto(
	name="John",
	last_name="Doe",
	email="john@example.com",
	phone_number="+1234567890",
	reference="CRM-12345"
)

customer = client.customers.create(customer_data)
print(f"Customer created: {customer.uuid}")
```

### Get Customer by UUID

```python
customer = client.customers.get("customer-uuid")
print(f"{customer.name} {customer.last_name} - {customer.email}")
```

### Update Customer

```python
update_data = UpdateCustomerDto(
	name="John",
	last_name="Doe",
	email="john.doe@example.com",
	phone_number="+9876543210"
)

updated_customer = client.customers.update("customer-uuid", update_data)
```

### Delete Customer

```python
response = client.customers.delete("customer-uuid")
print(response.message)
```

## Product Management

### Create a Product

```python
product_data = CreateProductDto(
	name="Premium Subscription",
	description="Access to all premium features",
	price=29.99,
	reference="PROD-PREMIUM"
)

product = client.products.create(product_data)
print(f"Product created: ID {product.id}")
```

### Update Product

```python
update_data = UpdateProductDto(
	name="Premium Plus",
	description="Enhanced premium features",
	price=39.99
)

updated_product = client.products.update(1, update_data)
```

### Delete Product

```python
response = client.products.delete(1)
```

## Webhook Handling

### FastAPI Example

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
		print(f"Payment completed: {event.session.product_name}")
		print(f"Customer: {event.session.customer_uuid}")
		print(f"Amount: ${event.session.price}")

	elif event.status.status == TransactionStatusValue.FAILED:
		print(f"Payment failed: {event.status.message}")

	return {"received": True}
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
	print(f"SDK error: {e.message}")
```

## API Reference

### QBitFlow

Main client class.

#### Constructor

```python
QBitFlow(api_key: str, timeout: Optional[int] = None, max_retries: Optional[int] = None)
```

#### Properties

-   `customers: CustomerRequests` - Customer operations
-   `products: ProductRequests` - Product operations
-   `users: UserRequests` - User operations
-   `api_keys: ApiKeyRequests` - API key operations
-   `one_time_payments: PaymentRequests` - One-time payment operations
-   `subscriptions: SubscriptionRequests` - Subscription operations
-   `pay_as_you_go: PayAsYouGoRequests` - Pay-as-you-go operations
-   `transaction_status: TransactionStatusRequests` - Transaction status operations

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

## License

This project is licensed under the MPL-2.0 License - see the [LICENSE](LICENSE) file for details.

## Support

-   📖 [Documentation](https://qbitflow.app/docs)
-   📧 [Email Support](mailto:support@qbitflow.app)
-   🐛 [Issue Tracker](https://github.com/qbitflow/qbitflow-python-sdk/issues)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes in each version.

## Security

For security issues, please email security@qbitflow.app instead of using the issue tracker.

---

Made with ❤️ by [QBitFlow](https://qbitflow.app)
