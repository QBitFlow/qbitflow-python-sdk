# Quick Start Guide

Get started with the QBitFlow Python SDK in 5 minutes!

## Installation

```bash
pip install qbitflow
```

## Basic Setup

```python
from qbitflow import QBitFlow

# Initialize with your API key
client = QBitFlow(api_key="your_api_key_here")
```

## Create Your First Payment

```python
# Create a one-time payment
response = client.one_time_payments.create_session(
    product_id=1,
    customer_uuid="customer-uuid",
    webhook_url="https://your-domain.com/webhook"
)

# Send this link to your customer
print(f"Payment link: {response.link}")
```

## Create a Subscription

```python
from qbitflow import Duration

# Create a monthly subscription
response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    customer_uuid="customer-uuid"
)

print(f"Subscription link: {response.link}")
```

## Handle Webhooks

```python
from fastapi import FastAPI
from qbitflow.dto.transaction.session import SessionWebhookResponse
from qbitflow.dto.transaction.status import TransactionStatusValue

app = FastAPI()

@app.post("/webhook")
def handle_webhook(event: SessionWebhookResponse):
    if event.status.status == TransactionStatusValue.COMPLETED:
        print(f"Payment completed: {event.session.product_name}")
        # Grant access to product/service
    
    return {"received": True}
```

## Check Status

```python
from qbitflow.dto.transaction.status import TransactionType

status = client.transaction_status.get(
    "transaction-uuid",
    TransactionType.ONE_TIME_PAYMENT
)

print(f"Status: {status.status.value}")
```

## Next Steps

- Read the [full documentation](README.md)
- Check out [examples](examples/)
- Explore the [API reference](README.md#api-reference)
- Learn about [error handling](README.md#error-handling)

## Need Help?

- 📖 [Documentation](https://docs.qbitflow.io)
- 💬 [Community Forum](https://community.qbitflow.io)
- 📧 [Email Support](mailto:support@qbitflow.io)
