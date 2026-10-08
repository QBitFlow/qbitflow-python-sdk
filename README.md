# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MPL-2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

The official Python SDK for [QBitFlow](https://qbitflow.app), non-custodial crypto payments: hosted
checkouts, one-time payments, subscriptions, refunds, marketplaces with commissions and held
funds, accounting exports and signed webhooks. Customers pay from their own wallets, on Ethereum,
Base and Solana, straight to yours.

- **API v2**, every integrator route: 13 services, 60 routes, one `QBitFlow` client.
- **Typed**: pydantic v2 models with snake_case attributes, enums, `py.typed`; keyword-only
  arguments checked before anything is sent.
- **Typed errors**, one class per condition, each carrying the API's code, request id and field
  errors.
- **Safe retries**: reads and creates are retried on network errors, 5xx and 429, and every create
  sends an `Idempotency-Key`, so a retry never charges or creates twice.
- **Iterators**: `for payment in client.payments.iterate(): ...` walks every page lazily.
- **Webhooks** verified locally (`QBitFlow-Signature`, secret rotation included) and parsed into
  typed events; a `WebhookRouter` dispatches them to your handlers and plugs into Flask, Django
  or FastAPI in one line.
- **Integration helpers**: `wait_for_completion` for scripts, `subscription.has_access()`, exact
  `format_amount`/`parse_amount`, accounting exports over any range, `QBitFlow.from_env()`.

> Coming from 2.x? Read [MIGRATION-v3.md](MIGRATION-v3.md): 3.0.0 targets API v2 and changes the
> client and most names.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Integration recipes](#integration-recipes)
- [Authentication and acting for a member](#authentication-and-acting-for-a-member)
- [Checkout sessions](#checkout-sessions)
- [Products and customers](#products-and-customers)
- [Payments and failures](#payments-and-failures)
- [Subscriptions](#subscriptions)
- [Refunds](#refunds)
- [Marketplaces](#marketplaces)
- [Wallets](#wallets)
- [Accounting export](#accounting-export)
- [Webhooks](#webhooks)
- [Currencies](#currencies)
- [Pagination and iterators](#pagination-and-iterators)
- [Errors](#errors)
- [Retries and idempotency](#retries-and-idempotency)
- [Configuration](#configuration)
- [Migrating from 2.x](#migrating-from-2x)
- [Examples](#examples) · [Testing](#testing) · [License](#license) · [Support](#support) · [Security](#security)

## Installation

```bash
pip install qbitflow
```

**Requires Python 3.10 or later.** Dependencies: `httpx` and `pydantic` (v2).

## Quick start

The snippets in this README assume `import os` and `import qbitflow`, and, past this first one,
a client named `client`. Variables such as `session_uuid`, `payment_uuid`, `subscription_uuid`
and `member_uuid` hold ids you got earlier.

<!-- docs:snippet client-init -->
```python
# One client per API key, shared by the whole program. ValidationError: not an sk_… key.
client = qbitflow.QBitFlow(os.environ["QBITFLOW_API_KEY"])

# The recommended start-up check: what is this key, and which mode is it in?
me = client.me()  # AuthenticationError for an unknown or revoked key
if me.space is not None:
    print(f"{me.space.organization_name}, role {me.role}, test mode {me.space.test}")
```
<!-- /docs:snippet -->

`client.close()`, or `with qbitflow.QBitFlow(...) as client:`, closes the connections the SDK
opened. A hosted checkout for a one-time payment of 4.99 USD:

<!-- docs:snippet checkout-create-payment -->
```python
session = client.checkout_sessions.create_payment(
    product_name="T-shirt",
    description="Blue, size M",
    price=4.99,  # USD
    reference="order-1042",  # your order id: unique per space
    # QBitFlow replaces the placeholder with the session's id when it redirects the customer.
    success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
    cancel_url="https://shop.example.com/orders/cancel",
)
# Redirect the customer to the hosted checkout page.
print("Send the customer to", session.link)
```
<!-- /docs:snippet -->

Then fulfil the order when the [`payment.completed` webhook](#webhooks) arrives for
`session.uuid`, never on the customer's redirect to your success page: the
[integration recipes](#integration-recipes) show the endpoint in Flask, Django and FastAPI.

### Conventions

- **Services are attributes** of the client (`client.checkout_sessions`, `client.webhooks.endpoints`);
  methods are snake_case. Every argument except a path id is **keyword-only**, and every method
  takes `options=RequestOptions(...)` last ([configuration](#configuration)).
- **Ids are strings.** Resources are named by UUIDs; transactions by prefixed ids (`pay@…` a
  payment, `sub@…` a subscription, `sub-hist@…` a bill, `refund@…` a refund) that you pass back
  verbatim. Only currencies keep numeric ids (`int`).
- **Models** are pydantic v2 models with snake_case attributes; `model.to_dict()` gives the wire
  form (camelCase). A field the API always sends is never `None`: an absent value decodes to its
  zero value (`""`, `0`, `False`, `[]`, `ZERO_TIME`). Optional fields are `Optional[...]`, `None`
  when absent. The wire's `from` is `from_`.
- **Amounts:** USD amounts are `float` (`amount`, `amount_usd`); exact amounts in a token's
  smallest unit, and a few USD prices, are decimal strings (`amount_min_units`, `price_usd`,
  `allowance`), never rounded. Fee rates are percents: `fee_percent == 1.5` is 1.5 %.
- **Enums** are `StrEnum`s (`SubscriptionStatus.ACTIVE`). A value this SDK does not know yet is
  kept as the raw `str`: compare with `==`, and give every `match` a default case.
- **Times** are timezone-aware `datetime`s, with the offset the API sent.

## Integration recipes

The usual integration in a few lines each: create a checkout, receive the webhook, grant access.

### A webhook endpoint in your framework

Register a handler per event type on a `WebhookRouter`, then mount it. The router verifies the
`QBitFlow-Signature` header over the raw body, parses the event, runs your handlers and answers
the status QBitFlow expects. No framework is a dependency of the SDK: each adapter imports its
framework only when you call it.

**FastAPI** (with `from fastapi import FastAPI`; `mark_order_paid` stands for your own,
idempotent, code):

<!-- docs:snippet webhook-handler -->
```python
router = qbitflow.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])


@router.on("payment.completed")  # the handler gets the typed data, then the event
def fulfil(data: qbitflow.PaymentCompleted, event: qbitflow.Event) -> None:
    # At least once: the same event can arrive twice, deduplicate on event.id.
    mark_order_paid(data.reference or data.uuid, event_id=event.id)


app = FastAPI()
# Verifies the QBitFlow-Signature header on the raw body, parses the event, runs the handler
# for its type, and answers the status QBitFlow expects (200, 400 or 500).
app.add_api_route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
```
<!-- /docs:snippet -->

Register more handlers the same way, e.g. `@router.on("subscription.statusChanged")` to update
access with `data.has_access()`. Starlette takes the same endpoint:
`Route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])`.

**Flask:**

```python
from flask import Flask

app = Flask(__name__)
app.add_url_rule("/webhooks/qbitflow", view_func=router.flask_view())  # POST only
```

**Django** (the view is CSRF-exempt: QBitFlow signs its deliveries instead):

```python
from django.urls import path

urlpatterns = [path("webhooks/qbitflow", router.django_view())]
```

Inside a route of your own, `return await router.handle_asgi(request)` answers the Starlette
`Request`. Anything else (a queue consumer, another framework): `router.handle(raw_body,
signature_header)` returns a `WebhookResult` whose `status` you answer. The details are in
[Webhooks](#webhooks).

### Checkout, success page, and waiting in a script

Create the checkout as in the [quick start](#quick-start). On the success page, show the state
with [`get_status`](#status), but fulfil on the webhook (anyone can open the URL). In a script, a
test or a back-office job, poll until the checkout is completed or expired:

<!-- docs:snippet wait-for-completion -->
```python
# For scripts and back-office jobs: fulfil orders on the payment.completed webhook.
final = client.checkout_sessions.wait_for_completion(session_uuid, timeout=600, interval=3)
if final.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
    print("paid")
else:
    print("not paid:", final.status)  # expired, or still open when the timeout elapsed
```
<!-- /docs:snippet -->

### Access control

<!-- docs:snippet has-access -->
```python
subscription = client.subscriptions.get(subscription_uuid)
# current_period_end is set and now is before it, whatever the status.
if subscription.has_access():
    print("grant access")
else:
    print("no access")
```
<!-- /docs:snippet -->

### Displaying amounts

<!-- docs:snippet amounts-display -->
```python
# Amounts in a token's smallest unit are decimal strings: never convert them through a float.
shown = qbitflow.format_amount("4990000", 6)  # "4.99" (6 decimals, like USDC)
min_units = qbitflow.parse_amount("4.99", 6)  # "4990000"
print(shown, min_units)
```
<!-- /docs:snippet -->

`parse_amount` raises a `ValidationError` beyond the given decimal places. A model's currency
knows its decimals: `payment.currency.format_amount(payment.amount_min_units)`.

### A yearly accounting export

<!-- docs:snippet accounting-export -->
```python
# Any range: the SDK splits it into the API's 95-day windows and joins the parts.
events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
for event in events:
    print(event.type, event.payment_uuid, event.token_symbol, event.net_amount)

csv_text = client.accounting.export_csv_range("2026-01-01", "2026-12-31")
with open("qbitflow-2026.csv", "w", encoding="utf-8") as file:
    file.write(csv_text)
```
<!-- /docs:snippet -->

### A client from the environment

<!-- docs:snippet config-from-env -->
```python
# QBITFLOW_API_KEY (required), QBITFLOW_BASE_URL and QBITFLOW_ON_BEHALF_OF when set.
client = qbitflow.QBitFlow.from_env(timeout=10)  # explicit options override the environment
```
<!-- /docs:snippet -->

## Authentication and acting for a member

Every request sends your API key in `X-API-Key`. Keys are created in the QBitFlow dashboard; each
belongs to one **space** (your organization's, or one of its members') and one **mode** (test or
live). `QBitFlow(...)` only checks the key's shape (non-blank, starting with `sk_`) and sends
nothing: call `me()` to check it online ([quick start](#quick-start)). `me.role` is `admin` for
an organization key, and `me.space.test` tells test mode from live (a job that must only run in
test mode checks it first).

Keep the key in a secret store or an environment variable, never in code. Keys issued before API v2
(`sk_<digits>_…`) still work; rotate them in the dashboard to the `sk_<uuid>_…` format.

### `On-Behalf-Of`: acting in a member's space

A marketplace's **organization key** can act in any of its members' spaces: create their products
and checkouts, read their payments. Name the member by their **user UUID** (`Member.user_uuid`,
also in the `member.joined` webhook). A non-member, an owner or admin of the team, or a member of
the other mode answers 404.

<!-- docs:snippet client-on-behalf-of -->
```python
# Every request of this client sends On-Behalf-Of: it acts in the member's space.
seller = client.on_behalf_of(member_uuid)  # shares the connections and settings of client
products = seller.products.list()
print(len(products), "products in the seller's space")
```
<!-- /docs:snippet -->

For one request only, the request option wins over the client's; `""` forces the organization's
own space for one request of the seller's client:

```python
from qbitflow import RequestOptions

page = client.payments.list(options=RequestOptions(on_behalf_of=member_uuid))
own = seller.products.list(options=RequestOptions(on_behalf_of=""))
```

`QBitFlow(key, on_behalf_of=uuid)` sets it for every request of a client. A value that is not a
UUID (or the nil UUID) is a `ValidationError`, raised at once, and nothing is sent.

## Checkout sessions

A checkout session is a hosted payment page. Create it, send your customer to its `link`, and act
on the webhook. The session's id (`pay@…` or `sub@…`) is also the id of the payment or the
subscription it creates once the customer's transaction is confirmed.

Name the product with **exactly one** of `product_uuid`, `product_reference`, or an inline
product (`product_name` + `price`, `description` optional, as in the
[quick start](#quick-start)). A product of your catalog:

<!-- docs:snippet checkout-create-payment-product -->
```python
session = client.checkout_sessions.create_payment(
    product_reference="tshirt-blue-m",  # or product_uuid=
    reference="order-1042",
    success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
    cancel_url="https://shop.example.com/orders/cancel",
)
print("Send the customer to", session.link)
```
<!-- /docs:snippet -->

`reference` is your order id, unique per space. `customer_reference` is kept on the payment, and
`expires_in_minutes` (10 to 1440) sets the checkout's lifetime.

A subscription checkout takes the same arguments plus its terms (`frequency`, `trial_period`,
and `min_periods`, the periods the customer commits to), each optional over a subscription
product's:

<!-- docs:snippet checkout-create-subscription -->
```python
session = client.checkout_sessions.create_subscription(
    product_name="T-shirt",
    description="Blue, size M",
    price=4.99,  # USD per period
    frequency=qbitflow.Duration(value=1, unit=qbitflow.DurationUnit.MONTHS),
    trial_period=qbitflow.Duration(value=7, unit=qbitflow.DurationUnit.DAYS),
    reference="order-1043",
    success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
    cancel_url="https://shop.example.com/orders/cancel",
)
print("Send the customer to", session.link)  # sub@…: the subscription's id once signed
```
<!-- /docs:snippet -->

- **Redirect placeholders.** In `success_url` and `cancel_url`, QBitFlow replaces `{{UUID}}` with
  the session's id and `{{TRANSACTION_TYPE}}` with `payment` or `createSubscription`
  (`qbitflow.PLACEHOLDER_UUID`, `qbitflow.PLACEHOLDER_TRANSACTION_TYPE`; the SDK sends them as
  is, never URL-encoded). In live mode
  both URLs must be `https`. A redirect proves nothing (anyone can open the URL): fulfil on the
  webhook, or on `get_status`.
- **Errors to expect:** `409 merchant_not_ready` (`details["reason"]`) when the space's wallets
  accept no currency; `409 unique_violation` when another payment or open session holds the
  `reference`; `400 validation_failed` above 5 USD in test mode (`details["max"]`); `404` for an
  unknown product or customer.

### Status

<!-- docs:snippet checkout-status -->
```python
status = client.checkout_sessions.get_status(session_uuid)  # pay@… or sub@…
if status.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
    print("paid, tx", status.tx_hash)  # the payment (or subscription) has the session's id
elif status.status == qbitflow.CheckoutSessionStatusValue.EXPIRED:
    print("expired unpaid")
elif status.last_attempt is not None:
    print("last attempt failed:", status.last_attempt.code)  # not final: they can try again
else:
    print("waiting:", status.status)  # created or waitingConfirmation
```
<!-- /docs:snippet -->

| `status` | Meaning | Final |
|---|---|---|
| `created` | Waiting for the customer. With `last_attempt` set, their last attempt failed (`last_attempt.code` says why) | no |
| `waitingConfirmation` | A transaction was sent; waiting for the network. It may last: the transaction can still land | no |
| `completed` | Confirmed and recorded: the `Payment` or `Subscription` exists, with the session's id | yes |
| `expired` | Expired unpaid (`checkout.expired` was sent). Read some days later, an expired session is a 404 | yes |

**Never cancel an order on `last_attempt`:** a failed attempt is not final, and the customer can
pay from the same checkout until it expires. Release what the order holds on `checkout.expired`.

For scripts, tests and back-office jobs, `wait_for_completion` polls `get_status` until the
session is `completed` or `expired` and returns that status; when `timeout` (seconds, default
600; 0 or less means the default) elapses first it returns the last status seen, so check
`.status`. `interval` (default 3)
is at least 1 second; errors of `get_status` (a 404 included) are raised. Webhooks remain the way
to fulfil orders. The code is in the
[recipes](#checkout-success-page-and-waiting-in-a-script).

### Expire

End a session early (an order cancelled on your side). It answers its status, and
`checkout.expired` follows. Once the customer paid or is paying it is a `409 tx_already_sent`.

<!-- docs:snippet checkout-expire -->
```python
# An order cancelled on your side: the checkout can no longer be paid.
expired = client.checkout_sessions.expire(session_uuid)
print(expired.status)  # expired; checkout.expired follows
```
<!-- /docs:snippet -->

## Products and customers

Products are optional (a checkout can name an inline product) and give you a reusable catalog
with payment links. The `reference` is generated when left out.

<!-- docs:snippet products-create -->
```python
product = client.products.create(
    name="T-shirt",
    description="Blue, size M",
    price=4.99,  # USD
    reference="tshirt-blue-m",  # your own id: unique per space
)
print(product.uuid, product.payment_link)
```
<!-- /docs:snippet -->

<!-- docs:snippet products-list -->
```python
for product in client.products.list():
    print(product.reference, product.name, product.price)
```
<!-- /docs:snippet -->

A subscription product carries its terms. `update` changes only the arguments given; a new price
applies to new checkouts and subscribers only, and an inactive product is hidden from `list()`
unless `include_hidden=True` (`subscription=True` lists the subscription products only):

```python
from qbitflow import Duration, DurationUnit, SubscriptionTermsParams

terms = SubscriptionTermsParams(frequency=Duration(value=1, unit=DurationUnit.MONTHS))
plan = client.products.create(name="Pro plan", price=4.99, subscription=terms)
plan = client.products.update(plan.uuid, price=5.99, is_active=False)
```

`products.get`, `get_by_reference` and `delete` complete the set. Deleting a product does not stop
its subscriptions: cancel them with `subscriptions.cancel` if the product is gone for good.

```python
customer = client.customers.create(
    name="Ada", last_name="Lovelace", email="ada@example.com", reference="crm-42"
)

# "" (or None) clears phone_number or address; leaving the argument out keeps it.
customer = client.customers.update(customer.uuid, phone_number="")

by_email = client.customers.get_by_email("ada@example.com")
print(customer.uuid == by_email.uuid)
```

`customers.get`, `get_by_reference`, `list` / `iterate` (by `email` or `verified`) and `delete`
complete the set. A checkout given `customer_uuid` or `customer_reference` asks the customer
nothing (`customer_reference` is kept on the payment, and links your customer with that reference
if there is one); without either, the checkout asks what your `checkout.customerDetails` setting
says (the full details by default).

The clearable update fields (`customers.update`'s `phone_number` and `address`,
`products.update`'s and `webhooks.endpoints.update`'s `description`) default to `NOT_GIVEN`:
left out, the value is unchanged; `""` or `None` clears it.

## Payments and failures

A `Payment` exists once its transaction is confirmed, with its checkout session's `pay@…` id.

<!-- docs:snippet payments-list -->
```python
page = client.payments.list(refunded=False, limit=20)  # newest first
for payment in page.items:
    print(payment.uuid, payment.reference, f"{payment.amount:.2f} USD")
if page.has_more:
    print("next page: cursor =", page.next_cursor)  # pass it back as cursor=
```
<!-- /docs:snippet -->

<!-- docs:snippet payments-get -->
```python
payment = client.payments.get(payment_uuid)  # pay@…, the id of its checkout session
print(payment.reference, f"{payment.amount:.2f} USD", payment.tx_hash)

by_reference = client.payments.get_by_reference("order-1042")  # your order id
print(by_reference.uuid)
```
<!-- /docs:snippet -->

A payment also carries its `explorer_url`, whether it is `refundable`, and its split:
`metadata.tx_amounts.usd.merchant` is what the merchant received.

- **Filters**: `customer_uuid`, `product_uuid`, `created_after` / `created_before` (aware
  `datetime`s, both excluded), `refunded`, and, with an organization key acting for itself,
  `include_members` (every member's rows, each naming its `user_uuid`) or `user_uuid` (one
  member's). The last two exclude each other.
- **Reading a member's row** from the organization's space:
  `client.payments.get(id, include_members=True)`, or `on_behalf_of` the member.
- **The combined feed** of one-time payments and subscription bills, newest first:
  `payments.list_combined` / `iterate_combined`, with the same filters plus `source`
  (`CombinedPaymentSource.PAYMENT`, `CombinedPaymentSource.SUBSCRIPTION_HISTORY`) and
  `subscription_uuid`.
- **Failures** are the failed attempts to pay a checkout or a bill. They never moved money and
  are not final: the customer can try again.

```python
from qbitflow import FailureCategory

for f in client.failures.iterate(category=FailureCategory.INSUFFICIENT_BALANCE):
    print(f"{f.tx_uuid} attempt {f.attempt}: {f.code} ({f.attempted_usd:.2f} USD)")
```

## Subscriptions

A subscription exists once its customer signed its checkout: paid the first period, or started
the free trial. It keeps the checkout's `sub@…` id for life.

| `status` | Meaning |
|---|---|
| `trial` | In its free trial |
| `trialExpired` | The trial ended without the customer confirming it (`action_required` `confirmTrial`); cancelled 7 days later unless confirmed |
| `active` | Billed on its due dates |
| `pastDue` | A bill failed; retried for up to 7 days (`dunning` on reads), then cancelled |
| `paused` | Paused by its customer: not billed until resumed |
| `stopped` | Cancelled during its period: never billed again, `cancelled` at `next_billing_date` |
| `cancelled` | Over (`cancellation_reason` says why). Final |

**Access rule: grant access while `now < current_period_end`, whatever the status.** A `stopped`
or `paused` subscription has paid for its period; a `pastDue` one's period has ended.
`subscription.has_access()` applies it ([access control](#access-control));
`has_access(at)` checks at a given `datetime` (a naive one is UTC). Every subscription model has
it, the subscription webhooks' data included.

<!-- docs:snippet subscriptions-get -->
```python
subscription = client.subscriptions.get(subscription_uuid)  # sub@…, cancelled ones too
print(subscription.status, "paid until", subscription.current_period_end)
```
<!-- /docs:snippet -->

`action_required` says what the customer must do (`topUpAllowance`, `raiseMaximum`,
`confirmTrial`; `None`: nothing): point them to the `management_page_link` the subscription
webhooks carry.

```python
from qbitflow import SubscriptionStatus

page = client.subscriptions.list(status=SubscriptionStatus.PAST_DUE)
for sub in page.items:
    if sub.dunning is not None:
        print(sub.uuid, sub.dunning.remaining_attempts, "attempts left")

# Every bill, newest first: the iterator fetches the pages lazily.
for bill in client.subscriptions.iterate_bills(subscription_uuid):
    if bill.period_end is not None:
        print(f"{bill.uuid}: {bill.amount:.2f} USD, paid until {bill.period_end.date()}")
```

- `subscriptions.get_by_reference` reads one by your checkout's `reference`; `get_bill` one bill
  (`sub-hist@…`).
- `subscriptions.get_public_history` returns the 10 latest bills as the customer's page shows
  them. It is a public route: the fields only the merchant sees (`metadata`, `customer_uuid`,
  `customer_reference`, `user_uuid`, `paid_min_units`, `refund`, …) are empty there. Use
  `list_bills` for full bills.
- Before its checkout completes, `subscriptions.get` is a 404: read the checkout session instead.

### Cancel

`cancel` cancels without the customer signing. By default it is immediate (`cancelled`, reason
`merchant`); `immediate=False` stops it now and cancels it at the end of the period paid for.

<!-- docs:snippet subscriptions-cancel -->
```python
result = client.subscriptions.cancel(subscription_uuid, immediate=False)  # at period end
if result.pending:
    # HTTP 202: still confirming on-chain; subscription.statusChanged tells the end.
    print("cancellation confirming")
else:
    print("now", result.subscription.status)  # stopped, cancelled at the period's end
```
<!-- /docs:snippet -->

`cancel` answers 200 when done and 202 (`pending`) while confirming on-chain: the status is not
updated yet, but the cancellation goes on regardless. It is never retried automatically. A
subscription already stopped is a `ConflictError` (409
`subscription_already_stopped_or_inactive`); a cancelled one a `NotFoundError`.

### Test billing

In test mode a subscription is billed only when you ask, with live's statuses and webhooks:

<!-- docs:snippet subscriptions-test-bill -->
```python
# Test mode only: run the next billing now instead of on its due date.
state = client.subscriptions.execute_test_billing(subscription_uuid)
print(state.stage, state.outcome, state.failure_code)
```
<!-- /docs:snippet -->

Before `next_billing_date` it is a `ConflictError` (409 `payment_not_due`); for a live
subscription a `BadRequestError`.

Walk the timeline once in test mode: a 5-minute frequency, pay from a test wallet, trigger the
bill, then empty the wallet and trigger it again to see `subscription.billingFailed` and
`pastDue`.

## Refunds

Refunds waiting for an answer. From the organization's space the members' are included by
default: `include_members=False` leaves them out.

<!-- docs:snippet refunds-list -->
```python
for refund in client.refunds.list():  # the active refunds
    print(refund.uuid, refund.tx_uuid, refund.status, refund.reason)
```
<!-- /docs:snippet -->

The answered refunds (approved or rejected) come page by page:

```python
for r in client.refunds.iterate_inactive():
    print(r.uuid, r.status, r.explorer_url)
```

`refunds.initiate` starts a refund of a payment (`pay@…`) or a bill (`sub-hist@…`) of the space.
**It creates a pending refund: no money moves until you sign the transfer in the dashboard**, from
the wallet that was paid. `refund.completed` tells you when it is sent.

<!-- docs:snippet refunds-create -->
```python
refund = client.refunds.initiate(
    tx_uuid=payment_uuid,  # pay@… (or a bill's sub-hist@…)
    refund_percent=50,  # of what the customer paid; None refunds everything
    reason="Damaged item",
)
# A pending refund: no money moves until you sign the transfer in the dashboard.
print(refund.uuid, refund.status)
```
<!-- /docs:snippet -->

`refund_percent` is a share of everything the customer paid, network fee included;
`merchant_message` adds a note for the customer. There is one refund per transaction: another is
a `ConflictError` (409 `refund_already_exists`, the existing one in `details["refundUuid"]`).

A refund is `pending`, `approved` or `rejected`; `initiated_by` is `customer` (a request you
answer in the dashboard) or `merchant`. A held seller's payment already released to them can no
longer be refunded (`409 held_funds_released`).

## Marketplaces

A marketplace is an organization whose sellers are its **members**. You invite them, sell for
them with your organization key and `On-Behalf-Of`, take a commission on their payments, and may
hold their funds until you trust them. QBitFlow stays non-custodial: money goes from the
customer's wallet to the seller's (and your commission to yours) in one transaction.

**1. Invite the seller.** The SDK always invites members (`role: user`); the team is invited from
the dashboard.

<!-- docs:snippet members-invite -->
```python
created = client.invitations.create(
    email="seller@example.com",
    trust_layer=True,  # hold their funds until you trust them
    organization_fee_percent=10,  # your commission on their payments
    redirect_url="https://shop.example.com/sellers/welcome",
)
# The seller exists once they accept: wait for the member.joined webhook.
print("invitation", created.invitation.uuid, "link:", created.link)  # also emailed
```
<!-- /docs:snippet -->

The commission is 0 to 50 %, with at most 2 decimals. Inviting a member is a `ConflictError`
(409 `already_joined`), and more than 50 invitations an hour a `RateLimitError`.

**2. Wait for `member.joined`.** The seller exists once they accepted: store the event's
`user_uuid` and match `invitation_uuid` to your invitation. Never trust the redirect's
`?invitationUuid=` (anyone can open it).

```python
from qbitflow import MemberJoinedEvent

if isinstance(event, MemberJoinedEvent):
    print("invitation", event.data.invitation_uuid, "accepted by", event.data.user_uuid)
```

**3. Sell for them.** The seller adds their receiving wallet in their QBitFlow dashboard (only
they can, not needed while you hold their funds). Until then their checkouts answer
`409 merchant_not_ready`:

```python
if not client.wallets.list_supported_currencies(user_uuid=member_uuid):
    raise SystemExit("the seller cannot be paid yet")
```

Then act in their space with `seller = client.on_behalf_of(member_uuid)`
([On-Behalf-Of](#on-behalf-of-acting-in-a-members-space)): `seller.checkout_sessions` and
`seller.products` create the seller's checkouts and products. Your policies may not let members
do this: a `PermissionDeniedError` (403 `policy_disabled`).

**4. Hear of every sale.** An organization webhook endpoint receives every seller's events by
default; the event's `user_uuid` names the seller. Use it as `on_behalf_of` for follow-up reads.

**5. Commission and held funds.** Each payment records your fee in `metadata.organization_fee`
and `metadata.tx_amounts`. While you hold a seller's funds (`trust_layer` True,
`Member.trusted_at` None), their payments go to your wallet and the net is owed to them:

<!-- docs:snippet members-held-funds -->
```python
for summary in client.members.list_held_funds():  # every member you hold funds for
    print(summary.user_uuid, f"{summary.total_amount:.2f} USD over {summary.count} lines")

held = client.members.get_held_funds(member_uuid)  # one member, line by line
print(f"owed to the seller: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")
```
<!-- /docs:snippet -->

The seller reads their side with their own key, or through a client acting for them
(`seller.members.get_own_held_funds()`):

<!-- docs:snippet members-own-held-funds -->
```python
# With a member's key, or a client acting on behalf of the member.
held = client.members.get_own_held_funds()
print(f"held for me: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")
```
<!-- /docs:snippet -->

Trust them once you no longer want to hold their funds:

<!-- docs:snippet members-trust -->
```python
# Their new payments go to their own wallets from now on. What is held stays held until you
# release it from the dashboard (heldFunds.released tells you).
member = client.members.trust(member_uuid)
print("trusted since", member.trusted_at)
```
<!-- /docs:snippet -->

Change the commission:

<!-- docs:snippet members-update -->
```python
# The fee on their new payments (a checkout already created keeps its fee).
member = client.members.update(member_uuid, organization_fee_percent=10)
print(member.organization_fee_percent)
```
<!-- /docs:snippet -->

**6. Manage members and invitations.**

<!-- docs:snippet members-list -->
```python
page = client.members.list()
for member in page.items:
    print(member.user_uuid, member.email, f"fee {member.organization_fee_percent}%")
```
<!-- /docs:snippet -->

<!-- docs:snippet members-get -->
```python
member = client.members.get(member_uuid)  # their user uuid
print(member.name, member.last_name, "trusted:", member.trusted_at is not None)
```
<!-- /docs:snippet -->

`members.iterate` walks every page. `wallets.list_for_member` reads a member's wallets:

<!-- docs:snippet members-wallets -->
```python
for wallet in client.wallets.list_for_member(member_uuid):
    print(wallet.currency.symbol, wallet.public_key)
```
<!-- /docs:snippet -->

`members.remove` ends a seller's membership in the key's mode. It is a `409 held_funds_pending`
while you hold their live funds: release them first.

<!-- docs:snippet members-remove -->
```python
try:
    client.members.remove(member_uuid)  # their keys stop working, their checkouts close
    print("removed")
except qbitflow.ConflictError as exc:
    if exc.code != "held_funds_pending":
        raise
    print("release their held funds first")  # from the dashboard
```
<!-- /docs:snippet -->

`invitations.list` / `iterate` (by `status`) and `invitations.revoke` manage the invitations:

<!-- docs:snippet invitations-list -->
```python
page = client.invitations.list(status=qbitflow.InvitationStatus.PENDING)
for invitation in page.items:
    print(invitation.uuid, invitation.email, "expires", invitation.expires_at)
```
<!-- /docs:snippet -->

<!-- docs:snippet invitations-revoke -->
```python
invitation = client.invitations.revoke(invitation_uuid)  # a pending one only
print(invitation.status)  # revoked
```
<!-- /docs:snippet -->

- `members.list_held_funds` lists every member you owe, longest held first.
- Today a seller whose account already belongs to another organization cannot accept (no
  `member.joined` comes), and test-mode sellers are real accounts that accept from a real inbox.

## Wallets

Wallets are added and removed in the dashboard, by their owner only. The SDK reads them.

```python
for w in client.wallets.list(with_balances=True):
    print(w.currency.symbol, w.public_key)
    for tw in w.token_wallets:
        if tw.balance is not None:
            print(f"  {tw.token.symbol}: {tw.balance.balance} ({tw.balance.balance_usd:.2f} USD)")
```

`wallets.list_for_member(user_uuid)` reads a member's wallets (organization key), and
`wallets.list_supported_currencies` the currencies a space's checkouts accept: none means its
checkouts answer `409 merchant_not_ready`.

## Accounting export

Every payment, bill, refund and fee between two dates (`YYYY-MM-DD` strings or `datetime.date`s,
both included), as models (`export_json`) or as CSV text (`export_csv`); the
[recipe](#a-yearly-accounting-export) exports a year with their `_range` twins. Each row has its
`type`, `payment_uuid`, `tx_time_utc`, `token_symbol`, `gross_amount`, `net_amount` and more.

The SDK checks the dates and `from <= to` before sending. **The API allows at most 95 days per
export** and answers 400 beyond. `export_json_range` and `export_csv_range` take any range: they
request consecutive windows of at most 95 days (`[from, from + 95 days]`, the next starting the
day after), in order, and join them (one list; one CSV with the header line once). A range of
95 days or less is one request. Rows are typed `payment`,
`subscriptionHistory`, `refund`, `organizationFee` or `referralFee`; amounts in a token's
smallest unit are decimal strings, and the empty fields of a row are `None`.

## Webhooks

QBitFlow posts an **event** to your endpoints when something happens: a payment confirmed, a
subscription billed, a member joined.

### 1. Create an endpoint and store its secret

<!-- docs:snippet webhook-endpoint-create -->
```python
created = client.webhooks.endpoints.create(
    url="https://shop.example.com/webhooks/qbitflow",
    events=[  # None: every type, including the ones added later
        qbitflow.EventType.PAYMENT_COMPLETED,
        qbitflow.EventType.CHECKOUT_EXPIRED,
        qbitflow.EventType.SUBSCRIPTION_STATUS_CHANGED,
    ],
    description="Order fulfilment",
)
# The whsec_… secret is returned only this once: put it in your secret store now
# (QBITFLOW_WEBHOOK_SECRET for your webhook handler).
print(created.uuid, created.secret)
```
<!-- /docs:snippet -->

Up to 10 endpoints per space and mode; live endpoints need `https` and a public host. An
organization endpoint also receives its members' events unless created with
`include_members=False`. `endpoints.list`, `get`, `update` (`enabled=False` pauses it, `True`
enables it again) and `delete` manage them. An endpoint's secret is shown and rotated in the
dashboard only.

### 2. Handle the deliveries with a router

A `WebhookRouter` holds the endpoint's secret and your handlers; it needs no client (a receiver
may not hold an API key). `client.webhooks.router(secret)` builds the same thing.

```python
import os

from qbitflow import (
    CheckoutExpired,
    Event,
    EventType,
    PaymentCompleted,
    SubscriptionStatusChanged,
    UnknownEvent,
    webhooks,
)

router = webhooks.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])  # tolerance=300


@router.on("payment.completed")  # the handler gets the typed data, then the event
def fulfil(data: PaymentCompleted, event: Event) -> None:
    print(f"fulfil order {data.reference!r} ({data.uuid}): {data.amount:.2f} USD")


@router.on(EventType.CHECKOUT_EXPIRED)  # an EventType works too
def release(data: CheckoutExpired, event: Event) -> None:
    print("release order", data.reference)


@router.on("subscription.statusChanged")
def status_changed(data: SubscriptionStatusChanged, event: Event) -> None:
    print(f"{data.uuid}: {data.previous_status} -> {data.status}, access: {data.has_access()}")


@router.on_unknown  # a type added after this SDK
def unknown(event: UnknownEvent) -> None:
    print("new event type", event.type)


@router.on_any  # every event, after its type's handlers
def audit(event: Event) -> None:
    print("received", event.id, event.type)


# router.add("member.joined", fn) registers without a decorator. Then, per delivery:
result = router.handle(raw_body, signature_header)  # the raw bytes, never re-serialized
print(result.status, result.event, result.error)
```

Mount it with `router.flask_view()`, `router.django_view()`, `router.fastapi_endpoint()` or
`await router.handle_asgi(request)` ([recipes](#a-webhook-endpoint-in-your-framework)).

| The delivery | `result.status` | Handlers |
|---|---|---|
| Verified, handled | 200 | its type's handlers (registration order), then every `on_any` |
| A type without a handler, or one this SDK does not know | 200 (QBitFlow must not retry it) | `on_unknown` for an unknown type, then `on_any` |
| Bad, missing or stale signature (`WebhookSignatureError`) | 400 | none |
| Not JSON, not a v2 event, or not matching its type (`ValidationError`) | 400 | none |
| A handler raised | 500 (QBitFlow retries) | the remaining ones are skipped; `result.error` is the exception |

The adapters answer `{"received":true}` on a 200 and `{"error":"<reason>"}` otherwise, never
the secret nor the exception: `invalid signature`, `invalid event` or `cannot read the body`
(400), `internal error` (500). They accept `POST` only (405 `method not allowed`, with
`Allow: POST`), read at most 1 MiB (413 `body too large`, early when `Content-Length` says so)
and find `QBitFlow-Signature` whatever its case. The Flask view reads the raw body
itself: don't read `request.data` before it. Handlers are synchronous; `handle_asgi` runs them
in Starlette's thread pool. `WebhookRouter(secret, on_error=fn)` calls `fn(event, exception)`
for every 400 and 500 (`event` is `None` when the body could not be parsed), to log it.

- **At least once.** The same event can arrive more than once: **deduplicate on `event.id`**
  (also in the `QBitFlow-Event-Id` header) and make the handlers idempotent: a 500 makes QBitFlow
  deliver the event again, to every handler.
- **Answer 2xx fast**, within 30 seconds, **including to the types you ignore** (the router does):
  anything else is retried (for 3 days in live mode), and an endpoint failing for 3 days is
  disabled. For slow work, store the event in a handler and process it in the background.
- **Secret rotation** needs nothing on your side: for 24 hours after a rotation the header
  carries two `v1=` signatures, the new secret's and the previous one's, and either secret
  verifies. Switch your secret within the day.
- **Timestamps** more than 5 minutes from your clock are refused (replays): `tolerance=`
  (seconds) changes it.
- **Members' events** carry the member in `event.user_uuid`: read their resources with
  `client.on_behalf_of(event.user_uuid)`.
- **No fixed source IPs**: verify the signature, never allow-list addresses.
- **v2 only.** An endpoint migrated from API v1 receives v1 bodies, which the router answers 400
  (a `ValidationError` on `version`): move it to v2 in the dashboard, or with
  `client.webhooks.endpoints.update(uuid, payload_version=WebhookPayloadVersion.V2)`.

### Testing your endpoint

`webhooks.sign(raw_body, secret, timestamp=None)` builds the header exactly as QBitFlow does:

```python
import json

from qbitflow import webhooks

test_router = webhooks.WebhookRouter("whsec_test_secret")  # register your handlers on it
event = {
    "id": "evt_1",
    "version": "v2",
    "type": "webhook.test",
    "createdAt": "2026-10-01T12:00:00Z",
    "test": True,
    "data": {"endpointUuid": "", "message": "hello"},
}
body = json.dumps(event).encode()
result = test_router.handle(body, webhooks.sign(body, "whsec_test_secret"))
assert result.status == 200
```

### The lower level: verify and parse

`webhooks.verify(raw_body, header, secret)` checks a signature (raising `WebhookSignatureError`
with a `reason`: `missingHeader`, `malformedHeader`, `timestampOutsideTolerance`,
`noMatchingSignature`), `webhooks.construct_event` verifies then parses, and
`webhooks.parse_event` only parses (a `ValidationError` for a body that is not a v2 event, such
as an endpoint still on v1). In a handler that returns the HTTP status to answer:

<!-- docs:snippet webhook-verify -->
```python
try:
    event = qbitflow.webhooks.construct_event(
        raw_body,  # the raw bytes as received, never re-serialized
        signature_header,  # the QBitFlow-Signature header
        os.environ["QBITFLOW_WEBHOOK_SECRET"],
    )
except qbitflow.WebhookSignatureError as exc:
    print("rejected:", exc.reason)  # e.g. noMatchingSignature, timestampOutsideTolerance
    return 400
except qbitflow.ValidationError:
    return 400  # not a v2 event
if isinstance(event, qbitflow.PaymentCompletedEvent):  # narrow the union by class
    print("fulfil order", event.data.reference)
return 200  # acknowledge every other type too, or QBitFlow retries it
```
<!-- /docs:snippet -->

`now=` sets their clock in tests (a `datetime`, unix seconds, or a callable). Not holding the
secret? `client.webhooks.verify_remote(endpoint_uuid, raw_body, header)` has the API check it,
then `client.webhooks.parse_event(raw_body)` parses the body. `client.webhooks.verify`,
`construct_event` and `parse_event` are the same functions on the client.

### Event types

| `event.type` | Event class | `event.data` |
|---|---|---|
| `payment.completed` | `PaymentCompletedEvent` | `PaymentCompleted`: the `Payment` + `management_page_link` |
| `subscription.created` | `SubscriptionCreatedEvent` | `SubscriptionCreated`: the `Subscription` (`active` or `trial`) + `management_page_link` |
| `subscription.billed` | `SubscriptionBilledEvent` | `SubscriptionBilled`: the `Bill` (paid until `period_end`) + `subscription_reference`, `subscription_status` |
| `subscription.statusChanged` | `SubscriptionStatusChangedEvent` | `SubscriptionStatusChanged`: the `Subscription` + `previous_status` |
| `subscription.actionRequiredChanged` | `SubscriptionActionRequiredChangedEvent` | the `Subscription` + `previous_action_required` |
| `subscription.billingFailed` | `SubscriptionBillingFailedEvent` | the `Subscription` + `reason`, `bill_uuid`, `amount_usd` (a **string**), `attempt`, `remaining_attempts`, `next_attempt_at` |
| `subscription.upcomingBill` | `SubscriptionUpcomingBillEvent` | the `Subscription` + `billing_date`, `amount_usd` (a **float**), `trial_ending`, `balance_sufficient`, `allowance_sufficient` |
| `refund.requested` / `.completed` / `.denied` | `RefundRequestedEvent` / `RefundCompletedEvent` / `RefundDeniedEvent` | the `Refund` |
| `member.joined` | `MemberJoinedEvent` | `MemberJoined`: the `Member` + `invitation_uuid` |
| `member.removed` | `MemberRemovedEvent` | the `Member` |
| `heldFunds.released` | `HeldFundsReleasedEvent` | `HeldFundsReleased`: the transfer paid to the member + the `ledgers` it settled |
| `checkout.expired` | `CheckoutExpiredEvent` | `PaymentSessionData`, or `SubscriptionSessionData` when `tx_type` is `createSubscription` |
| `webhook.test` | `WebhookTestEvent` | `WebhookTest`: `endpoint_uuid`, `message` (the dashboard's test) |
| any other | `UnknownEvent` | the raw JSON value |

`qbitflow.Event` is the union of these classes (a pydantic discriminated union on `type`); every
one derives from `BaseEvent` (`id`, `type`, `version`, `created_at`, `test`, `user_uuid`). Webhook
data never carries what only API reads return (`customer`, `refund`/`refundable`, `dunning`,
`approval`, `product_name`): those fields are `None` on events.

### The event log

Every event of the space, newest first (`events.iterate` walks every page):

<!-- docs:snippet events-list -->
```python
page = client.webhooks.events.list(type=qbitflow.EventType.PAYMENT_COMPLETED, limit=20)
for event in page.items:  # newest first
    print(event.id, event.type, event.created_at)
```
<!-- /docs:snippet -->

`events.get(event_id)` adds each one's deliveries:

```python
detail = client.webhooks.events.get(event_id)
for d in detail.deliveries:
    print(detail.event.id, d.url, d.delivered, len(d.attempts))
```

## Currencies

<!-- docs:snippet currencies-list -->
```python
# A public route limited to 60 requests a minute: cache the list at start-up.
currencies = client.currencies.list_available()
for currency in currencies:
    print(currency.id, currency.symbol, currency.name, currency.decimals)
```
<!-- /docs:snippet -->

`list_available` lists every currency checkouts can take, `list_main` the chains' native coins,
and `get` one by id, to resolve the `currency_id`, `available_currency_ids` and
`accepted_currency_ids` fields. These routes are public and **limited to 60 requests a minute per
IP: cache the list** at start-up instead of reading it per request. Payments, bills and
subscriptions already carry their `currency`.

## Pagination and iterators

Paginated lists return a `Page[T]`: `items`, and `next_cursor` (`None` on the last page, else
the value to pass back as `cursor=`, verbatim); `page.has_more` says whether another page follows.

<!-- docs:snippet customers-list -->
```python
page = client.customers.list(limit=20)
for customer in page.items:
    print(customer.uuid, customer.email, customer.reference)
if page.has_more:
    print("next page: cursor =", page.next_cursor)  # pass it back as cursor=
```
<!-- /docs:snippet -->

Each paginated list has an `iterate…` twin returning an iterator: it fetches one page at a time,
only as you consume it, keeps your filters and page size, and stops when you `break`. An error is
raised from the loop.

<!-- docs:snippet pagination-iterate -->
```python
# Fetches one page at a time, only as the loop consumes it; break stops the fetching.
for payment in client.payments.iterate(limit=50):
    print(payment.uuid, f"{payment.amount:.2f} USD")
```
<!-- /docs:snippet -->

| Method | Iterator | Page size: default / max |
|---|---|---|
| `customers.list` | `iterate` | 10 / 100 |
| `payments.list`, `payments.list_combined` | `iterate`, `iterate_combined` | 10 / 50 |
| `failures.list` | `iterate` | 10 / 50 |
| `subscriptions.list`, `subscriptions.list_bills` | `iterate`, `iterate_bills` | 20 / 100 |
| `refunds.list_inactive` | `iterate_inactive` | 10 / 50 |
| `members.list`, `invitations.list` | `iterate` | 20 / 100 |
| `webhooks.events.list` (cursor `evt_…`) | `iterate` | 20 / 100 |

The other lists are short and return a plain `list`: `products.list`, `refunds.list`,
`wallets.*`, `currencies.*`, `webhooks.endpoints.list` (at most 10), `members.list_held_funds`
and `subscriptions.get_public_history` (the 10 latest bills).

## Errors

Every error the SDK raises derives from `QBitFlowError` and from `ApiError`, which carries the
fields every error has; catch the most specific class you can act on:

| Class | When | Codes and fields worth knowing |
|---|---|---|
| `ValidationError` | 400 `validation_failed`, or input the SDK refused **before sending** (`status` None) | `field_errors`: each failing input by its wire name, dotted when nested (`frequency.unit`) |
| `BadRequestError` | any other 400 | `bad_request`, `foreign_key_violation` (`details["field"]`) |
| `AuthenticationError` | 401 | a missing, unknown, expired or revoked key (a removed member's keys too) |
| `PermissionDeniedError` | 403 | `forbidden`, `policy_disabled` (`details["policy"]`), `plan_required` |
| `NotFoundError` | 404 | unknown, deleted, or outside the request's space |
| `ConflictError` | 409 | `unique_violation` (`details["field"]`), `tx_already_sent`, `merchant_not_ready` (`details["reason"]`), `refund_already_exists` (`details["refundUuid"]`), `held_funds_released`, `held_funds_pending`, `already_joined`, `payment_not_due`, `idempotency_key_in_use`, `conflict` |
| `GoneError` | 410 | `merchant_closed`: a removed member's or a closed organization's space |
| `IdempotencyError` | 422 `idempotency_key_reused` | an `Idempotency-Key` reused for another request: a bug, never retried |
| `RateLimitError` | 429 | `retry_after` (seconds), `limit`, `period_seconds` |
| `ServerError` | 5xx (503 `network_unavailable`, 504 `timeout`), an unexpected 3xx (redirects are never followed), a 2xx whose body is not the expected JSON | |
| `NetworkError` | no response: DNS, connection, TLS, timeout | the cause is chained (`__cause__`) |
| `WebhookSignatureError` | a webhook signature refused, locally or by `verify_remote` | `reason` |
| `ApiError` | any other HTTP error (e.g. 413 `request_too_large`), and the base of all the above | |

Every error carries `status` (`None` without a response), `code` (branch on it, never on
`message`), `message`, `details` (never `None`), `request_id`, `field_errors` and `raw_body`.
`str(error)` reads `"<message> (status <status>, code <code>, request <requestId>)"`, followed by
`"; <field>: <message>"` for each field error.

<!-- docs:snippet errors-handling -->
```python
try:
    payment = client.payments.get_by_reference("order-1042")
    print("paid:", payment.uuid)
except qbitflow.ValidationError as exc:  # status None: refused before sending
    for field_error in exc.field_errors:
        print(f"{field_error.field}: {field_error.message}")
except qbitflow.NotFoundError:
    print("no payment for order-1042 yet")
except qbitflow.ApiError as exc:  # the base of every error the SDK raises
    print(f"QBitFlow error {exc.status} {exc.code} (request {exc.request_id})")
    if qbitflow.is_retryable(exc):  # network, 5xx, 429: worth trying again later
        print("transient: try again later")
```
<!-- /docs:snippet -->

Catch the classes you act on before `ApiError`: a `ConflictError` with code `unique_violation`
names the taken field in `details["field"]`, a `RateLimitError` says when to retry in
`retry_after`. Quote the request id to support.

**Client-side validation** runs before every request: names and texts (lengths in characters, no
markup characters), references (`A-Z a-z 0-9 . _ : @ -`, 1 to 100), emails, phone numbers,
absolute `http(s)` URLs, prices above 0, percents (at most 2 decimals), durations (a frequency
between 1 unit and 1 year), UUIDs and transaction ids, dates, the checkout's product choice,
exclusive filters, and argument types. A failure is a `ValidationError` with `status` None, and
nothing is sent. What depends on the key's mode or on stored data is left to the API: the 5 USD
test-mode cap, `https`-only live URLs, the frequency minimum (1 hour live, 5 minutes test), the
95-day export window, uniqueness.

## Retries and idempotency

| | |
|---|---|
| Retried methods | every read (GET), and the 7 creates: `checkout_sessions.create_payment`, `checkout_sessions.create_subscription`, `products.create`, `customers.create`, `webhooks.endpoints.create`, `invitations.create`, `refunds.initiate` |
| Never retried | every other write: updates, deletes, `checkout_sessions.expire`, `subscriptions.cancel`, `subscriptions.execute_test_billing`, `members.trust`, `members.remove`, `invitations.revoke`, `webhooks.verify_remote` |
| Retried on | a network error or timeout, a 5xx, a 429, a 409 `idempotency_key_in_use` |
| Not retried on | any other 4xx (422 `idempotency_key_reused` included), a 3xx, an unusable response |
| Attempts | 3 retries by default (`max_retries=n`; `0` disables them) |
| Back-off | 1 s, 2 s, 4 s…; a 429 waits for its `Retry-After` if longer. A wait above 60 s is not made: the `RateLimitError` is raised at once |

`qbitflow.is_retryable(error)` says whether an error is of a transient kind. `timeout` bounds each
attempt; a retried call may take longer in total.

**Idempotency keys.** Each call of a create sends a fresh `Idempotency-Key` (a UUID v4) and reuses
it on every retry of that call: a create retried after a timeout answers the first result instead
of opening a second checkout. To retry **across processes** (a queue re-running a job after a
crash), pass your own stable key:

<!-- docs:snippet retries-idempotency -->
```python
# Network errors, timeouts, 5xx and 429 are retried with back-off (3 retries by default).
client = qbitflow.QBitFlow.from_env(max_retries=5)

order_reference = "order-1042"
session = client.checkout_sessions.create_payment(
    product_name="T-shirt",
    description="Blue, size M",
    price=4.99,
    reference=order_reference,
    # A key derived from the order: any retry, even from another process after a crash,
    # returns this same checkout instead of creating a second one.
    options=qbitflow.RequestOptions(idempotency_key=f"checkout-{order_reference}"),
)
print("Send the customer to", session.link)
```
<!-- /docs:snippet -->

The same key with other params is an `IdempotencyError` (422 `idempotency_key_reused`).
`RequestOptions(request_id=...)` also sends an `X-Request-Id`, echoed in errors. A key is 1 to 255 printable ASCII characters without spaces, and only successful answers are kept
(24 hours): after a 4xx, the same key runs the request again. A `409 idempotency_key_in_use` (the
first request still running) is retried automatically. Other methods ignore the option. Retry the
other writes yourself only after reading the resource's state (a 504 may have done the work).

## Configuration

```python
import os

import httpx

from qbitflow import QBitFlow

client = QBitFlow(
    os.environ["QBITFLOW_API_KEY"],
    timeout=10,  # seconds, per attempt
    max_retries=5,
    http_client=httpx.Client(proxy="http://proxy.internal:3128"),  # proxies, transports, tracing…
)
```

| Constructor argument | Default | |
|---|---|---|
| `base_url` | `https://api.qbitflow.app/v2` (`qbitflow.DEFAULT_BASE_URL`) | an absolute `http(s)` URL; a trailing `/` is stripped |
| `timeout` | 30 (`DEFAULT_TIMEOUT`) | seconds, per attempt; positive |
| `max_retries` | 3 (`DEFAULT_MAX_RETRIES`) | `0` disables retries; negative is refused |
| `http_client` | an `httpx.Client` the SDK creates (and closes) | yours is never closed by the SDK, and never follows redirects for it |
| `on_behalf_of` | none | every request acts in that member's space |

| `RequestOptions` field (`options=`, every method) | |
|---|---|
| `on_behalf_of` | acts in that member's space for this call; `""` forces the organization's |
| `idempotency_key` | the 7 creates only: your own `Idempotency-Key` |
| `request_id` | sends `X-Request-Id` (1 to 128 of `A-Z a-z 0-9 - _ . :`) |

| Webhook argument (`WebhookRouter`, `verify`, `construct_event`) | Default |
|---|---|
| `tolerance` | 300 seconds (`webhooks.DEFAULT_TOLERANCE`; 0 or less keeps it) |
| `now` (`verify`, `construct_event`) | the system clock |
| `on_error` (`WebhookRouter`) | none: called with `(event, exception)` for every 400 and 500 |

`QBitFlow.from_env(**overrides)` reads `QBITFLOW_API_KEY` (required: a `ValidationError` naming
it otherwise), `QBITFLOW_BASE_URL` and `QBITFLOW_ON_BEHALF_OF` (when set and not empty); its
keyword arguments are the constructor's and win over the environment.

A bad argument makes `QBitFlow(...)` raise a `ValidationError`. A client's configuration never
changes; `client.on_behalf_of(...)` derives clients that share it. Use the client as a context
manager, or call `client.close()`, to close the connections the SDK opened. Every request sends
`User-Agent: qbitflow-python/3.0.0` (`qbitflow.__version__`). The SDK is synchronous; a client is
safe to share between threads.

## Migrating from 2.x

3.0.0 is a rewrite for API v2: base URL `/v2`, a new client with keyword-only arguments, UUID ids,
members and invitations instead of users and claims, a new webhook signature, typed errors.
**[MIGRATION-v3.md](MIGRATION-v3.md)** maps every 2.x method and type to its replacement, with
before/after code for the common tasks.

## Examples

Runnable scripts in [`examples/`](examples) (`QBITFLOW_API_KEY=sk_… python examples/<name>.py`;
`QBITFLOW_BASE_URL` optional). The code blocks of this README come from their `# docs:start`
regions ([CONTRIBUTING.md](CONTRIBUTING.md#website-snippets)).

| Example | Shows | Other environment |
|---|---|---|
| [`client_setup.py`](examples/client_setup.py) | a client and `me()`, `QBitFlow.from_env` | |
| [`checkout.py`](examples/checkout.py) | a payment checkout, its status, waiting, expiry | `WAIT=1` waits for the payment |
| [`catalog.py`](examples/catalog.py) | create and list products, list customers, a checkout for a product | |
| [`payments.py`](examples/payments.py) | a page of payments, one payment, every payment, `format_amount` | `PAYMENT_UUID` |
| [`refunds.py`](examples/refunds.py) | refund half of a payment, the active refunds | `PAYMENT_UUID` (refunds it) |
| [`subscriptions.py`](examples/subscriptions.py) | a subscription checkout with a trial; one subscription's access, bills, test billing, cancel at period end | `SUBSCRIPTION_UUID`, `TEST_BILL=1`, `CANCEL=1` |
| [`marketplace.py`](examples/marketplace.py) | invitations, members, `on_behalf_of`, held funds, fee, trust, removal | `INVITE=1`, `INVITATION_UUID`, `MEMBER_UUID`, `UPDATE_FEE=1`, `TRUST=1`, `REMOVE=1` |
| [`webhook_endpoints.py`](examples/webhook_endpoints.py) | create a webhook endpoint, the event log | `CREATE_ENDPOINT=1` |
| [`webhook_fastapi.py`](examples/webhook_fastapi.py) | a `WebhookRouter` mounted in FastAPI (needs `fastapi` and `uvicorn`) | `QBITFLOW_WEBHOOK_SECRET` (no API key) |
| [`webhook_handler.py`](examples/webhook_handler.py) | a `WebhookRouter` behind a standard-library server: typed handlers, deduplication, `has_access` | `QBITFLOW_WEBHOOK_SECRET` (no API key) |
| [`webhook_verify.py`](examples/webhook_verify.py) | `construct_event` on a delivery signed with `webhooks.sign` (offline) | `QBITFLOW_WEBHOOK_SECRET` (optional, no API key) |
| [`errors_and_retries.py`](examples/errors_and_retries.py) | error classes, `is_retryable`, idempotency keys across processes | |
| [`accounting.py`](examples/accounting.py) | a year of accounting events, as models and as `qbitflow-2026.csv` | |
| [`currencies.py`](examples/currencies.py) | the currencies customers can pay with | |

The examples share the order references `order-1042` (payment) and `order-1043` (subscription),
unique per space: those that create a payment checkout expire it before they exit, so they can
run again.

## Testing

```bash
pip install -e ".[dev]"
mypy qbitflow/ && flake8 qbitflow/ tests/ examples/ && black --check qbitflow/ tests/ examples/ && isort --check-only qbitflow/ tests/ examples/ && pytest
```

`pytest` runs the offline suite against stub transports, including the cross-SDK conformance
vectors in `tests/fixtures/vectors/`, and the website snippet check
([CONTRIBUTING.md](CONTRIBUTING.md#website-snippets)). The live checks need an API key **and** an explicit base
URL:

```bash
QBITFLOW_API_KEY=sk_… QBITFLOW_BASE_URL=https://… pytest tests/test_integration.py -v
```

The read-only checks only read; the write checks also need `QBITFLOW_LIVE_WRITES=1` and a
test-mode key (or `QBITFLOW_ALLOW_LIVE_MODE_WRITES=1`).

## License

This project is licensed under the MPL-2.0 License: see the [LICENSE](LICENSE) file. See also
[COMPLIANCE.md](COMPLIANCE.md) and the [trademark policy](TRADEMARKS.md).

## Support

- 📖 [Documentation](https://qbitflow.app/docs)
- 📧 [Email Support](mailto:support@qbitflow.app)
- 🐛 [Issue Tracker](https://github.com/qbitflow/qbitflow-python-sdk/issues)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Security

For security issues, please email security@qbitflow.app instead of using the issue tracker (see
[SECURITY.md](SECURITY.md)).
