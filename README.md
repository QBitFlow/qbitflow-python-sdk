# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MPL-2.0](https://img.shields.io/pypi/l/qtwebview2)](https://opensource.org/licenses/MPL-2.0)

Official Python SDK for [QBitFlow](https://qbitflow.app) - a comprehensive cryptocurrency payment processing platform that enables seamless integration of crypto payments, recurring subscriptions, and usage-based billing into your applications.

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
-   👥 **Customer Management**: Create and manage customer profiles
-   🛍️ **Product Management**: Organize your products and pricing
-   📈 **Transaction Tracking**: Real-time transaction status updates
-   💸 **Refund Tracking**: Monitor refund status
-   📊 **Accounting Export**: Export transaction data as JSON or CSV
-   🔑 **Account Claims**: Invite unclaimed users to set up their wallets

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
    -   [Get Customer for Transaction](#get-customer-for-transaction)
-   [Subscriptions](#subscriptions)
    -   [Create a Subscription](#create-a-subscription)
    -   [Frequency Units](#frequency-units)
    -   [Get Subscription](#get-subscription)
    -   [Get Payment History](#get-payment-history)
    -   [Force Cancel](#force-cancel)
    -   [Execute Test Billing Cycle](#execute-test-billing-cycle)
-   [Refunds](#refunds)
    -   [List Active Refunds](#list-active-refunds)
    -   [List Inactive Refunds](#list-inactive-refunds)
    -   [Get Refund by Transaction](#get-refund-by-transaction)
-   [Accounting Export](#accounting-export)
-   [Account Claims](#account-claims)
    -   [Get a Claim Request](#get-a-claim-request)
    -   [Create a Claim Request](#create-a-claim-request)
    -   [Get Claim Funds](#get-claim-funds)
    -   [Trigger Test Claim Funds](#trigger-test-claim-funds)
-   [Transaction Status](#transaction-status)
    -   [Check Status](#check-status)
    -   [Transaction Types](#transaction-types)
    -   [Status Values](#status-values)
-   [Customer Management](#customer-management)
-   [Product Management](#product-management)
-   [User Management](#user-management)
-   [API Key Management](#api-key-management)
-   [Webhook Handling](#webhook-handling)
    -   [Configuring Webhooks](#configuring-webhooks)
    -   [Transaction Webhook](#transaction-webhook)
    -   [Subscription Status Webhook](#subscription-status-webhook)
-   [Error Handling](#error-handling)
-   [API Reference](#api-reference)
-   [License](#license)

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

client = QBitFlow(api_key="your_api_key_here")
```

### 3. Create a One-Time Payment

```python
response = client.one_time_payments.create_session(
    product_id=1,
    customer_uuid="customer-uuid",
    success_url="https://your-domain.com/success",
    cancel_url="https://your-domain.com/cancel"
)

print(f"Payment link: {response.link}")
# Send this link to your customer
```

### 4. Create a Recurring Subscription

```python
from qbitflow import Duration

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),  # Optional 7-day trial
    customer_uuid="customer-uuid"
)

print(f"Subscription link: {response.link}")
```

### 5. Check Transaction Status

```python
from qbitflow.dto.transaction.status import TransactionType, TransactionStatusValue

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

Provide either a `product_id` for an existing product, or `product_name` + `description` + `price` for an ad-hoc charge:

```python
# From an existing product
response = client.one_time_payments.create_session(
    product_id=1,
    customer_uuid="customer-uuid"
)

# Ad-hoc payment
response = client.one_time_payments.create_session(
    product_name="Custom Product",
    description="Product description",
    price=99.99,  # USD
    customer_uuid="customer-uuid"
)

print(response.uuid)  # Session UUID
print(response.link)  # Payment link for customer
```

#### Using your own references

Instead of storing QBitFlow's internal UUIDs, pass your own identifiers. Set `reference` to your
order/invoice ID, and use `product_reference` / `customer_reference` to select an existing product
or customer by your own reference:

```python
response = client.one_time_payments.create_session(
    reference="order-1234",            # your own transaction reference
    product_reference="PROD-PREMIUM",  # use a product by your reference (instead of product_id)
    customer_reference="user-42",      # use a customer by your reference (instead of customer_uuid)
)
```

The `reference` is echoed back on the resulting `Payment` and in webhook payloads, and you can look
the payment up later with [`get_by_reference()`](#get-payment-by-reference). If no customer matches
`customer_reference`, one is created during checkout.

### With Redirect URLs

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
-   `{{TRANSACTION_TYPE}}`: The transaction type (e.g., "payment", "subscription")

### Get Payment Session

Returns a `OneTimePaymentSession` with the base transaction fields.

```python
session = client.one_time_payments.get_session("session-uuid")
print(session.product_name, session.price)
```

### Get Completed Payment

```python
payment = client.one_time_payments.get("payment-uuid")
print(payment.transaction_hash, payment.amount)
```

### Get Payment by Reference

Look a payment up by the `reference` you assigned when creating the session — no need to store
QBitFlow's UUID:

```python
payment = client.one_time_payments.get_by_reference("order-1234")
print(payment.uuid, payment.amount)
```

### List All Payments

```python
page = client.one_time_payments.get_all(limit=10)

print(page.items)      # List of Payment objects
print(page.has_more()) # Whether there are more pages
print(page.next_cursor)

if page.has_more():
    next_page = client.one_time_payments.get_all(limit=10, cursor=page.next_cursor)
```

### List Combined Payments

Get all payments from both one-time and subscription sources in a single paginated list:

```python
page = client.one_time_payments.get_all_combined(limit=20)
for item in page.items:
    print(item.source)  # "payment" or "subscription_history"
    print(item.amount)
    if item.subscription_uuid:
        print(f"Subscription: {item.subscription_uuid}")
```

### Get Customer for Transaction

```python
customer = client.one_time_payments.get_customer_for_transaction("transaction-uuid")
print(f"{customer.name} {customer.last_name} — {customer.email}")
```

## Subscriptions

Subscriptions require an existing product — provide either `product_id` or `product_reference`.

### Create a Subscription

```python
from qbitflow import Duration

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),  # Optional
    min_periods=3,                                 # Optional: minimum billing periods
    customer_uuid="customer-uuid",
)

print(response.link)  # Send to customer
```

Like one-time payments, subscription sessions accept your own `reference`, `product_reference`,
and `customer_reference` instead of QBitFlow's internal IDs:

```python
response = client.subscriptions.create_session(
    reference="sub-1234",            # your own subscription reference
    product_reference="PLAN-PRO",    # select a product by your reference
    customer_reference="user-42",    # select a customer by your reference
    frequency=Duration(value=1, unit="months"),
)
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

```python
subscription = client.subscriptions.get("subscription-uuid")
print(subscription.subscription_status, subscription.next_billing_date)
```

### Get Subscription by Reference

Look a subscription up by the `reference` you assigned when creating the session:

```python
subscription = client.subscriptions.get_by_reference("sub-1234")
print(subscription.uuid, subscription.subscription_status)
```

> **Tracking status changes:** You no longer need to poll `get()` on a schedule
> (e.g. a cron job) to detect subscription lifecycle changes. Enable the
> **Subscription status webhook** in your QBitFlow dashboard settings and you will
> receive a notification on every status transition. See
> [Subscription Status Webhook](#subscription-status-webhook).

### Get Payment History

```python
history = client.subscriptions.get_payment_history("subscription-uuid")
for record in history:
    print(record.uuid, record.amount, record.created_at)
```

### Force Cancel

Force cancel a subscription immediately, bypassing the normal user-signed cancellation flow:

```python
response = client.subscriptions.force_cancel("subscription-uuid")
print(response.message)
```

### Execute Test Billing Cycle

**Test Mode Only**: Manually trigger a billing cycle to test webhook behaviour.

```python
result = client.subscriptions.execute_test_billing_cycle("subscription-uuid")
print("Status link:", result.status_link)
```

## Refunds

### List Active Refunds

```python
refunds = client.refunds.get_all()
for refund in refunds:
    print(f"{refund.uuid}: {refund.status.value} — {refund.reason}")
```

### List Inactive Refunds

Returns processed (approved/refused/failed) refunds with pagination:

```python
page = client.refunds.get_all_inactive(limit=10)
for refund in page.items:
    print(f"{refund.uuid}: {refund.status.value}")

if page.has_more():
    next_page = client.refunds.get_all_inactive(limit=10, cursor=page.next_cursor)
```

### Get Refund by Transaction

Public endpoint — no authentication required:

```python
refund = client.refunds.get_by_transaction("transaction-uuid")
print(refund.status.value, refund.tx_hash)
```

## Accounting Export

Export transaction data for a date range. Dates must be in `YYYY-MM-DD` format.

```python
# JSON export — returns List[AccountingEvent]
events = client.accounting.export("2025-01-01", "2025-12-31", "json")
for event in events:
    print(f"{event.payment_id} | {event.type} | ${event.gross_amount_usd}")

# CSV export — returns raw CSV string
csv_data = client.accounting.export("2025-01-01", "2025-12-31", "csv")
with open("accounting_2025.csv", "w") as f:
    f.write(csv_data)
```

`AccountingEvent` fields include: `payment_id`, `type`, `tx_time_utc`, `receipt_url`, `product_id`, `customer_uuid`, `chain`, `tx_hash`, `token_symbol`, `gross_amount_usd`, `platform_fee_usd`, `organization_fee_usd`, `net_amount_usd`, and more.

## Account Claims

QBitFlow lets organizations create users whose payments are held by the organization. When the organization is ready, they create a **claim request** — a one-time link that the user follows to set up their wallet and receive their accumulated funds.

### Get a Claim Request

Retrieve the existing claim link for a user without creating a new one:

```python
result = client.claim.get_request(user_id=42)
print(f"Claim link: {result.link}")
```

### Create a Claim Request

Create a new claim request (or return the existing one) for a user:

```python
result = client.claim.create_request(user_id=42)
print(f"Claim link: {result.link}")
# Send result.link to the user by email
```

### Get Claim Funds

List pending fund transfers owed to users who have already claimed their accounts:

```python
funds = client.claim.get_funds()
for fund in funds:
    if not fund.funded:
        print(f"Pending: ${fund.total_amount_owed} → user {fund.user_id}")
```

### Trigger Test Claim Funds

**Test Mode Only**: Manually compute ledger totals for a user without waiting for the hourly job:

```python
client.claim.trigger_test_claim_funds(user_id=42)
```

## Transaction Status

### Check Status

```python
from qbitflow.dto.transaction.status import TransactionType

status = client.transaction_status.get(
    "transaction-uuid",
    TransactionType.ONE_TIME_PAYMENT
)

print(status.status)   # TransactionStatusValue enum
print(status.tx_hash)  # Blockchain transaction hash
```

### Transaction Types

```python
class TransactionType:
    ONE_TIME_PAYMENT = 'payment'
    CREATE_SUBSCRIPTION = 'createSubscription'
    CANCEL_SUBSCRIPTION = 'cancelSubscription'
    EXECUTE_SUBSCRIPTION_PAYMENT = 'executeSubscription'
    INCREASE_ALLOWANCE = 'increaseAllowance'
```

### Status Values

```python
class TransactionStatusValue:
    CREATED = 'created'
    WAITING_CONFIRMATION = 'waitingConfirmation'
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'
```

## Customer Management

```python
from qbitflow.dto.customer import CreateCustomerDto, UpdateCustomerDto

# Create
customer = client.customers.create(CreateCustomerDto(
    name="John", last_name="Doe",
    email="john@example.com",
    phone_number="+1234567890",
    reference="CRM-12345"
))

# Get
customer = client.customers.get("customer-uuid")
customer = client.customers.get_by_email("john@example.com")
customer = client.customers.get_by_reference("CRM-12345")

# List (paginated)
page = client.customers.get_all(limit=10)

# Update
updated = client.customers.update("customer-uuid", UpdateCustomerDto(
    name="John", last_name="Doe", email="john.doe@example.com"
))

# Delete
client.customers.delete("customer-uuid")
```

## Product Management

```python
from qbitflow.dto.product import CreateProductDto, UpdateProductDto

# Create
product = client.products.create(CreateProductDto(
    name="Premium Subscription",
    description="Access to all premium features",
    price=29.99,
    reference="PROD-PREMIUM"
))

# Get
product = client.products.get(1)
product = client.products.get_by_reference("PROD-PREMIUM")

# List all
products = client.products.get_all()

# Update
updated = client.products.update(1, UpdateProductDto(
    name="Premium Plus",
    description="Enhanced premium features",
    price=39.99
))

# Delete
client.products.delete(1)
```

## User Management

```python
from qbitflow.dto.user import CreateUserDto, UpdateUserDto

# Create (admin only)
user = client.users.create(CreateUserDto(
    name="Alice",
    last_name="Smith",
    email="alice@example.com",
    role="user",              # "user" or "admin"
    organization_fee_bps=100  # optional, 1% fee
))

# Get current user (identified by API key)
me = client.users.get()

# Get by ID or list all (admin only)
user = client.users.get_by_id(42)
users = client.users.get_all()

# Update
updated = client.users.update(user.id, UpdateUserDto(
    name="Alicia",
    last_name="Smith",
    email=user.email
))

# Delete (admin only)
client.users.delete(user.id)
```

## API Key Management

```python
from qbitflow.dto.api_key import CreateApiKeyDto

# Create
resp = client.api_keys.create(CreateApiKeyDto(
    name="Production Key",
    user_id=user_id,
    test=False
))
print(f"Key (only shown once): {resp.key}")

# List API keys for the current user
keys = client.api_keys.get_all()

# List API keys for a specific user (admin only)
keys = client.api_keys.get_for_user(user_id)

# Delete
client.api_keys.delete(key_id)
```

## Webhook Handling

### Configuring Webhooks

Webhook URLs are **no longer set per session**. Instead, configure them once in your
QBitFlow dashboard settings, and they apply consistently to every transaction:

-   **Transaction webhook** — receives notifications when a payment or subscription
    session changes status (e.g. completed, failed). Payload: `SessionWebhookResponse`.
-   **Subscription status webhook** — receives notifications on every subscription
    lifecycle transition (e.g. `trial → active`, `active → past_due`,
    `active → cancelled`). Payload: `SubscriptionStatusTransitionWebhook`.

> **Migration note:** Previous versions accepted a `webhook_url` argument on
> `one_time_payments.create_session()` and `subscriptions.create_session()`. That
> parameter has been removed — set the **Transaction webhook** in the dashboard instead.
> Likewise, the **Subscription status webhook** replaces the old pattern of running a
> cron job that periodically calls `subscriptions.get()` to detect status changes.

A complete, runnable FastAPI example handling both webhook types lives in
[`test-internal/main.py`](test-internal/main.py).

#### Test Webhook Reachability

The dashboard's **Test webhook** action lets you confirm your endpoint is reachable
before going live. It sends a request with a **fake payload** that will not parse like a
real webhook — so your handler must short-circuit it. The request carries the webhook ID
in the `X-Webhook-ID` header; when that value equals `TEST_WEBHOOK_ID`, return HTTP `200`
immediately and skip normal payload processing:

```python
from qbitflow.requests.webhook import TEST_WEBHOOK_ID

# ...inside your handler, after verifying the signature:
if x_webhook_id == TEST_WEBHOOK_ID:
    return {"status": "received", "message": "Test webhook acknowledged"}
```

Perform this check **after** signature verification but **before** parsing the payload —
otherwise the fake payload will fail validation and the reachability check will report an
error. Both examples below include this guard.

### Transaction Webhook

Handles payment and subscription session status changes. Always verify the signature
before trusting the payload:

```python
from typing import Annotated
from fastapi import FastAPI, Request, Header, HTTPException
from qbitflow import QBitFlow
from qbitflow.dto.transaction.session import SessionWebhookResponse
from qbitflow.dto.transaction.status import TransactionStatusValue
from qbitflow.requests.webhook import TEST_WEBHOOK_ID

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_webhook_id: Annotated[str, Header()],
    x_webhook_signature_256: Annotated[str, Header()],
    x_webhook_timestamp: Annotated[str, Header()]
):
    body = await request.body()

    if not client.webhooks.verify(
        payload=body,
        signature=x_webhook_signature_256,
        timestamp=x_webhook_timestamp
    ):
        # Returning a >= 400 status causes QBitFlow to retry the webhook
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Reachability test from the dashboard — acknowledge and skip processing
    if x_webhook_id == TEST_WEBHOOK_ID:
        return {"status": "received", "message": "Test webhook acknowledged"}

    event = SessionWebhookResponse.model_validate_json(body)

    # event.session is automatically resolved to the correct session type:
    # OneTimePaymentSession, SubscriptionSession, or PaygSubscriptionSession
    if event.status.status == TransactionStatusValue.COMPLETED:
        print(f"Payment completed: {event.session.product_name}")
        print(f"Customer: {event.session.customer_uuid}")
        print(f"Amount: ${event.session.price}")
        # `reference` echoes back the value you set when creating the session, so you can
        # match the transaction to your own order/invoice without storing our UUID.
        print(f"Your reference: {event.session.reference}")

        from qbitflow.dto.transaction.session import SubscriptionSession
        if isinstance(event.session, SubscriptionSession):
            print(f"Frequency: {event.session.frequency}s")
    elif event.status.status == TransactionStatusValue.FAILED:
        print(f"Payment failed: {event.status.message}")

    return {"received": True}
```

### Subscription Status Webhook

Once the **Subscription status webhook** is enabled in the dashboard, QBitFlow POSTs a
`SubscriptionStatusTransitionWebhook` payload whenever a subscription changes status —
no polling required. The payload carries `subscription_uuid`, `subscription_reference`
(your own reference, if set), `previous_status`, `current_status`, and `updated_at`:

```python
from typing import Annotated
from fastapi import FastAPI, Request, Header, HTTPException
from qbitflow import QBitFlow
from qbitflow.dto.transaction.subscription import (
    SubscriptionStatusTransitionWebhook,
    SubscriptionStatus,
)
from qbitflow.requests.webhook import TEST_WEBHOOK_ID

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.post("/subscription-webhook")
async def handle_subscription_webhook(
    request: Request,
    x_webhook_id: Annotated[str, Header()],
    x_webhook_signature_256: Annotated[str, Header()],
    x_webhook_timestamp: Annotated[str, Header()]
):
    body = await request.body()

    if not client.webhooks.verify(
        payload=body,
        signature=x_webhook_signature_256,
        timestamp=x_webhook_timestamp
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Reachability test from the dashboard — acknowledge and skip processing
    if x_webhook_id == TEST_WEBHOOK_ID:
        return {"status": "received", "message": "Test webhook acknowledged"}

    event = SubscriptionStatusTransitionWebhook.model_validate_json(body)

    print(f"Subscription {event.subscription_uuid} "
          f"(ref: {event.subscription_reference}): "
          f"{event.previous_status.value} -> {event.current_status.value}")

    # React to the lifecycle transition — e.g. revoke access on cancellation
    if event.current_status == SubscriptionStatus.CANCELLED:
        print(f"Revoking access for {event.subscription_uuid}")
    elif event.current_status == SubscriptionStatus.PAST_DUE:
        print(f"Payment failed — notifying customer for {event.subscription_uuid}")

    return {"received": True}
```

`SubscriptionStatus` values: `active`, `cancelled`, `past_due`, `low_on_funds`,
`pending`, `trial`, `trial_expired`.

## Error Handling

```python
from qbitflow.exceptions import (
    QBitFlowError,
    AuthenticationError,
    NotFoundException,
    ValidationError,
    RateLimitError,
    NetworkError,
    APIError
)

try:
    payment = client.one_time_payments.get("non-existent-uuid")
except AuthenticationError:
    print("Invalid API key or authentication failed")
except NotFoundException as e:
    print(f"Payment not found: {e.message}")
except ValidationError as e:
    print(f"Validation error: {e.message}")
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after: {e.response.get('retry_after')}")
except NetworkError as e:
    print(f"Network error: {e.message}")
except APIError as e:
    print(f"API error: {e.message} (status: {e.status_code})")
except QBitFlowError as e:
    print(f"SDK error: {e.message}")
```

## API Reference

### QBitFlow

#### Constructor

```python
QBitFlow(api_key: str, timeout: Optional[int] = None, max_retries: Optional[int] = None)
```

#### Properties

| Property             | Type                          | Description                              |
|----------------------|-------------------------------|------------------------------------------|
| `customers`          | `CustomerRequests`            | Customer CRUD operations                 |
| `products`           | `ProductRequests`             | Product CRUD operations                  |
| `users`              | `UserRequests`                | User management operations               |
| `api_keys`           | `ApiKeyRequests`              | API key management                       |
| `one_time_payments`  | `PaymentRequests`             | One-time payment sessions and history    |
| `subscriptions`      | `SubscriptionRequests`        | Recurring subscription management        |
| `refunds`            | `RefundRequests`              | Refund retrieval                         |
| `accounting`         | `AccountingRequests`          | Accounting data export (JSON/CSV)        |
| `claim`              | `ClaimRequests`               | Account claim and fund transfer          |
| `transaction_status` | `TransactionStatusRequests`   | Transaction status polling               |
| `webhooks`           | `WebhookRequests`             | Webhook signature verification           |

## Testing

```bash
export QBITFLOW_API_KEY="your_test_api_key"
export QBITFLOW_BASE_URL="http://localhost:3001"  # Optional local server

pytest tests/ -v
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

