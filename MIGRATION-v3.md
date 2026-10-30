# Migrating from qbitflow 2.x to 3.0

Version 3.0 of the QBitFlow Python SDK (PyPI `qbitflow`) is built for **QBitFlow API v2**. API
v2 organizes the platform around spaces (your organization's, and one per member), names every
resource by a UUID, uses REST routes, writes money as decimal strings and signs webhooks with a
new scheme. The SDK follows it: a new client, services named after the API's areas, keyword-only
arguments, typed errors and typed webhook events.

This guide maps everything the last 2.x release (2.1.0) exposed to its 3.0 replacement, with
before and after code for the common tasks. The
[README](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/README.md) documents 3.0 in
full, and the [CHANGELOG](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/CHANGELOG.md)
lists every change.

## Who should read this

Anyone whose code uses `qbitflow` 2.x, that is, anyone calling QBitFlow API v1 from Python.
The 2.x SDK talks to API v1 only and 3.0 talks to API v2 only, so plan the move as one change:
upgrade the package, update the calls listed here, replace your webhook handler, and test the
whole flow in test mode before going live.

## What changed at a glance

- **API v2**: the default base URL is `https://api.qbitflow.app/v2`. API keys in an earlier
  format are refused: create new keys in the dashboard.
- **One client, new services**: `client.checkout_sessions`, `payments`, `transactions`,
  `subscriptions`, `refunds`, `customers`, `products`, `members`, `invitations`, `wallets`,
  `accounting`, `currencies`, `failures`, `webhooks`. `one_time_payments`, `transaction_status`,
  `users`, `claim` and `api_keys` are gone.
- **Keyword-only arguments**, no more `Create…Dto` / `Update…Dto` classes, and
  `client.on_behalf_of(user_uuid)` (a whole client) instead of each service's `on_behalf_of`.
- **Ids are strings** (`product_id` becomes `product_uuid`, `user_id` becomes `user_uuid`) and
  **money is a decimal string**: `price=4.99` becomes `price_usd="4.99"`, and `Payment.amount`
  is now the token amount, `amount_usd` its USD value.
- **Pagination**: `get_all(limit, cursor)` becomes `list(...)` returning a `Page`, plus an
  `iterate(...)` that walks every page.
- **Errors**: one class per condition, each carrying the API's `code`, `details`, `request_id`
  and `field_errors`.
- **Safe retries**: reads and the six creates are retried, and every create sends an
  `Idempotency-Key`, so a retry never creates twice.
- **Webhooks**: a new `QBitFlow-Signature` header over the raw body, typed events, and a
  `WebhookRouter` with Flask, Django and FastAPI adapters. 2.x verification code does not carry
  over.
- **Members and invitations** replace users and claims.

## Upgrade steps

```bash
pip install -U "qbitflow>=3,<4"
```

- **Python 3.10 or later**, as for 2.x. Runtime dependencies are `httpx` and `pydantic` 2.5 or
  later. The SDK is synchronous.
- **API keys.** API v2 keys look like `sk_<test|live>_<uuid>_<secret>`. Keys in an earlier
  format are refused by the API (401 `AuthenticationError`): create a new key in the QBitFlow
  dashboard for each environment. Each key belongs to one space and one mode (test or live).
- **Base URL.** The default is `https://api.qbitflow.app/v2`. 3.0 no longer reads
  `QBITFLOW_BASE_URL` on import and `qbitflow.config.set_base_url` is gone: pass `base_url=` to
  the client, or build it with `QBitFlow.from_env()`, which reads `QBITFLOW_API_KEY`,
  `QBITFLOW_BASE_URL` and `QBITFLOW_ON_BEHALF_OF`.

Then:

1. **Imports.** Import everything from `qbitflow` (client, models, enums, errors,
   `RequestOptions`) and `qbitflow.webhooks`. `qbitflow.dto`, `qbitflow.exceptions`,
   `qbitflow.requests`, `qbitflow.utils` and `qbitflow.config` are gone.
2. **Client.** Pass `timeout` and `max_retries` as keywords; call `client.me()` at start-up to
   check the key and its mode; replace per-service `on_behalf_of(user_id)` with
   `client.on_behalf_of(user_uuid)`.
3. **Ids.** Store UUIDs instead of numeric product and user ids (see
   [Ids](#ids-are-uuid-strings)).
4. **Calls.** Rename every service and method using the
   [tables below](#renamed-and-removed-items), and pass arguments as keywords.
5. **Money.** Send `Decimal` or decimal strings (`"4.99"`), never floats; read `amount_usd` where
   you read `amount`.
6. **Statuses.** Update the checkout, subscription and refund status values you compare to
   (see [Enums](#enums)). Grant subscription access with `subscription.has_access()`.
7. **Pagination.** Replace `get_all(...)` loops with `list(...)` or `iterate(...)`; `has_more` is
   a field, not a method.
8. **Errors.** Catch the new classes (`NotFoundError`, `BadRequestError`,
   `PermissionDeniedError`…) and branch on `error.code`.
9. **Retries.** Remove retry loops around reads and creates (the SDK retries them safely).
10. **Webhooks.** Replace your handler with a `WebhookRouter` or `webhooks.construct_event`, and
    handle the new event types.
11. **Marketplaces.** Replace `users.*` and `claim.*` with `invitations.*` and `members.*`.
12. **Test** the whole flow in test mode with a test key, then switch to a live key.

## Breaking changes

| Area | 2.x | 3.0 |
|---|---|---|
| API | v1, `https://api.qbitflow.app/v1` | v2, `https://api.qbitflow.app/v2` |
| API keys | v1 keys | `sk_<test\|live>_<uuid>_<secret>`; older keys answer 401 |
| Client | `QBitFlow(api_key, timeout=None, max_retries=None)` | `QBitFlow(api_key, *, base_url=None, timeout=None, max_retries=None, on_behalf_of=None, http_client=None)` |
| Acting for a member | `client.<service>.on_behalf_of(user_id: int)` | `client.on_behalf_of(user_uuid: str)`, or `RequestOptions(on_behalf_of=…)` |
| Arguments | positional, or `Create…Dto` / `Update…Dto` objects | keyword-only (path ids positional), `options=` last |
| Checkouts | `one_time_payments.create_session`, `subscriptions.create_session` | `checkout_sessions.create_payment`, `create_subscription` |
| Checkout status | `transaction_status.get(uuid, transaction_type)` | `checkout_sessions.get(uuid)` |
| Ids | `Product.id: int`, `product_id`, `user_id` | `Product.uuid: str`, `product_uuid`, `user_uuid` |
| Money | floats (`price=4.99`, `Payment.amount` in USD) | decimal strings (`price_usd="4.99"`, `Payment.amount_usd`); `Payment.amount` is the token amount |
| Fee rates | basis points (`fee_bps=150`) | percent strings (`fee_percent == "1.5"`) |
| Pagination | `CursorData` with `has_more()` | `Page` with `has_more` (a field), plus `iterate(...)` |
| Deletes | return `SuccessResponse` | return `None` |
| Users and claims | `users.*`, `claim.*`, `api_keys.*` | `invitations.*`, `members.*`; keys managed in the dashboard |
| Errors | `qbitflow.exceptions`, `status_code`, message only | `qbitflow`, `status`, `code`, `details`, `request_id`, `field_errors` |
| Retries | timeouts and network errors on every method, no idempotency key | GETs and six creates, on network errors, 5xx, 429 and 409 `idempotency_key_in_use`, with an `Idempotency-Key` |
| Webhook signature | `X-Webhook-Signature-256` over canonical JSON | `QBitFlow-Signature` over the raw body |
| Webhook payloads | `SessionWebhookResponse`, `SubscriptionStatusTransitionWebhook` | 15 typed events (`PaymentCompletedEvent`, …) |

### Before and after

The 3.0 snippets assume `import os` and `import qbitflow` (or the names imported from it).

#### Create the client

```python
# 2.x
from qbitflow import QBitFlow

client = QBitFlow(api_key="sk_...", timeout=60, max_retries=5)
```

```python
# 3.0
import os

from qbitflow import QBitFlow

client = QBitFlow(os.environ["QBITFLOW_API_KEY"], timeout=60, max_retries=5)
me = client.me()  # checks the key online: AuthenticationError if unknown or revoked
if me.space is not None:
    print(me.space.organization_name, "test mode:", me.space.test)

# Or from the environment (QBITFLOW_API_KEY, QBITFLOW_BASE_URL, QBITFLOW_ON_BEHALF_OF):
client = QBitFlow.from_env(max_retries=5)
```

`QBitFlow(...)` checks the key's shape and sends nothing. Use it as a context manager, or call
`client.close()`, to close its connections.

#### Act for a member

```python
# 2.x
products = client.products.on_behalf_of(123).get_all()
payments = client.one_time_payments.on_behalf_of(123).get_all()
```

```python
# 3.0
seller = client.on_behalf_of("0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f")  # Member.user_uuid
products = seller.products.list()
payments = seller.payments.list()

# For one call only:
page = client.payments.list(
    options=qbitflow.RequestOptions(on_behalf_of="0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f")
)
```

A numeric id is refused (`ValidationError`). `None` or `""` means the organization level (2.x
used `0`).

#### Open a payment checkout and read its status

```python
# 2.x
from qbitflow.dto.transaction import TransactionStatusValue, TransactionType

link = client.one_time_payments.create_session(
    product_id=1,
    reference="order-1042",
    success_url="https://shop.example.com/success",
    cancel_url="https://shop.example.com/cancel",
)
print(link.link)
status = client.transaction_status.get(link.uuid, TransactionType.ONE_TIME_PAYMENT)
if status.status == TransactionStatusValue.COMPLETED:
    payment = client.one_time_payments.get(link.uuid)
    print(payment.amount, payment.transaction_hash)
```

```python
# 3.0
session = client.checkout_sessions.create_payment(
    product_uuid="0192f1c2-1111-7c4d-9e5f-6a7b8c9d0e1f",  # or product_reference=
    reference="order-1042",
    success_url=f"https://shop.example.com/success?uuid={qbitflow.PLACEHOLDER_UUID}",
    cancel_url="https://shop.example.com/cancel",
)
print(session.link)

status = client.checkout_sessions.get(session.uuid)  # pay@… or sub@…
if status.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
    payment = client.payments.get(session.uuid)  # the payment keeps the session's id
    print(payment.amount_usd, payment.tx_hash)
elif status.last_attempt is not None:
    print("last attempt failed, not final:", status.last_attempt.code)
```

Fulfil orders on the `payment.completed` webhook. In scripts,
`client.checkout_sessions.wait_for_completion(uuid)` polls until the session is completed or
expired.

#### Sell an inline product

```python
# 2.x
link = client.one_time_payments.create_session(
    product_name="T-shirt", description="Blue, size M", price=4.99
)
```

```python
# 3.0
session = client.checkout_sessions.create_payment(
    product_name="T-shirt",
    description="Blue, size M",  # optional now
    price_usd="4.99",  # a decimal string or a Decimal; a float is a ValidationError
    metadata={"orderId": "order-1043"},  # new: copied onto the payment and its webhooks
)
```

#### Open a subscription checkout

```python
# 2.x
from qbitflow import Duration

link = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),
)
```

```python
# 3.0
from qbitflow import Duration, DurationUnit

session = client.checkout_sessions.create_subscription(
    product_uuid="0192f1c2-1111-7c4d-9e5f-6a7b8c9d0e1f",
    frequency=Duration(value=1, unit=DurationUnit.MONTHS),
    trial_period=Duration(value=7, unit=DurationUnit.DAYS),
)
```

`frequency`, `trial_period` and `min_periods` are each optional over a subscription product's
terms, and a subscription checkout may now use an inline product (`product_name` +
`price_usd`).

#### List payments, page by page

```python
# 2.x
page = client.one_time_payments.get_all(limit=50)
while True:
    for payment in page.items:
        print(payment.uuid, payment.amount)
    if not page.has_more():
        break
    page = client.one_time_payments.get_all(limit=50, cursor=page.next_cursor)
```

```python
# 3.0
from datetime import datetime, timedelta, timezone

for payment in client.payments.iterate(
    limit=50, created_after=datetime.now(timezone.utc) - timedelta(days=30)
):
    print(payment.uuid, payment.amount_usd, "USD")

# Or one page at a time:
page = client.payments.list(limit=50)
if page.has_more:  # a field now
    page = client.payments.list(limit=50, cursor=page.next_cursor)
```

`one_time_payments.get_all_combined` becomes `client.transactions.list` / `iterate`: one feed of
payments and subscription bills.

#### Find customers by email

```python
# 2.x
customer = client.customers.get_by_email("ada@example.com")
```

```python
# 3.0: an email may match several customers
for customer in client.customers.iterate(email="ada@example.com"):
    print(customer.uuid, customer.first_name, customer.reference)
```

#### Cancel a subscription

```python
# 2.x
client.subscriptions.force_cancel(subscription_uuid)
```

```python
# 3.0
result = client.subscriptions.cancel(subscription_uuid)  # immediate by default
result = client.subscriptions.cancel(subscription_uuid, immediate=False)  # at period end
if result.pending:
    print("confirming on-chain")  # HTTP 202; subscription.statusChanged tells the end
else:
    print(result.subscription.status)
```

#### Read refunds

```python
# 2.x
pending = client.refunds.get_all()
answered = client.refunds.get_all_inactive(limit=20)
refund = client.refunds.get_by_transaction(payment_uuid)
print(refund.status.value)
```

```python
# 3.0
from qbitflow import RefundStatus

pending = client.refunds.list(status=[RefundStatus.PENDING])
for r in client.refunds.iterate(status=[RefundStatus.APPROVED, RefundStatus.REJECTED]):
    print(r.uuid, r.status, r.refund_percent, r.amount_usd)

page = client.refunds.list(tx_uuid=payment_uuid)  # zero or one refund
refund = page.items[0] if page.items else None
refund = client.refunds.get("refund@0192f1c2-4444-7c4d-9e5f-6a7b8c9d0e1f")
```

Refunds are read only in the SDK: customers request them, and you answer them or send your own
from the dashboard. A payment's `refund` field summarizes its refund, if any.

#### Receive and verify webhooks

```python
# 2.x
import os

from qbitflow import extract_webhook_headers, verify_webhook_signature
from qbitflow.dto.transaction import SessionWebhookResponse, TransactionStatusValue

headers = extract_webhook_headers(request.headers)
verify_webhook_signature(
    os.environ["QBITFLOW_WEBHOOK_SECRET"], headers["timestamp"], headers["signature"], body
)
if not headers["is_test"]:
    event = SessionWebhookResponse.model_validate_json(body)
    if event.status.status == TransactionStatusValue.COMPLETED:
        print("paid:", event.session.reference)
```

```python
# 3.0, with the router (FastAPI shown; flask_view() and django_view() work the same way)
import os

from fastapi import FastAPI

from qbitflow import Event, PaymentCompleted, SubscriptionStatusChanged, WebhookRouter

router = WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])


@router.on("payment.completed")
def fulfil(data: PaymentCompleted, event: Event) -> None:
    print("paid:", data.reference, "event", event.id)  # deduplicate on event.id


@router.on("subscription.statusChanged")
def status_changed(data: SubscriptionStatusChanged, event: Event) -> None:
    print(data.uuid, data.previous_status, "->", data.status, "access:", data.has_access())


app = FastAPI()
app.add_api_route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
```

```python
# 3.0, the lower level: verify and parse yourself
try:
    event = qbitflow.webhooks.construct_event(
        raw_body,  # the raw bytes as received, never re-serialized
        signature_header,  # the QBitFlow-Signature header
        os.environ["QBITFLOW_WEBHOOK_SECRET"],
    )
except qbitflow.WebhookSignatureError as exc:
    print("rejected:", exc.reason)  # answer 400
except qbitflow.ValidationError:
    print("not a v2 event")  # answer 400
else:
    if isinstance(event, qbitflow.PaymentCompletedEvent):
        print("paid:", event.data.reference)
    # answer 200 to every type, including the ones you ignore
```

#### Handle errors

```python
# 2.x
from qbitflow.exceptions import InvalidRequestError, NotFoundException, QBitFlowError

try:
    payment = client.one_time_payments.get_by_reference("order-1042")
except NotFoundException:
    print("not paid yet")
except InvalidRequestError as e:
    print(e.status_code, e.message)
except QBitFlowError as e:
    print(e)
```

```python
# 3.0
try:
    payment = client.payments.get_by_reference("order-1042")
except qbitflow.NotFoundError:
    print("not paid yet")
except qbitflow.ValidationError as exc:  # status None: refused before sending
    for f in exc.field_errors:
        print(f.field, f.message)
except qbitflow.PermissionDeniedError as exc:
    if exc.code == "policy_disabled":
        print("blocked by policy", exc.details.get("policy"), exc.details.get("field"))
except qbitflow.ApiError as exc:  # the base of every SDK error
    print(exc.status, exc.code, exc.request_id)
```

## Renamed and removed items

### Imports and modules

| 2.x | 3.0 |
|---|---|
| `from qbitflow import QBitFlow, Duration` | unchanged |
| `from qbitflow.dto import …`, `from qbitflow.dto.transaction import …` | `from qbitflow import …` |
| `from qbitflow.exceptions import …` | `from qbitflow import …` |
| `from qbitflow import verify_webhook_signature, compute_webhook_signature, canonical_json, extract_webhook_headers, TEST_WEBHOOK_ID` | `from qbitflow import webhooks` (see [Webhook helpers](#webhook-helpers)) |
| `qbitflow.config` (`set_base_url`, `QBITFLOW_BASE_URL` read on import) | `QBitFlow(base_url=…)` or `QBitFlow.from_env()` |
| `qbitflow.requests`, `qbitflow.utils` | removed (internal) |

### Client and configuration

| 2.x | 3.0 |
|---|---|
| `QBitFlow(api_key, timeout, max_retries)` (positional allowed) | `QBitFlow(api_key, *, timeout=…, max_retries=…)`: options are keyword-only |
| `timeout=` (int, per request) | `timeout=` seconds per attempt, the response body included (default 30) |
| `max_retries=0` (fell back to 3) | `max_retries=0` disables retries (default 3) |
| a blank key raised `ValueError` | a blank or malformed key raises `ValidationError` (never quoting the key) |
| `client.api_key` | not exposed |
| `client.<service>.on_behalf_of(user_id)` | `client.on_behalf_of(user_uuid)`, `QBitFlow(…, on_behalf_of=…)`, `RequestOptions(on_behalf_of=…)` |
| — | `client.me()`, `client.close()`, `with QBitFlow(...) as client:`, `QBitFlow.from_env()`, `http_client=` |

### Checkouts and status

| 2.x | 3.0 | Notes |
|---|---|---|
| `one_time_payments.create_session(product_id=…, price=…, …)` | `checkout_sessions.create_payment(product_uuid=…, price_usd=…, …)` | returns `CreatedCheckoutSession`; new `expires_in_minutes`, `metadata`, `fees` |
| `subscriptions.create_session(product_id=…, frequency=…, …)` | `checkout_sessions.create_subscription(product_uuid=…, frequency=…, …)` | inline products allowed; terms optional over the product's |
| `transaction_status.get(uuid, transaction_type)` | `checkout_sessions.get(uuid)` | the type is in the id (`pay@…`, `sub@…`) |
| `transaction_status.get_websocket_url(…)` | removed | use webhooks, `checkout_sessions.get` or `wait_for_completion` |
| `one_time_payments.get_session(uuid)`, `subscriptions.get_session(uuid)` | removed | `checkout_sessions.get` for the state; `checkout.expired` carries the session's data |
| — | `checkout_sessions.expire(uuid)`, `wait_for_completion(uuid)` | new |

### Payments and transactions

| 2.x | 3.0 | Notes |
|---|---|---|
| `one_time_payments.get(uuid)` | `payments.get(uuid)` | |
| `one_time_payments.get_by_reference(reference)` | `payments.get_by_reference(reference)` | `NotFoundError` when none |
| `one_time_payments.get_all(limit, cursor)` | `payments.list(…)` / `payments.iterate(…)` | filters: `customer_uuid`, `product_uuid`, `created_after`, `created_before`, `reference`, `refunded`, `include_members`, `user_uuid` |
| `one_time_payments.get_all_combined(limit, cursor)` | `transactions.list(…)` / `transactions.iterate(…)` | payments and bills; filter `type=TransactionKind.PAYMENT` or `.BILL` |
| `one_time_payments.get_customer_for_transaction(uuid)` | removed | `payment.customer` (a summary), or `customers.get(payment.customer_uuid)` |
| — | `failures.list(…)` / `failures.iterate(…)` | new: failed payment attempts |

### Subscriptions

| 2.x | 3.0 | Notes |
|---|---|---|
| `subscriptions.get(uuid)` | `subscriptions.get(uuid)` | cancelled subscriptions are returned too |
| `subscriptions.get_by_reference(reference)` | `subscriptions.get_by_reference(reference)` | `NotFoundError` when none |
| `subscriptions.get_payment_history(uuid)` | `subscriptions.list_bills(uuid)` / `iterate_bills(uuid)` | paginated `Bill`s |
| `subscriptions.force_cancel(uuid)` → `SuccessResponse` | `subscriptions.cancel(uuid, immediate=None)` → `SubscriptionCancellation` | immediate by default; `immediate=False` cancels at the end of the paid period; `pending` on HTTP 202; one cancelled already raises a `ConflictError` (`subscription_already_stopped_or_inactive`), a `NotFoundError` only another space's |
| `subscriptions.execute_test_billing_cycle(uuid)` → `StatusLinkResponse` | `subscriptions.test_bill(uuid)` → `TestBill` | test mode only; answers once the attempt settled |
| — | `subscriptions.list` / `iterate`, `update(uuid, metadata=…)`, `get_bill(bill_uuid)` | new |

### Refunds

| 2.x | 3.0 |
|---|---|
| `refunds.get_all()` | `refunds.list(status=[RefundStatus.PENDING])` / `iterate(…)` |
| `refunds.get_all_inactive(limit, cursor)` | `refunds.list(status=[RefundStatus.APPROVED, RefundStatus.REJECTED], …)` / `iterate(…)` |
| `refunds.get_by_transaction(uuid)` | `refunds.list(tx_uuid=uuid)`, or `payment.refund` / `bill.refund` |
| — | `refunds.get(refund_uuid)` (new) |

### Customers and products

| 2.x | 3.0 | Notes |
|---|---|---|
| `customers.create(CreateCustomerDto(name=…, …))` | `customers.create(first_name=…, email=…, last_name=…, phone_number=…, address=…, reference=…, metadata=…)` | `name` → `first_name`; `last_name` optional |
| `customers.get(uuid)`, `customers.get_by_reference(reference)` | same names | |
| `customers.get_by_email(email)` | `customers.list(email=…)` / `iterate(email=…)` | an email may match several customers |
| `customers.get_all(limit, cursor)` | `customers.list(…)` / `iterate(…)` | filters `email`, `reference` |
| `customers.update(uuid, UpdateCustomerDto(…))` | `customers.update(uuid, first_name=…, …)` | only what you pass changes; `""` or `None` clears `last_name`, `phone_number`, `address` |
| `customers.delete(uuid)` → `SuccessResponse` | `customers.delete(uuid)` → `None` | |
| `products.create(CreateProductDto(price=…, …))` | `products.create(name=…, price_usd=…, description=…, reference=…, subscription=…, metadata=…)` | `subscription=SubscriptionTermsParams(…)` for a subscription product |
| `products.get(product_id: int)` | `products.get(uuid: str)` | |
| `products.get_all()` | `products.list(…)` / `iterate(…)` | paginated; `include_hidden`, `subscription`, `reference` |
| `products.get_by_reference(reference)` | same name | |
| `products.update(product_id, UpdateProductDto(…))` | `products.update(uuid, name=…, description=…, price_usd=…, is_active=…, subscription=…, remove_subscription=…, metadata=…)` | |
| `products.delete(product_id)` → `SuccessResponse` | `products.delete(uuid)` → `None` | |

### Users, claims and API keys

| 2.x | 3.0 | Notes |
|---|---|---|
| `users.create(CreateUserDto(…))` | `invitations.create(email=…, hold_funds=…, organization_fee_percent=…, redirect_url=…)` | the seller exists once they accept (`member.joined` webhook) |
| `users.get_all()` | `members.list()` / `iterate()` | |
| `users.get()` (the key's user) | `client.me()` | the key's role, space and mode |
| `users.get_by_id(user_id)` | `members.get(user_uuid)` | |
| `users.get_by_email(email)` | removed | iterate `members` and compare `member.email` |
| `users.update(user_id, UpdateUserDto(organization_fee_bps=…))` | `members.update(user_uuid, organization_fee_percent="2.5")` | names and emails belong to the person |
| `users.delete(user_id)` | `members.remove(user_uuid)` → `None` | 409 `held_funds_pending` while you hold their funds |
| `claim.create_request(user_id)`, `claim.get_request(user_id)` | `invitations.create`, `invitations.list` | the invitation link replaces the claim link |
| `claim.get_funds()` | `members.list_held_funds()`, `members.get_held_funds(user_uuid)` | a member reads its own with `members.get_own_held_funds()` |
| `claim.trigger_test_claim_funds(user_id)` | removed | held funds are released from the dashboard; `members.trust(user_uuid)` pays new payments to the seller directly |
| `api_keys.get_all()`, `api_keys.get_for_user(user_id)` | removed | keys are managed in the dashboard; `client.me()` describes the current key |
| — | `invitations.revoke(uuid)`, `members.trust(user_uuid)` | new |

### Accounting and currencies

| 2.x | 3.0 | Notes |
|---|---|---|
| `accounting.export(from_date, to_date, "json")` | `accounting.export_json(from_date, to_date)` → `list[AccountingEvent]` | at most 92 days per call, both ends included |
| `accounting.export(from_date, to_date, "csv")` | `accounting.export_csv(from_date, to_date)` → `str` | |
| — | `accounting.export_json_range`, `export_csv_range` | any range, split into 92-day windows |
| `currencies.get_all_available(test=False)` | `currencies.list(test=False)` | |
| `currencies.get_all_main(test=False)` | `currencies.list(test=False, main=True)` | |
| — | `currencies.get(id)` | new |

### Models

| 2.x | 3.0 | Main changes |
|---|---|---|
| `LinkResponse` | `CreatedCheckoutSession` | `link`, `uuid`, `expires_at` (a `datetime`, always set) |
| `TransactionStatus` | `CheckoutSessionStatus` | `status` is a `CheckoutSessionStatusValue`; + `uuid`, `last_attempt`, `expires_at`; `settlement_details` removed (read the payment's `settlement`) |
| `Payment` | `Payment` | `amount` is the token amount (a string), `amount_usd` its USD value; `transaction_hash` → `tx_hash`; `name` / `description` → `product_name` / `product_description`; `product_id` → `product_uuid`; `currency_id` removed (`currency`); `metadata` (fee split) → `settlement`, and `metadata` is now your own `dict[str, str]`; `user_id` → `user_uuid`; `organization_id` removed |
| `CombinedPaymentItem` | `Transaction` | `source` → `type` (`TransactionKind`); the same renames as `Payment` |
| `SubscriptionHistory` | `Bill` | the same renames as `Payment`; + `period_start`, `period_end` |
| `Subscription` | `Subscription` | `subscription_status` → `status`; `stopped` → the `stopped` status; `frequency` (seconds) → `Duration`; `product_id` → `product_uuid`; `last_billing_date` → `last_billed_at`, `next_billing_date` → `next_billing_at`, `minimum_cancellation_date` → `cancellable_at`; `allowance` (a string) → `Allowance`; `currency_id`, `organization_id` removed; `user_id` → `user_uuid` |
| `RefundEntry` | `Refund` | `tx_id` → `tx_uuid`; `metadata` → `settlement`; `organization_id` removed; amounts as strings |
| `Customer` | `Customer` | `name` → `first_name`; `last_name` optional; `organization_id` removed; `user_id` → `user_uuid`; + `metadata` |
| `Product` | `Product` | `id: int` → `uuid: str`; `price` (float) → `price_usd` (string); `organization_id` removed; `user_id` → `user_uuid`; + `subscription`, `payment_link`, `metadata` |
| `User` | `Member` (and `Me` for the key) | `id` → `user_uuid`; `name` → `first_name`; `organization_fee_bps` → `organization_fee_percent`; `claimed_at` → `trusted_at` (see [Members](#users-and-claims-become-members-and-invitations)); + `joined_at`, `accepted_currencies` |
| `AccountingEvent` | `AccountingEvent` | `payment_id` → `tx_uuid`; `related_payment_id` → `related_tx_uuid`; `payment_reference` → `reference`; `related_payment_reference` → `related_reference`; `product_id` → `product_uuid`; `token_symbol` → `currency`; `type` → `AccountingEventType`; USD amounts and rates are decimal strings |
| `PaymentMetadata` | `Settlement` | `fee_bps` → `fee_percent`; `tx_amounts` → `split`; `tx_metadata` → `transaction` (`SettlementTransaction`) |
| `OrganizationFee(organization_id, organization, fee_bps)` | `OrganizationFee(address, fee_percent)` | |
| `ReferralFee(referral_id, referrer, fee_bps, deadline)` | `ReferralFee(address, fee_percent)` | |
| `TxMetadata`, `BlockData`, `NetworkFees`, `TxAmountsFull`, `TxAmountsUSD`, `TxAmountsMinUnits` | removed | `Settlement`, `Split`, `SettlementTransaction`, `TokenAmount` |
| `Currency` | `Currency` | + `code` (`BASE:USDC`), `chain`; `address` is `None` on a native coin; nested `main_currency` removed (`main_currency_id` stays) |
| `Duration` | `Duration` | `unit` is a `DurationUnit` (the strings `"months"`… are still accepted) |
| `CursorData` | `Page` | `items`, `has_more` (a field), `next_cursor` |
| `ClaimFund` | `MemberHeldFunds` | `user_uuid`, `total_usd`, `count`, `oldest_at` |
| `CreateClaimRequestResponse` | `CreatedInvitation` | the invitation's fields and its `link` |
| `CreatePaymentSessionDto`, `CreateSubscriptionSessionDto`, `CreateCustomerDto`, `UpdateCustomerDto`, `CreateProductDto`, `UpdateProductDto`, `CreateUserDto`, `UpdateUserDto` | removed | keyword arguments of the methods |
| `BaseSession`, `OneTimePaymentSession`, `SubscriptionSession`, `AnySession` | removed | `PaymentSessionData` / `SubscriptionSessionData` in `checkout.expired` |
| `SessionWebhookResponse`, `SubscriptionStatusTransitionWebhook` | removed | typed events (see [Webhooks](#webhooks)) |
| `PayAsYouGoSubscription`, `PaygSubscriptionSession` | removed | the API has no pay-as-you-go subscriptions |
| `StatusLinkResponse` | `TestBill` | for `subscriptions.test_bill` |
| `SuccessResponse` | `None` | deletes and `members.remove` return `None` |
| `ApiKey`, `Organization`, `ClaimRequest`, `StatusResponse`, `StatusResponseError` | removed | `client.me()` names the key, its space and its organization |

### Enums

| 2.x | 3.0 |
|---|---|
| `TransactionStatusValue` | `CheckoutSessionStatusValue`: `CREATED`, `WAITING_CONFIRMATION`, `COMPLETED`, `EXPIRED` |
| `TransactionStatusValue.PENDING`, `FAILED`, `CANCELLED` | removed: a failed attempt leaves the session `CREATED` with `last_attempt` set, and the customer may still pay |
| `TransactionType.ONE_TIME_PAYMENT` | `TransactionType.PAYMENT` |
| `TransactionType.CREATE_SUBSCRIPTION` | unchanged |
| every other `TransactionType` member, `TransactionShortType` | removed |
| `SubscriptionStatus.ACTIVE`, `TRIAL`, `CANCELLED` | unchanged |
| `SubscriptionStatus.PAST_DUE` (`past_due`), `TRIAL_EXPIRED` (`trial_expired`) | same members, values `pastDue`, `trialExpired` |
| `SubscriptionStatus.LOW_ON_FUNDS` | `subscription.action_required == ActionRequired.TOP_UP_ALLOWANCE` |
| `SubscriptionStatus.PENDING` | `subscription.action_required == ActionRequired.RAISE_MAXIMUM` |
| `subscription.stopped is True` | `SubscriptionStatus.STOPPED` |
| — | `SubscriptionStatus.PAUSED` (paused by the customer), `ActionRequired.CONFIRM_TRIAL` |
| `RefundStatus.PENDING`, `APPROVED` | unchanged |
| `RefundStatus.REFUSED` | `RefundStatus.REJECTED` |
| `RefundStatus.FAILED` | removed: a refund is pending, approved or rejected |
| `UserRole` (`ADMIN`, `USER`, `OWNER`) | `Role` (`ADMIN`, `USER`) |
| `CombinedPaymentItem.source` `"subscription_history"` | `TransactionKind.BILL` |
| `AccountingEvent.type` (a `str`) | `AccountingEventType` (`subscription_history` → `BILL`) |

Enum values follow the API's lowerCamelCase. Enums are `StrEnum`s and keep a value the SDK does
not know yet as the raw string: compare with `==`, and give every `match` a default case.

### Exceptions

| 2.x (`qbitflow.exceptions`) | 3.0 (`qbitflow`) |
|---|---|
| `QBitFlowError` | `QBitFlowError` (the base of every SDK error) |
| `APIError` | `ApiError` (the base of every class below) |
| `ValidationError` (client-side checks) | `ValidationError`: client-side checks (`status` None) and 400 `validation_failed` |
| `InvalidRequestError` (every other 4xx) | `BadRequestError` (400), `PermissionDeniedError` (403), `ConflictError` (409), `GoneError` (410), `IdempotencyError` (422) |
| `AuthenticationError` | `AuthenticationError` (401) |
| `NotFoundException` | `NotFoundError` (404, and `get_by_reference` with no match) |
| `RateLimitError` (`response["retry_after"]`) | `RateLimitError` (`retry_after`, `limit`, `period_seconds`) |
| `NetworkError` | `NetworkError` (no response; the cause is chained) |
| `APIError` for a 5xx | `ServerError` (5xx, an unexpected 3xx, an unusable 2xx) |
| — | `WebhookSignatureError` (`reason`) |
| `error.status_code`, `error.response` | `error.status`, `error.details`, `error.raw_body`; + `code`, `request_id`, `field_errors` |

### Webhook helpers

| 2.x | 3.0 |
|---|---|
| `verify_webhook_signature(secret, timestamp, signature, payload)` | `webhooks.verify(raw_body, signature_header, secret)`: argument order changed, raises `WebhookSignatureError` |
| `client.webhooks.verify(payload, signature, timestamp)` (asks the API, returns `bool`) | `client.webhooks.verify_remote(endpoint_uuid, raw_body, signature_header)`: returns `None` or raises `WebhookSignatureError` |
| `compute_webhook_signature(secret, timestamp, payload)` | `webhooks.sign(raw_body, secret, timestamp=None)`, for tests |
| `canonical_json(payload)` | removed: the signature covers the raw body |
| `extract_webhook_headers(headers)` | removed: read the `QBitFlow-Signature` header (`webhooks.SIGNATURE_HEADER`) |
| `HEADER_SIGNATURE`, `HEADER_TIMESTAMP`, `HEADER_WEBHOOK_ID`, `client.webhooks.get_*_header()` | `webhooks.SIGNATURE_HEADER`, `EVENT_ID_HEADER`, `EVENT_TYPE_HEADER` (the timestamp is inside the signature header) |
| `TEST_WEBHOOK_ID` | the `webhook.test` event (`EventType.WEBHOOK_TEST`) |
| `max_timestamp_age_seconds=`, `now_seconds=`, `DEFAULT_MAX_TIMESTAMP_AGE_SECONDS` | `tolerance=`, `now=`, `webhooks.DEFAULT_TOLERANCE` (300 seconds) |
| `SessionWebhookResponse.model_validate_json(body)` | `webhooks.construct_event(...)` or `webhooks.parse_event(raw_body)` |

**Watch out:** `client.webhooks.verify` still exists in 3.0, but it is now the local check and
takes your endpoint's secret. If you used 2.x's `client.webhooks.verify` to have the API check
signatures without holding the secret, call `client.webhooks.verify_remote` instead.

## New capabilities

- **Checkout sessions**: `expires_in_minutes`, `metadata`, `{{UUID}}` and
  `{{TRANSACTION_TYPE}}` redirect placeholders (`qbitflow.PLACEHOLDER_UUID`,
  `PLACEHOLDER_TRANSACTION_TYPE`), `checkout_sessions.expire`, and `wait_for_completion` for
  scripts.
- **Checkout fees**: `fees=CheckoutFees(items=[FeeItem(...)], processing_fee=True)` adds your
  own lines (tax, shipping) and, optionally, QBitFlow's processing fee, paid by the customer.
- **Your own metadata** (`dict[str, str]`) on products, customers, checkouts and subscriptions,
  copied from a checkout onto its payment or subscription and into their webhooks.
- **Subscription products** (`SubscriptionTermsParams`) and inline subscription checkouts.
- **Subscriptions**: `list` / `iterate` with filters, `update` (metadata), bills
  (`list_bills`, `iterate_bills`, `get_bill`), `current_period_end`, `action_required`,
  `dunning`, `cancellation_reason`, `management_page_link`, and `subscription.has_access()`.
- **Transactions and failures**: one feed of payments and bills (`transactions`), and the failed
  payment attempts (`failures`).
- **Refunds**: `refunds.list` / `iterate` with filters, `refunds.get`.
- **Marketplaces**: invitations, members, commissions in percent, held funds
  (`members.list_held_funds`, `get_held_funds`, `get_own_held_funds`) and `members.trust`.
- **Wallets**: `wallets.list(with_balances=…)`, `wallets.list_for_member`,
  `wallets.list_accepted_currencies`.
- **Accounting exports over any range** (`export_json_range`, `export_csv_range`).
- **Webhook endpoints and the event log**: `client.webhooks.endpoints` (`list`, `iterate`,
  `create`, `get`, `update`, `delete`) and `client.webhooks.events` (`list`, `iterate`, `get`
  with each event's deliveries).
- **Typed webhook events** and the **`WebhookRouter`**, with `flask_view()`, `django_view()`,
  `fastapi_endpoint()` and `handle_asgi()` (optional extras `qbitflow[flask]`, `[django]`,
  `[fastapi]`, `[starlette]`).
- **Iterators** on every paginated list.
- **Safe retries with idempotency keys**, and `RequestOptions(idempotency_key=…)` for keys of your
  own.
- **Helpers**: `client.me()`, `QBitFlow.from_env()`, `qbitflow.format_amount` /
  `parse_amount`, `qbitflow.is_retryable`, `RequestOptions(request_id=…)`.

## Behaviour changes

### Ids are UUID strings

- Products are named by `uuid` (was the numeric `id`); `product_id` becomes `product_uuid`
  everywhere (payments, bills, subscriptions, checkouts, the accounting export).
- People are named by their user UUID (`Member.user_uuid`); `user_id` becomes `user_uuid`, and
  is `None` on the organization's own records.
- `organization_id` is gone from every model; `client.me().space.organization_uuid` names your
  organization.
- Transactions keep prefixed ids (`pay@…`, `sub@…`, `sub-hist@…`, `refund@…`); pass them back
  verbatim. `tx_id` becomes `tx_uuid` and `transaction_hash` becomes `tx_hash`.
- Currencies keep numeric ids.

If you stored numeric product or user ids, map them once: walk your products with
`client.products.iterate(include_hidden=True)` and match them on `reference`, and walk your
members with `client.members.iterate()` and match them on `email`. Then store the UUIDs.

### Money is a decimal string

USD amounts (`price_usd`, `amount_usd`, `total_usd`), token amounts (`amount == "10"` for 10
USDC, next to `amount_min_units == "10000000"`) and fee rates in percent (`fee_bps=150` becomes
`fee_percent == "1.5"`) are decimal strings, in requests and responses. Money inputs take a
`str` or a `decimal.Decimal`; a `float` or an `int` is a `ValidationError`. Compute with
`Decimal`, never `float`:

```python
from decimal import Decimal

product = client.products.create(name="T-shirt", price_usd=Decimal("4.99"))
total = Decimal(product.price_usd) * 3
```

In test mode a checkout's total, fees included, is capped at 5 USD.

### Users and claims become members and invitations

API v2 creates no accounts for you: a seller sells once they accepted an invitation.

1. `client.invitations.create(email=…, hold_funds=…, organization_fee_percent=…)` returns a
   `CreatedInvitation` with its `link` (also emailed, unless `send_email=False`).
2. Wait for the `member.joined` webhook and store its `user_uuid` (match `invitation_uuid` to
   your invitation).
3. Sell for them with `client.on_behalf_of(user_uuid)`.

`hold_funds=True` (the 2.x claim model) sends the seller's payments to your wallet until you
trust them: `members.get_held_funds` shows what you owe, `members.trust` makes their new
payments go to them directly, and the release of what is held is signed in the dashboard. While
you hold a seller's funds they sell one-time payments only. To see where your existing sellers
stand, list them with `client.members.list()`: a member whose `trusted_at` is `None` is one whose
funds you hold.

### Errors

- Every error derives from `QBitFlowError` and `ApiError`, and carries `status` (`None` without
  a response), `code`, `message`, `details` (a dict, never `None`), `request_id`,
  `field_errors` and `raw_body`.
- **Branch on `code`**, never on `message`: `unique_violation` (`details["field"]`),
  `merchant_not_ready` (`details["reason"]`), `tx_already_sent`, `held_funds_pending`,
  `payment_not_due`, `test_mode_only`, `policy_disabled`…
- **Field errors**: a `ValidationError` lists each failing input in `field_errors`
  (`FieldError(field, message)`), named by its wire name and dotted when nested
  (`frequency.unit`). 2.x exposed only a message.
- **Client-side checks** run before every request and raise `ValidationError` with `status`
  `None`; nothing is sent. They cover lengths, emails, URLs, money, percents, metadata, UUIDs,
  cursors and references.
- **References** (`reference`, `product_reference`, `customer_reference`, the `reference=`
  filters and `get_by_reference`) are 1 to 100 characters among `A-Z a-z 0-9 . _ : @ -`, and
  never exactly `.` or `..`.
- **403**: `forbidden` (a role, or another space's resource) carries no details.
  `policy_disabled` means a member's own key did something its organization's policy does not
  allow members; `details["policy"]` names the policy, and `details["field"]` the request field
  it governs. For example, a member's key may send `success_url` / `cancel_url` on checkouts
  while the organization's `members.checkoutRedirects` policy allows it; otherwise the call is a
  403 `policy_disabled` with `details["policy"] == "members.checkoutRedirects"` and
  `details["field"]` naming the field. The organization's key acting for the member
  (`on_behalf_of`) may always send them.
- **`get_by_reference`** with no match is a `NotFoundError` (404, code `not_found`), like an
  unknown UUID.
- Log `request_id` and quote it to support. `RequestOptions(request_id=…)` sets your own.

### Retries and idempotency

| | 2.x | 3.0 |
|---|---|---|
| Retried methods | every method, writes included | GETs and the six creates: `checkout_sessions.create_payment`, `create_subscription`, `products.create`, `customers.create`, `webhooks.endpoints.create`, `invitations.create` |
| Retried on | timeouts and network errors | network errors and timeouts, 5xx, 429, 409 `idempotency_key_in_use` |
| Idempotency | none: a retried create could create twice | each create sends an `Idempotency-Key`, the same on every retry |
| Default | 3 (`max_retries=0` also meant 3) | 3; `max_retries=0` disables retries |

Redirects are never followed: an unexpected 3xx is a `ServerError`, so your key is never sent to
another origin. Back-off is 1 s, 2 s, 4 s…; a 429 waits for its `Retry-After` when longer, and
a wait above 60 seconds is not made (the `RateLimitError` is raised). Every other write
(updates, deletes, `expire`, `cancel`, `test_bill`, `trust`, `remove`, `revoke`) is attempted
once: retry it yourself only after reading the resource's state. To retry a create across
processes, pass a stable key: `options=RequestOptions(idempotency_key=f"checkout-{order_id}")`.
Reusing a key with other parameters is an `IdempotencyError` (422 `idempotency_key_reused`).

### Pagination

`list(...)` returns a `Page[T]`: `items`, `has_more` and `next_cursor`. While `page.has_more`,
pass `page.next_cursor` back as `cursor=`, verbatim. Each paginated list has an `iterate…` twin
that fetches one page at a time as you consume it and keeps your filters. The page size defaults
to 20 and is capped at 100. The short bounded lists return a plain `list`: `currencies.list`,
`wallets.list`, `wallets.list_for_member`, `wallets.list_accepted_currencies`,
`members.list_held_funds` and `accounting.export_json`.

### Webhooks

| | 2.x | 3.0 |
|---|---|---|
| Headers | `X-Webhook-Signature-256: sha256=<hex>`, `X-Webhook-Timestamp`, `X-Webhook-Id` | `QBitFlow-Signature: t=<unix>,v1=<hex>`, `QBitFlow-Event-Id`, `QBitFlow-Event-Type` |
| Signed content | timestamp + canonical JSON of the body | `t` + `.` + the raw body, exactly as received |
| Secret rotation | one secret | for 24 hours after a rotation the header carries two `v1=` signatures; either secret verifies |
| Body | `SessionWebhookResponse` or a subscription status transition | an event (`id`, `type`, `created_at`, `test`, `user_uuid`, `data`) |
| Dashboard test | `X-Webhook-Id: test-webhook-id` | a `webhook.test` event |

- **Read the raw body and never re-serialize it** before verifying (Flask
  `request.get_data()`, Django `request.body`, FastAPI `await request.body()`). The router's
  adapters do this for you.
- **Event types replace the two 2.x payloads.** A completed transaction webhook is now
  `payment.completed` or `subscription.created`; the subscription status webhook is
  `subscription.statusChanged` (`data.uuid`, `data.reference`, `data.previous_status`,
  `data.status`). New types include `subscription.billed`, `subscription.billingFailed`,
  `subscription.upcomingBill`, `subscription.actionRequiredChanged`, `checkout.expired`,
  `refund.requested`, `refund.approved`, `refund.rejected`, `member.joined`, `member.removed`,
  `heldFunds.released` and `webhook.test`. A failed checkout attempt sends no event: the session
  stays open until paid or `checkout.expired`.
- Each type parses into its own class (`PaymentCompletedEvent`, …) with a typed `data`; narrow
  with `isinstance`, or register handlers on a `WebhookRouter`. A type newer than the SDK is an
  `UnknownEvent`.
- **Deliveries are at least once**: deduplicate on `event.id`, and answer 2xx quickly, including
  to the types you ignore (the router does).
- Timestamps more than 5 minutes from your clock are refused (`tolerance=` changes it).
- **Endpoints.** Every endpoint receives v2 events. List yours with
  `client.webhooks.endpoints.list()`, and create one with `client.webhooks.endpoints.create(…)`,
  whose answer carries the `whsec_…` secret once. An endpoint's secret is otherwise shown and
  rotated in the dashboard. An organization endpoint also receives its members' events unless
  created with `include_members=False`; `event.user_uuid` names the member.

### Test and live mode

The API key decides the mode: a test key works on test data, a live key on live data. No call
takes a `test=` flag except `currencies.list(test=…)`, which lists the test networks' currencies.
Check the mode at start-up with `client.me().space.test`. Test mode caps checkout totals at 5 USD,
and `subscriptions.test_bill` runs a subscription's next bill on demand (test mode only).

### Synchronous client

3.0 is synchronous, like 2.x; there is no async client. A client is safe to share between
threads: create one per API key and reuse it. In async code, call it from a worker thread. The
router's `handle_asgi` runs your handlers in Starlette's thread pool.

### API keys

2.x's `api_keys` service is gone: keys are created, listed and revoked in the dashboard, and
`client.me()` describes the key in use (its role, space and mode). Member policies (such as
`members.checkoutRedirects`) are also changed in the dashboard only.

## Final checklist

- [ ] `pip install -U "qbitflow>=3,<4"`; Python 3.10 or later.
- [ ] New API v2 keys created in the dashboard for test and live; old keys removed from your
      configuration.
- [ ] Base URL left at the default, or set to a `/v2` URL with `base_url=` or
      `QBITFLOW_BASE_URL` through `QBitFlow.from_env()`.
- [ ] Imports come from `qbitflow` and `qbitflow.webhooks` only.
- [ ] Client options passed as keywords; `client.me()` checked at start-up.
- [ ] `on_behalf_of(user_id)` replaced with `client.on_behalf_of(user_uuid)`.
- [ ] Numeric product and user ids mapped to UUIDs.
- [ ] Every service and method renamed; arguments passed as keywords; DTO classes removed.
- [ ] Money sent as `Decimal` or decimal strings; `amount` reads changed to `amount_usd` where
      you meant USD.
- [ ] Status comparisons updated (checkout, subscription, refund); access granted with
      `has_access()`.
- [ ] Pagination loops use `list` / `iterate`, and `has_more` as a field.
- [ ] Error handling catches the 3.0 classes and branches on `code`; `request_id` logged.
- [ ] Your own retry loops around reads and creates removed.
- [ ] Webhook handler rewritten for `QBitFlow-Signature` and typed events, deduplicating on
      `event.id`; 2.x `client.webhooks.verify` calls replaced with `verify_remote` or the local
      `webhooks.verify`.
- [ ] Marketplace code moved from `users` / `claim` to `invitations` / `members`.
- [ ] The whole flow tested in test mode, then switched to a live key.
