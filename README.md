# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MPL-2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

The official Python SDK for [QBitFlow](https://qbitflow.app), non-custodial crypto payments: hosted
checkouts, one-time payments, subscriptions, refunds, marketplaces with commissions and held
funds, accounting exports and signed webhooks. Customers pay from their own wallets, on Ethereum,
Base and Solana, straight to yours.

- **API v2**, every integrator route: 14 services, 53 public routes, one `QBitFlow` client.
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

> Coming from 2.x? Read [MIGRATION-v3.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/MIGRATION-v3.md): 3.0.0 targets API v2 and changes the
> client and most names.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Integration recipes](#integration-recipes)
- [Authentication and acting for a member](#authentication-and-acting-for-a-member)
- [Checkout sessions](#checkout-sessions)
- [Products and customers](#products-and-customers)
- [Payments, transactions and failures](#payments-transactions-and-failures)
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
pip install "qbitflow>=3,<4"
```

**Requires Python 3.10 or later** (tested on 3.10 to 3.14). Runtime dependencies: `httpx` (0.24 or
later, below 1.0) and `pydantic` (2.5 or later, below 3). The SDK is synchronous and needs nothing
else.

The webhook router's framework adapters import their framework only when you call them, so no
web framework is a dependency. The optional extras only install a supported version of one next
to the SDK:

| Extra | Installs | For |
|---|---|---|
| `qbitflow[flask]` | `flask>=2.2` | `router.flask_view()` |
| `qbitflow[django]` | `django>=4.2` | `router.django_view()` |
| `qbitflow[fastapi]` | `fastapi>=0.100` | `router.fastapi_endpoint()` |
| `qbitflow[starlette]` | `starlette>=0.27` | `router.fastapi_endpoint()` in a Starlette route, `router.handle_asgi()` |

```bash
pip install "qbitflow[fastapi]>=3,<4"
```

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
    price_usd="4.99",  # USD, a decimal string: never a float
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
  zero value (`""`, `0`, `False`, `[]`, `{}`, `ZERO_TIME`). Optional fields are `Optional[...]`,
  `None` when absent (the API never sends `null`: an optional field without a value is absent).
  The wire's `from` is `from_`.
- **Money is a decimal string, never a float**, in requests and responses alike: USD amounts
  (`price_usd="4.99"`, `amount_usd`, `total_usd`), token amounts (`amount == "10"` in the token's
  units, next to `amount_min_units == "10000000"` on-chain and the `currency` object) and fee rates
  in percent (`fee_percent == "0.99"` is 0.99 %, `refund_percent == "50"`). Inputs take a `str` or a
  `decimal.Decimal` (sent as `str(value)`); a `float` or an `int` is a `ValidationError`, because
  a float cannot carry `0.1` exactly and the API refuses a JSON number. Inputs are checked before
  sending: at most 2 decimals, no sign or exponent (`"12.50"` is fine). Compute with `Decimal`, or
  `format_amount` / `parse_amount`. They come back canonical (`"12.50"` reads back `"12.5"`,
  `"12.00"` as `"12"`): compare amounts as decimals, never as strings.
- **Metadata:** products, customers, checkouts and subscriptions carry `metadata`, your own
  `dict[str, str]` (an order id, a CRM key): at most 50 keys of 1 to 40 characters among
  `A-Z a-z 0-9 _ - . :`, values of at most 500 characters without control or bidirectional
  characters. A checkout's is copied onto its payment or subscription and into their webhooks. On
  an update it is **merged**: a key set to a value sets it, a key set to `""` deletes it, keys not
  named are kept. Never put secrets or personal data in it.
- **Enums** are `StrEnum`s (`SubscriptionStatus.ACTIVE`). A value this SDK does not know yet is
  kept as the raw `str`: compare with `==`, and give every `match` a default case.
- **Times** are timezone-aware `datetime`s (the API sends RFC 3339 in UTC; any offset is
  accepted).

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
access with `data.has_access()`, or `@router.on("refund.approved")` to reverse an order. Starlette takes the same endpoint:
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
with [`checkout_sessions.get`](#status), but fulfil on the webhook (anyone can open the URL). In a script, a
test or a back-office job, poll until the checkout is completed or expired:

<!-- docs:snippet wait-for-completion -->
```python
# For scripts and back-office jobs: fulfil orders on the payment.completed webhook. It polls
# checkout_sessions.get; on timeout it returns the last status seen (check .status).
final = client.checkout_sessions.wait_for_completion(session_uuid, timeout=600, interval=3)
if final.status == qbitflow.CheckoutSessionStatusValue.COMPLETED:
    print("paid")
else:
    print("not paid:", final.status)  # expired, or still open when the timeout elapsed
```
<!-- /docs:snippet -->

### Access control

Grant access while `now < access_until`, whatever the subscription's status: the end of the period
paid for, plus an hour for an `active` one, since its renewal is billed within minutes of its due
date. `has_access()` does exactly that, reading `current_period_end` for a subscription you stored
before the API sent `access_until`:

<!-- docs:snippet has-access -->
```python
subscription = client.subscriptions.get(subscription_uuid)
# now is before access_until, whatever the status: the end of the period paid for, plus an
# hour for an active subscription while its renewal is billed.
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

Token amounts come both ways: `amount` in the token's units (`"4.99"`) and `amount_min_units`,
its on-chain integer (`"4990000"`). `parse_amount` raises a `ValidationError` beyond the given
decimal places. A model's currency knows its decimals:
`payment.currency.format_amount(payment.amount_min_units)`.

### A yearly accounting export

<!-- docs:snippet accounting-export -->
```python
# The API exports at most 92 days at a time (both included): the *_range methods split any
# range into windows, request them in order and join the results (the CSV header once).
events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
for event in events:
    print(event.type, event.tx_uuid, event.tx_time_utc.date(), event.gross_amount_usd)

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
live). `QBitFlow(...)` only checks the key's shape (non-blank, starting with `sk_`, printable
ASCII without spaces) and sends nothing: call `me()` to check it online ([quick start](#quick-start)). `me.role` is `admin` for
an organization key, and `me.space.test` tells test mode from live (a job that must only run in
test mode checks it first).

Keep the key in a secret store or an environment variable, never in code. The SDK never shows it
(`repr(client)`, errors). API v2 issues keys shaped `sk_<test|live>_<uuid>_<secret>`; the SDK
never parses a key, it only checks its shape. Keys in an earlier format (v1's `sk_<digits>_…`,
and `sk_<uuid>_<test|live>_…`) are refused by the API (`401`): create a new one in the dashboard.

### `On-Behalf-Of`: acting in a member's space

A marketplace's **organization key** can act in any of its members' spaces: create their products
and checkouts, read their payments. Name the member by their **user UUID** (`Member.user_uuid`,
also in the `member.joined` webhook). A non-member, an owner or admin of the team, or a member of
the other mode answers 404. Acting for a member, the request's role is `user`: the admin methods
(`members`, `invitations`, `wallets.list_for_member`, `wallets.list_accepted_currencies` with a
`user_uuid`) answer 403.

<!-- docs:snippet client-on-behalf-of -->
```python
# Every request of this client sends On-Behalf-Of: it acts in the member's space.
seller = client.on_behalf_of(member_uuid)  # shares the connections and settings of client
products = seller.products.list()
print(len(products.items), "products on the first page of the seller's space")
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
UUID (or the nil UUID, or blank) is a `ValidationError`, raised at once, and nothing is sent;
`""` (or `None`) means the organization level and the header is then **omitted** (never sent
blank: the API answers 403 to a blank one).

## Checkout sessions

A checkout session is a hosted payment page. Create it, send your customer to its `link`, and act
on the webhook. The session's id (`pay@…` or `sub@…`) is also the id of the payment or the
subscription it creates once the customer's transaction is confirmed.

Name the product with **exactly one** of `product_uuid`, `product_reference`, or an inline
product (`product_name` + `price_usd`, `description` optional, as in the
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

A payment checkout of a subscription product sells it **once**, at its price (its terms are
ignored, nothing recurs). A subscription checkout of a one-time product needs `frequency`, else a
`ValidationError` on `frequency` naming the product. An inline product of a **subscription**
checkout creates a hidden product (`is_active` False), reused by the next checkouts with the same
name, description and price (`products.list(include_hidden=True)` shows it); a payment's inline
product creates none.

`reference` is your order id, unique per space. `customer_reference` is kept on the payment
(**no receipt without a QBitFlow customer**: see [Products and customers](#products-and-customers)),
`expires_in_minutes` (10 to 1440) sets the checkout's lifetime, and `metadata` is copied onto the
payment or the subscription and into their webhooks (`payment.completed`, `subscription.*`,
`checkout.expired`). The answer is a `CreatedCheckoutSession`: `link`, `uuid` and `expires_at`,
always set.

A subscription checkout takes the same arguments plus its terms (`frequency`, `trial_period`,
and `min_periods`, the periods the customer commits to), each optional over a subscription
product's:

<!-- docs:snippet checkout-create-subscription -->
```python
session = client.checkout_sessions.create_subscription(
    product_name="T-shirt",
    description="Blue, size M",
    price_usd="4.99",  # USD per period, a decimal string
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
  webhook, or on `checkout_sessions.get`. Left out, the space's `checkout.defaults` setting
  applies (set in the dashboard).
- **A member's own key** sends `success_url` and `cancel_url` while its organization's
  `members.checkoutRedirects` policy allows it (on by default: a seller's shop sends its
  customers back to its own site). With the policy off for the member, sending either is a
  `PermissionDeniedError` (403 `policy_disabled`, `details["policy"]` `"members.checkoutRedirects"`
  and `details["field"]` naming the field, `successUrl` first), nothing is created, and the
  member's checkouts go where the organization's `checkout.defaults` says. The organization's key
  acting for the member (`on_behalf_of`) may always send them.
- **Errors to expect:** `409 merchant_not_ready` (`details["reason"]`) when the space's wallets
  accept no currency, or for a subscription of a member whose funds you hold (`fundsHeld`);
  `409 unique_violation` when another payment or open session holds the `reference`;
  `400 validation_failed` above `"5"` USD in test mode, fees included (`details["max"]`, a
  string), and at `"0.25"` or less for a live subscription (`details["min"]`); `404` for an
  unknown product or customer; `410 merchant_closed` for a removed member's space.

### Fees

A checkout, a payment's or a subscription's, can add amounts to its product's price: a tax,
shipping, a service fee, and QBitFlow's processing fee when you have the customer pay it. The
customer sees them line by line and pays them with the price (a subscription: with every bill).

<!-- docs:snippet checkout-create-payment-fees -->
```python
session = client.checkout_sessions.create_payment(
    product_name="T-shirt",
    description="Blue, size M",
    price_usd="3.99",  # USD: you keep the price and your lines
    reference="order-1044",
    success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
    cancel_url="https://shop.example.com/orders/cancel",
    fees=qbitflow.CheckoutFees(
        # Your own lines (up to 10), shown to the customer and paid with the price.
        items=[
            qbitflow.FeeItem(
                label="Shipping", description="Standard, 3 to 5 days", amount_usd="0.75"
            ),
        ],
        # The customer also pays QBitFlow's processing fee, a last line computed by QBitFlow.
        processing_fee=True,
    ),
)
# The customer pays the price plus every line (then the network fee on top).
print("Send the customer to", session.link)
```
<!-- /docs:snippet -->

- **Your lines**: `fees=CheckoutFees(items=[...])`, up to 10 `FeeItem`s, shown in that order.
  `label` is one line of 1 to 40 characters, `description` (optional) at most 200, and
  `amount_usd` is a decimal string (`"0.75"`) or a `Decimal`: above 0, at most 1,000,000, with at
  most 2 decimals (a float is refused). The SDK checks all of this before sending
  (`fees.items[0].amountUsd`…).
- **The processing fee**: `processing_fee=True` adds a last line, `Processing fee`, computed by
  QBitFlow on the price and your lines at your platform fee. QBitFlow's fee is taken on
  everything charged, this line included, so the line is grossed up (and rounded up to the cent)
  to leave you at least the price and your lines, as if no fee were taken: $100 + $20 VAT at
  0.99 % is a $1.20 processing fee, $121.20 charged, $120.00 kept. The rate is the checkout's:
  QBitFlow's fee for your space when the checkout is created (a schedule by volume, unless
  QBitFlow set you a custom rate). Left out (`None`), the space's
  `checkout.customerPaysProcessingFee` setting decides (off by default; the organization's team
  sets it in the dashboard, for a member's space too: a member doesn't); `False` turns it off for
  one checkout. A product link's checkout follows the
  setting too.
- **What the customer pays** is the price plus every line: the payment's `amount_usd`. It is
  what is charged and split (QBitFlow's fee, and an organization's, are taken on it) and recorded
  on the payment with its `price_usd` and `fees` (each a `FeeLine`: `type` `custom` or
  `processingFee`, `label`, `description`, `amount_usd`). The network fee comes on top, paid by
  the customer's wallet (`settlement.split.network_fee`).
- **Test mode** caps the total, fees included, at `"5"` USD: `400 validation_failed` on `fees`
  (`details["max"]`).
- The lines are fixed when the session is created; `checkout.expired` carries them
  (`PaymentSessionData.price_usd`, `fees`, `amount_usd`).
- **Subscriptions** take the same `fees` (`create_subscription(..., fees=CheckoutFees(...))`,
  the same rules), locked with the price: every bill, the first one and each next one, charges
  the price plus every line, whatever the product's price or your fee becomes. The `Subscription`
  keeps them as `fees` next to `price_usd` (which stays the price); a bill's `amount_usd` and
  `subscription.upcomingBill`'s `amount_usd` include them, and the maximum and allowance the
  subscriber signs are sized on that amount. A trial's upgrade keeps the trial's lines.
  `checkout.customerPaysProcessingFee` applies to subscription checkouts too.

### Status

<!-- docs:snippet checkout-status -->
```python
status = client.checkout_sessions.get(session_uuid)  # pay@… or sub@…
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
| `expired` | Expired unpaid (`checkout.expired` was sent). Once QBitFlow no longer keeps the record, a 404 | yes |

**Never cancel an order on `last_attempt`:** a failed attempt is not final, and the customer can
pay from the same checkout until it expires. Release what the order holds on `checkout.expired`.

`expires_at` is set while the session is open. For scripts, tests and back-office jobs,
`wait_for_completion` polls `checkout_sessions.get` until the session is `completed` or `expired`
and returns that status; when `timeout` (seconds, default 600; 0 or less means the default)
elapses first it returns the last status seen, so check `.status`. `interval` (default 3) is at
least 1 second; the last wait is shortened to the time left, then one last poll is made at the
deadline. Errors of `get` (a 404 included) are raised. Webhooks remain the way
to fulfil orders. The code is in the
[recipes](#checkout-success-page-and-waiting-in-a-script).

### Expire

End a session early (an order cancelled on your side). It answers its status (`expired`,
`expires_at` the time you expired it), and `checkout.expired` follows. Expiring it again answers
`expired` too, without `expires_at` (only the first answer has it). Once the customer paid or is
paying it is a `409 tx_already_sent`.

<!-- docs:snippet checkout-expire -->
```python
# An order cancelled on your side: the checkout can no longer be paid.
expired = client.checkout_sessions.expire(session_uuid)
print(expired.status)  # expired; checkout.expired follows
```
<!-- /docs:snippet -->

## Products and customers

Products are optional for payments (a payment checkout can name an inline product; a
subscription checkout's inline product becomes a hidden product: [Checkout sessions](#checkout-sessions))
and give you a reusable catalog with payment links. The `reference` is generated when left out.

<!-- docs:snippet products-create -->
```python
product = client.products.create(
    name="T-shirt",
    description="Blue, size M",
    price_usd="4.99",  # USD, a decimal string: never a float
    reference="tshirt-blue-m",  # your own id: unique per space
)
print(product.uuid, product.payment_link)
```
<!-- /docs:snippet -->

<!-- docs:snippet products-list -->
```python
# iterate walks every page (list returns one); hidden products only with include_hidden.
for product in client.products.iterate():
    print(product.reference, product.name, product.price_usd, "USD")
```
<!-- /docs:snippet -->

`products.list` returns one page (a `Page`, newest first) and `products.iterate` walks them all.
A subscription product carries its terms. `update` (`PATCH`) changes only the arguments given; a
new price or new terms apply to new checkouts and subscribers only, and an inactive product is
hidden from the list unless `include_hidden=True` (`subscription=True` lists the subscription
products only). A
member's key gives a product terms (on `create` or `update`) only while the organization's
`members.subscriptions` policy allows it (`403 policy_disabled` otherwise); with the policy off,
the links of the member's subscription products open nothing:

```python
from qbitflow import Duration, DurationUnit, SubscriptionTermsParams

terms = SubscriptionTermsParams(frequency=Duration(value=1, unit=DurationUnit.MONTHS))
plan = client.products.create(name="Pro plan", price_usd="4.99", subscription=terms)
plan = client.products.update(
    plan.uuid,
    price_usd="5.99",
    is_active=False,  # hidden from products.list
    description="",  # "" clears it
    metadata={"sku": "TS-BLUE-M", "legacy": ""},  # merged: "" deletes a key
)
print(plan.price_usd, plan.metadata)
```

`products.get` and `delete` (`204`) complete the set. `products.get_by_reference("tshirt-blue-m")`
runs the list's reference filter (`GET /products?reference=`, hidden products included) and
returns its one product, or raises `NotFoundError` (status 404, code `not_found`) when there is
none, exactly like an unknown uuid. Deleting a product does not stop its subscriptions: cancel
them with `subscriptions.cancel` if the product is gone for good.

```python
customer = client.customers.create(
    first_name="Ada",
    last_name="Lovelace",
    email="ada@example.com",
    reference="crm-42",
    metadata={"plan": "pro"},
)

# "" (or None) clears last_name, phone_number or address; leaving the argument out keeps it.
customer = client.customers.update(customer.uuid, phone_number="")

# An email is not unique: several customers of a space may share one.
page = client.customers.list(email="ada@example.com")
print(len(page.items), "customers with this email")

by_reference = client.customers.get_by_reference("crm-42")  # NotFoundError when none
print(customer.uuid == by_reference.uuid)
```

`customers.get`, `list` / `iterate` (by `email` or `reference`) and `delete` (`204`) complete
the set. A checkout given `customer_uuid` or `customer_reference` asks the customer
nothing (`customer_reference` is kept on the payment, and links your customer with that reference
if there is one; none is created); without either, the checkout asks what your
`checkout.customerDetails` setting says (the full details by default).

**Without a QBitFlow customer, the buyer gets no receipt and no other customer email** (a
subscription's billing emails included): QBitFlow has no address for them. To have them, create
the customer with that reference and their email first
(`customers.create(reference="crm-42", first_name="Ada", email="ada@example.com")`). That works
even after the checkout was created, as long as it is before the payment is recorded.

The clearable update fields (`customers.update`'s `last_name`, `phone_number` and `address`,
`products.update`'s and `webhooks.endpoints.update`'s `description`) default to `NOT_GIVEN`:
left out, the value is unchanged; `""` or `None` clears it. `metadata` on an update is merged
(`None`: unchanged).

## Payments, transactions and failures

A `Payment` exists once its transaction is confirmed, with its checkout session's `pay@…` id.

<!-- docs:snippet payments-list -->
```python
page = client.payments.list(refunded=False, limit=20)  # newest first
for payment in page.items:
    # Amounts are decimal strings: the token's (amount, with currency) and USD (amount_usd).
    print(
        payment.uuid,
        payment.reference,
        payment.amount,
        payment.currency.symbol,
        f"({payment.amount_usd} USD)",
    )
if page.has_more:
    print("next page: cursor =", page.next_cursor)  # pass it back, verbatim, as cursor=
```
<!-- /docs:snippet -->

<!-- docs:snippet payments-get -->
```python
payment = client.payments.get(payment_uuid)  # pay@…, the id of its checkout session
print(payment.reference, payment.amount_usd, "USD", payment.tx_hash, payment.metadata)

# Runs GET /payments?reference= and returns its one payment (NotFoundError when none).
by_reference = client.payments.get_by_reference("order-1042")  # your order id
print(by_reference.uuid)
```
<!-- /docs:snippet -->

A payment carries its transaction (`tx_hash`, `explorer_url`, `confirmed_at`), your `metadata`
(copied from its checkout, read-only), how it settled (`settlement`), and whether it can be
refunded (`refundable`, `refund`).

- **The amounts:** `amount` is what the customer paid **in the token's units** (`"10"` for 10
  USDC, with `amount_min_units` and the `currency` object), `amount_usd` the same in USD:
  `price_usd` (the product's price at the checkout) plus every line of `fees` (the
  [checkout's fees](#fees)). It is what the contracts split; the network fee the customer paid on
  top is not in it (`paid`, `paid_min_units` and `paid_usd` include it: a refund's base).
- **The settlement** (`settlement`): QBitFlow's `fee_percent`, the `organization_fee` and
  `referral_fee` when they apply, the `split` (`platform`, `organization`, `referral`,
  `merchant`, `network_fee`, each a `TokenAmount`: `amount`, `amount_min_units`, `amount_usd`) and
  the `transaction` that paid it (`block_number`, `block_time`, `gas_used`, its `fee` in the
  native coin).

```python
print("price", payment.price_usd, "USD")
for line in payment.fees:  # a tax, shipping, the processing fee
    print(f"  {line.label}: {line.amount_usd} USD")
print("paid", payment.amount_usd, "USD =", payment.amount, payment.currency.symbol)
if payment.settlement.split is not None:
    print("you received", payment.settlement.split.merchant.amount, payment.currency.symbol)
```

- **Filters**: `customer_uuid`, `product_uuid`, `created_after` / `created_before` (aware
  `datetime`s, both excluded), `reference`, `refunded`, and, with an organization key acting for
  itself, `include_members` (every member's rows, each naming its `user_uuid`) or `user_uuid`
  (one member's). The last two exclude each other. `payments.get_by_reference` runs the
  `reference` filter and raises `NotFoundError` when no payment has it.
- **Reading a member's row** from the organization's space:
  `client.payments.get(id, include_members=True)`, or `on_behalf_of` the member.
- **The transactions feed** of one-time payments and subscription bills, newest first:
  `transactions.list` / `iterate`, with the same filters (`reference` excepted) plus `type`
  (`TransactionKind.PAYMENT`, `TransactionKind.BILL`), `subscription_uuid` and `refunded`. Each
  `Transaction` reads like its resource (a `Payment` or a `Bill`); open it with `payments.get` or
  `subscriptions.get_bill`.

<!-- docs:snippet transactions-list -->
```python
# One feed of one-time payments and subscription bills, newest first; each row reads like
# its resource. type= filters it to one kind (TransactionKind.PAYMENT or .BILL).
feed = client.transactions.list(limit=20)
for tx in feed.items:
    print(tx.type, tx.uuid, tx.amount_usd, "USD")
```
<!-- /docs:snippet -->

- **Failures** are the failed attempts to pay a checkout or a bill. They never moved money and
  are not final: the customer can try again.

```python
from qbitflow import FailureCategory

for f in client.failures.iterate(category=FailureCategory.INSUFFICIENT_BALANCE):
    print(f"{f.tx_uuid} attempt {f.attempt}: {f.code} ({f.attempted_usd} USD)")
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
| `stopped` | Cancelled during its period: never billed again, `cancelled` at `next_billing_at` |
| `cancelled` | Over (`cancellation_reason` says why). Final |

**Access rule: grant access while `now < access_until`, whatever the status.** `access_until` is
`current_period_end` (the paid-through date), plus 1 hour for an `active` subscription: QBitFlow
bills a renewal within minutes of its due date, so checking `current_period_end` would cut every
subscriber off for those minutes at each renewal (show it as "paid through", don't gate on it). A
`stopped` or `paused` subscription has paid for its period; a `pastDue` one's period has ended.
`subscription.has_access()` applies it, reading `current_period_end` for a subscription stored
before `access_until` existed ([access control](#access-control));
`has_access(at)` checks at a given `datetime` (a naive one is UTC). Every subscription model has
it, the subscription webhooks' data included.

<!-- docs:snippet subscriptions-get -->
```python
subscription = client.subscriptions.get(subscription_uuid)  # sub@…, cancelled ones too
print(subscription.status, "paid until", subscription.current_period_end)
```
<!-- /docs:snippet -->

`action_required` says what the customer must do (`topUpAllowance`, `raiseMaximum`,
`confirmTrial`; `None`: nothing): point them to the subscription's `management_page_link`.

A subscription's price is locked at signup: `price_usd` plus its `fees` lines, every bill. Its
`allowance` (`None` during a trial) is what the subscriber's wallet still lets QBitFlow bill
(`amount`, `amount_min_units`, `amount_usd`), how many bills that covers (`remaining_periods`) and
the most one bill may charge (`max_per_period`). `remaining_periods` counts bills before each
bill's network fee, so it is usually higher than the checkout's "N payments" (an estimate that kept
room for network fees). `last_billed_at`, `next_billing_at` and
`cancellable_at` are `None` when they don't apply.

```python
from qbitflow import SubscriptionStatus

page = client.subscriptions.list(status=SubscriptionStatus.PAST_DUE)
for sub in page.items:
    if sub.dunning is not None:
        print(sub.uuid, sub.dunning.remaining_attempts, "attempts left")

# Every bill, newest first: the iterator fetches the pages lazily.
for bill in client.subscriptions.iterate_bills(subscription_uuid):
    if bill.period_end is not None:
        print(f"{bill.uuid}: {bill.amount_usd} USD, paid until {bill.period_end.date()}")
```

- `subscriptions.get_by_reference` reads one by your checkout's `reference` (the list's
  `?reference=` filter; `NotFoundError` when none); `get_bill` one bill (`sub-hist@…`). Bills
  carry no metadata: read the subscription's.
- Before its checkout completes, `subscriptions.get` is a 404: read the checkout session instead.
- `subscriptions.update` changes its `metadata` only, merged (a key set to `""` deletes it), and
  answers the subscription:

<!-- docs:snippet subscriptions-update -->
```python
# Metadata is merged into the subscription's: "" deletes a key, keys not named are kept.
# It is the only thing a merchant edits on a subscription; webhooks carry it.
updated = client.subscriptions.update(subscription_uuid, metadata={"plan": "pro", "coupon": ""})
print(updated.metadata.get("plan"))
```
<!-- /docs:snippet -->

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
subscription cancelled already, or stopped already with `immediate=False`, is a `ConflictError`
(409 `subscription_already_stopped_or_inactive`); a `NotFoundError` only means it isn't in your
space (or doesn't exist). A trial is
cancelled immediately only (`immediate=False` on a trial: a `ValidationError`, 400
`validation_failed` on `immediate`).

### Test billing

In test mode a subscription is billed only when you ask, with live's statuses and webhooks.
`test_bill` answers once the attempt settled: a `TestBill` with the bill's `sub-hist@…` id, its
`stage` and, once done, its `outcome` (a live subscription: a `BadRequestError` `test_mode_only`; a
bill not due: a `ConflictError` `payment_not_due`; a cancelled subscription: a `ConflictError`
`subscription_already_stopped_or_inactive`):

<!-- docs:snippet subscriptions-test-bill -->
```python
# Test mode only: run the next bill now instead of on its due date.
bill = client.subscriptions.test_bill(subscription_uuid)
print(bill.bill_uuid, bill.stage, bill.outcome, bill.failure_code)  # sub-hist@…
```
<!-- /docs:snippet -->

Before `next_billing_at` it is a `ConflictError` (409 `payment_not_due`); for a live
subscription a `BadRequestError` (400 `test_mode_only`).

Walk the timeline once in test mode: a 5-minute frequency, pay from a test wallet, trigger the
bill, then empty the wallet and trigger it again to see `subscription.billingFailed` and
`pastDue`.

## Refunds

`refunds.list` filters by `status` (up to 5 statuses, sent as repeated `?status=`; `None`:
every status) and `tx_uuid` (the refund of one transaction). From the organization's space the
members' refunds are included by default: `include_members=False` leaves them out.

<!-- docs:snippet refunds-list -->
```python
# The ones waiting for an answer (status None: every status).
page = client.refunds.list(status=[qbitflow.RefundStatus.PENDING])
for refund in page.items:
    print(refund.uuid, refund.tx_uuid, refund.initiated_by, refund.reason, refund.amount)
```
<!-- /docs:snippet -->

`refunds.iterate` walks every page, e.g. the answered refunds:

```python
from qbitflow import RefundStatus

for r in client.refunds.iterate(status=[RefundStatus.APPROVED, RefundStatus.REJECTED]):
    print(r.uuid, r.status, r.explorer_url)
```

`refunds.get` reads one refund by its `refund@…` id:

<!-- docs:snippet refunds-get -->
```python
refund = client.refunds.get(refund_uuid)  # refund@…
# pending (a customer's request), approved or rejected.
print(refund.uuid, refund.status, f"{refund.refund_percent}%", refund.amount)
```
<!-- /docs:snippet -->

Refunds are read only here: there is no create. A refund is **requested by the customer** (the
refund page; you approve or reject it in the dashboard) or **sent by you from the dashboard**,
signed from the wallet that was paid. Yours exists only once its transfer confirmed: it is recorded
`approved`, and `refund.approved` (with `initiated_by` `merchant`) is the first and only event
about it. `refund.requested` is always a customer's request.

`refund_percent` is a percent string (`"100"`: all of it) of everything the customer paid (`paid`,
network fee included); `amount` / `amount_min_units` / `amount_usd` is what it sends back. There
is one refund per transaction, whatever it became: `Payment.refundable` / `not_refundable_reason`
say whether one would be accepted now.

A refund is `pending` (a customer's request waiting for your answer), `approved` or `rejected`
(both final). `initiated_by` is `customer` or `merchant`.

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
    hold_funds=True,  # hold their payments until you trust them (always sent)
    organization_fee_percent="10",  # your commission on their payments: "0" to "50" %
    redirect_url="https://shop.example.com/sellers/welcome",
)
# The seller exists once they accept: wait for the member.joined webhook.
# created.uuid is what member.joined's invitation_uuid names; its user_uuid is the seller.
# QBitFlow also emails them a link of their own.
print("invitation", created.uuid, "link:", created.link)
```
<!-- /docs:snippet -->

`hold_funds` is required (always sent); the commission is a percent string from `"0"` to `"50"`
with at most 2 decimals. The answer is a `CreatedInvitation`: the invitation's fields and its
`link` (only here). QBitFlow emails the person a link of their own (another token, never
returned), so don't compare it with `link`. `send_email=False` creates the invitation without
emailing it: share `link` in your own onboarding (signing up through it still emails the person a
confirmation). Inviting a
member is a `ConflictError` (409 `already_joined`), and more than 50 invitations an hour, emailed
or not, a `RateLimitError` (raised at once).

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
if not client.wallets.list_accepted_currencies(user_uuid=member_uuid):
    raise SystemExit("the seller cannot be paid yet")
```

Then act in their space with `seller = client.on_behalf_of(member_uuid)`
([On-Behalf-Of](#on-behalf-of-acting-in-a-members-space)): `seller.checkout_sessions` and
`seller.products` create the seller's checkouts and products. Your policies may not let members
do this: a `PermissionDeniedError` (403 `policy_disabled`). Policies (`members.*`) are changed
from the dashboard only: no API key can write them.

While you hold a seller's funds (`Member.trusted_at` None), they sell **one-time payments only**: a
subscription checkout in their space answers `409 merchant_not_ready` with `details["reason"]`
`fundsHeld` (`qbitflow.MerchantNotReadyReason.FUNDS_HELD`) until you trust them
(`members.trust`), and their subscription products' links open nothing.

**4. Hear of every sale.** An organization webhook endpoint receives every seller's events by
default; the event's `user_uuid` names the seller. Use it as `on_behalf_of` for follow-up reads.

**5. Commission and held funds.** Your commission is taken on what remains after QBitFlow's fee:
`(amount − QBitFlow's fee) × organization_fee_percent / 100`, rounded down, the seller getting the
rest (on $7.50 at 0.5 % and 10 %: QBitFlow 0.0375, you 0.74625, the seller 6.71625). Each payment
records it in `settlement.organization_fee` and `settlement.split.organization`. While you hold a seller's funds (`hold_funds` True,
`Member.trusted_at` None), their payments go to your wallet and the net is owed to them
(`HeldFunds.total_usd`, each `LedgerEntry` with what it counts for: `owed`, `owed_min_units`,
`owed_usd`, negative on a refund line):

<!-- docs:snippet members-held-funds -->
```python
# Every member you hold funds for, the longest held first.
for summary in client.members.list_held_funds():
    print(summary.user_uuid, f"{summary.total_usd} USD over {summary.count} lines")

held = client.members.get_held_funds(member_uuid)  # one member, line by line
print(f"owed to the seller: {held.total_usd} USD over {len(held.ledgers)} lines")
```
<!-- /docs:snippet -->

The seller reads their side with their own key, or through a client acting for them
(`seller.members.get_own_held_funds()`):

<!-- docs:snippet members-own-held-funds -->
```python
# With a member's key, or a client acting on behalf of the member.
held = client.members.get_own_held_funds()
print(f"held for me: {held.total_usd} USD over {len(held.ledgers)} lines")
```
<!-- /docs:snippet -->

Trust them once you no longer want to hold their funds. Trust is one-way and narrows the seller's
currencies to their own wallets': a seller whose wallets accept none of yours is a `ConflictError`
(409 `member_has_no_wallet`; nothing changes, trust them once they've added one):

<!-- docs:snippet members-trust -->
```python
# Their new payments go to their own wallets from now on (one-way). What is held stays held
# until you release it from the dashboard (heldFunds.released tells you).
try:
    member = client.members.trust(member_uuid)
    print("trusted since", member.trusted_at)
except qbitflow.ConflictError as exc:
    if exc.code != "member_has_no_wallet":
        raise
    print("not trusted: their own wallets accept none of your currencies yet")
```
<!-- /docs:snippet -->

Change the commission:

<!-- docs:snippet members-update -->
```python
# The fee on their new payments, a percent string from "0" to "50" (a checkout already
# created keeps its fee).
member = client.members.update(member_uuid, organization_fee_percent="10")
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
print(member.first_name, member.last_name, "trusted:", member.trusted_at is not None)
for currency in member.accepted_currencies:  # empty: their checkouts answer 409
    print("  accepts", currency.code)
```
<!-- /docs:snippet -->

`members.iterate` walks every page; a `Member` has `first_name`, `last_name`,
`organization_fee_percent` and the `accepted_currencies` their checkouts take now.
`wallets.list_for_member` reads a member's wallets:

<!-- docs:snippet members-wallets -->
```python
for wallet in client.wallets.list_for_member(member_uuid):
    print(wallet.currency.chain, wallet.address)
```
<!-- /docs:snippet -->

`members.remove` ends a seller's membership in the key's mode (`204`): their keys stop working
and their checkouts close. It is a `409 held_funds_pending` while you hold their live funds:
release them from the dashboard first.

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

`invitations.list` / `iterate` (by `status`; member invitations only, the team's being managed
from the dashboard) and `invitations.revoke` (`204`, returns `None`) manage the invitations:

<!-- docs:snippet invitations-list -->
```python
page = client.invitations.list(status=qbitflow.InvitationStatus.PENDING)
for invitation in page.items:
    print(invitation.uuid, invitation.email, "expires", invitation.expires_at)
```
<!-- /docs:snippet -->

<!-- docs:snippet invitations-revoke -->
```python
client.invitations.revoke(invitation_uuid)  # 204: its link stops working
print("revoked", invitation_uuid)
```
<!-- /docs:snippet -->

- `members.list_held_funds` lists every member you owe, longest held first (a plain list).
- A seller who already uses QBitFlow joins your platform with the same account: accepting with an
  account that belongs to another organization succeeds like any acceptance, keeps its other
  memberships, and sends `member.joined` as for any member. Test-mode sellers are real accounts
  that accept from a real inbox.

## Wallets

Wallets are added and removed in the dashboard, by their owner only. The SDK reads them; every
wallet list is short and returned as a plain list.

```python
for w in client.wallets.list(with_balances=True):
    print(w.currency.chain, w.address)
    for tw in w.token_wallets:
        if tw.balance is not None:  # None when the chain couldn't be read
            print(f"  {tw.currency.code}: {tw.balance.amount} ({tw.balance.amount_usd} USD)")
```

`wallets.list_for_member(user_uuid)` reads a member's wallets (organization key), and
`wallets.list_accepted_currencies` the currencies a space's checkouts accept now (`user_uuid=`: a
member's, organization key): none means its checkouts answer `409 merchant_not_ready`.

## Accounting export

Every payment, bill, refund and fee between two dates (`YYYY-MM-DD` strings or `datetime.date`s,
both included), as models (`export_json`, a `list[AccountingEvent]`) or as CSV text
(`export_csv`); the [recipe](#a-yearly-accounting-export) exports a year with their `_range`
twins. Each row has its `type`, `tx_uuid`, `tx_time_utc`, `currency`, `gross_amount`,
`net_amount` and more.

The SDK checks the dates and `from <= to` before sending. **The API allows at most 92 days per
export, both days included** (`400 validation_failed` on `to` beyond, `details["max"]` 92).
`export_json_range` and `export_csv_range` take any range: they split it into consecutive windows
of at most 92 days (`[from, from + 91 days]`, the next one starting the day after, on calendar
dates in UTC), request them in order and join them (one list; one CSV with the first window's
header line once, then every window's rows). A range of 92 days or less is one request;
`2026-01-01` to `2026-12-31` is four: `[01-01, 04-02]`, `[04-03, 07-03]`, `[07-04, 10-03]`,
`[10-04, 12-31]`. Rows are typed `payment`, `bill`, `refund`, `organizationFee` or
`referralFee`; a value a row doesn't have (a fee that doesn't apply) is `None`, never `"0"`.

- **Dates** are the transactions' (the day their block was mined, in UTC: `tx_time_utc`), so
  consecutive exports never miss nor repeat an event. Rows are ordered by `tx_time_utc`, `type`,
  then `tx_uuid`; a refund names what it refunds in `related_tx_uuid` and `related_reference`.
- **Amounts** are in the currency's units (`"7.5"` USDC, not `7500000`), as decimal strings, next
  to `currency_decimals`, each with its on-chain twin (`gross_amount_min_units`, …). USD amounts
  (`gross_amount_usd`, …) and rates (`platform_fee_percent`, …) are decimal strings too.
  `currency` names what was paid as markets do (`USDC`, or the chain's
  native currency: `ETH`, `SOL`), and `currency_price_usd` is the USD price the amounts were
  converted at. `gross_amount = platform_fee + organization_fee + net_amount` exactly; a refund's
  net is the refunded amount, negative.
- **Network fees are never part of the net.** `network_fees_paid_by` (a `NetworkFeesPayer`) says
  whose wallet paid them: `payer` (a payment or a bill: on top of the amount, in its currency),
  `merchant` (a refund your space sent) or `organization` (a refund of a payment the organization
  held for its member). Book `network_fees` (in `network_fees_currency`, the chain's native
  currency on a refund) apart for `merchant` and `organization`.
- **CSV columns** are `AccountingEvent`'s wire keys in its field order (what happened, the USD
  amounts, the same amounts in the currency, the network fees, the rates, the on-chain proof, the
  ids): read them by header name, not position. Amounts are plain numbers there, an absent value
  an empty cell, and a cell starting with `=`, `+`, `-`, `@`, a tab or a CR gets a leading `'`.
- A `referralFee` row only has what the referrer earned (its type, time, chain, block, currency
  and the referral fee): every other field is `None`.

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
`include_members=False`. `endpoints.list` / `iterate` (paginated), `get`, `update` (`PATCH`:
`enabled=False` pauses it, `True` enables it again, `description=""` clears it, `events=[]`
receives every type) and `delete` (`204`) manage them. `delete` also deletes the endpoint's
delivery history: `events.get` no longer lists its deliveries. To keep it, disable the endpoint
instead. An endpoint's secret is shown and rotated
in the dashboard only. A replay of the create's `Idempotency-Key` within 24 hours returns the same
endpoint and secret.

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
    Refund,
    SubscriptionBilled,
    SubscriptionStatusChanged,
    UnknownEvent,
    webhooks,
)

router = webhooks.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])  # tolerance=300


@router.on("payment.completed")  # the handler gets the typed data, then the event
def fulfil(data: PaymentCompleted, event: Event) -> None:
    print(f"fulfil order {data.reference!r} ({data.uuid}): {data.amount_usd} USD", data.metadata)


@router.on(EventType.CHECKOUT_EXPIRED)  # an EventType works too
def release(data: CheckoutExpired, event: Event) -> None:
    print("release order", data.reference)


@router.on("subscription.billed")  # {bill, subscription}
def billed(data: SubscriptionBilled, event: Event) -> None:
    print(f"{data.subscription.uuid} paid until {data.bill.period_end} ({data.bill.amount_usd} USD)")


@router.on("refund.approved")  # was refund.completed
def refunded(data: Refund, event: Event) -> None:
    print(f"refund {data.uuid} of {data.tx_uuid}: {data.refund_percent}% sent back")


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
- **Order is per publication, never per subscription.** The events published together (a
  `subscription.created` and its first `subscription.billed`) reach an endpoint in that order,
  each once the previous one is delivered or abandoned; meanwhile the event log shows the waiting
  one `pending` with `waiting_for` the earlier event ([The event log](#the-event-log)). Nothing
  waits across publications: a renewal's `subscription.billed` never waits for an earlier event
  your endpoint is failing. Order those by `created_at` and the resources' own timestamps.
- **Secret rotation** needs nothing on your side: for 24 hours after a rotation the header
  carries two `v1=` signatures, the new secret's and the previous one's, and either secret
  verifies. Switch your secret within the day.
- **Timestamps** more than 5 minutes from your clock are refused (replays): `tolerance=`
  (seconds) changes it.
- **Members' events** carry the member in `event.user_uuid`: read their resources with
  `client.on_behalf_of(event.user_uuid)`.
- **No fixed source IPs**: verify the signature, never allow-list addresses.
- **v2 events only.** Every endpoint receives the v2 event envelope; a body that is not one is
  refused (a `ValidationError`, a 400 from the router).
- **Headers:** `QBitFlow-Signature`, `QBitFlow-Event-Id` and `QBitFlow-Event-Type`
  (`webhooks.SIGNATURE_HEADER`, `EVENT_ID_HEADER`, `EVENT_TYPE_HEADER`).

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
`webhooks.parse_event` only parses (a `ValidationError` for a body that is not a v2 event, or
whose data does not fit its type). In a handler that returns the HTTP status to answer:

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

`now=` sets their clock in tests (a `datetime`, naive taken as UTC as in `sign`, unix seconds,
or a callable). Not holding the secret? `client.webhooks.verify_remote(endpoint_uuid, raw_body, header)` has the API check it,
then `client.webhooks.parse_event(raw_body)` parses the body. `client.webhooks.verify`,
`construct_event` and `parse_event` are the same functions on the client.

### Event types

| `event.type` | Event class | `event.data` |
|---|---|---|
| `payment.completed` | `PaymentCompletedEvent` | `PaymentCompleted`: the `Payment` + `management_page_link` |
| `subscription.created` | `SubscriptionCreatedEvent` | the `Subscription` (`active` or `trial`, its `management_page_link` included) |
| `subscription.billed` | `SubscriptionBilledEvent` | `SubscriptionBilled`: `bill`, the `Bill` paid (until `bill.period_end`), and `subscription`, the `Subscription` as it leaves it (`.status`, `.reference`, `.metadata`) |
| `subscription.statusChanged` | `SubscriptionStatusChangedEvent` | `SubscriptionStatusChanged`: the `Subscription` + `previous_status` |
| `subscription.actionRequiredChanged` | `SubscriptionActionRequiredChangedEvent` | the `Subscription` + `previous_action_required` |
| `subscription.billingFailed` | `SubscriptionBillingFailedEvent` | the `Subscription` + `reason`, `bill_uuid`, `amount_usd` (a string), `failure_code`, `attempt`, `remaining_attempts`, `next_attempt_at` |
| `subscription.upcomingBill` | `SubscriptionUpcomingBillEvent` | the `Subscription` + `billing_at`, `amount_usd` (a string), `trial_ending`, `balance_sufficient`, `allowance_sufficient`. Sent the dashboard's `subscriptions.upcomingBillDays` before the bill (3 days by default, 0 = never), checked daily; not for a subscription whose period (a trial: the trial) is no longer than that |
| `refund.requested` / `.approved` / `.rejected` | `RefundRequestedEvent` / `RefundApprovedEvent` / `RefundRejectedEvent` | the `Refund` (`refund.approved` and `refund.rejected` were `refund.completed` and `refund.denied`) |
| `member.joined` | `MemberJoinedEvent` | `MemberJoined`: the `Member` + `invitation_uuid` |
| `member.removed` | `MemberRemovedEvent` | the `Member` |
| `heldFunds.released` | `HeldFundsReleasedEvent` | `HeldFundsReleased`: the transfer paid to the member (`amount`, `amount_usd`, `settlement.transaction`) + the `ledgers` it settled |
| `checkout.expired` | `CheckoutExpiredEvent` | `PaymentSessionData`, or `SubscriptionSessionData` when `tx_type` is `createSubscription` |
| `webhook.test` | `WebhookTestEvent` | `WebhookTest`: `endpoint_uuid`, `message` (the dashboard's test) |
| any other | `UnknownEvent` | the raw JSON value |

`qbitflow.Event` is the union of these classes (a pydantic discriminated union on `type`); every
one derives from `BaseEvent` (`id`, `type`, `created_at`, `test`, `user_uuid`).
`router.on` refuses a type it does not know (a `ValidationError`: a typo never goes unnoticed).
Webhook data never carries what only API reads return (`customer`,
`refund`/`refundable`/`not_refundable_reason`, a subscription's `dunning`, a refund's `approval`,
`customer_uuid` and `product_name`): those fields are `None` on events. It carries your
`metadata` and the `settlement`.

### The event log

Every event of the space, newest first, each exactly as it was delivered (kept at least 90 days;
`events.iterate` walks every page). `type` is sent as is, not checked against this SDK's types
(newer ones appear):

<!-- docs:snippet events-list -->
```python
page = client.webhooks.events.list(type=qbitflow.EventType.PAYMENT_COMPLETED, limit=20)
for event in page.items:  # newest first, each exactly as delivered
    print(event.id, event.type, event.created_at)
if page.has_more:
    print("more: pass", page.next_cursor, "as cursor=")  # opaque, never an event id
```
<!-- /docs:snippet -->

`events.get(event_id)` adds each one's deliveries:

```python
detail = client.webhooks.events.get(event_id)
for d in detail.deliveries:
    if d.delivered:
        print(d.url, f"delivered after {len(d.attempts)} attempts")
    elif d.next_attempt_at:
        print(d.url, f"failed, retried at {d.next_attempt_at.isoformat()}")
    elif d.waiting_for:
        print(d.url, f"queued behind {d.waiting_for}")  # no attempt yet
    elif d.pending:
        print(d.url, "about to start")  # no attempt yet
    else:
        print(d.url, f"not delivered, gave up after {len(d.attempts)} attempts")
    for attempt in d.attempts:  # oldest first; empty while queued or about to start
        print(attempt.attempt, attempt.status_code, attempt.skipped, attempt.error)
```

`pending` is true while QBitFlow still attempts the event on its own: `next_attempt_at` is set while
it is retried after a failed attempt, `waiting_for` (an `evt_…`) while it is queued behind an
earlier event of the same publication, and neither while its delivery is about to start (within a
minute). **A queued or starting delivery has no `attempts` yet**: `d.attempts[-1]` would raise
`IndexError`, so check the list first. Once `pending` is false nothing more happens on its own, and
`delivered=False` means it was abandoned after its retries (3 days in live mode, 3 hours in test
mode) or the endpoint was disabled. **A deleted endpoint's deliveries aren't listed at all**: they
are deleted with it, the successful ones included. To keep an endpoint's history, disable it
(`enabled=False`) rather than delete it. If QBitFlow can't read a delivery's progress at that
moment, `pending` comes from the attempts: true while the retry schedule still attempts the event
again (a delivery being retried never reads as abandoned), without `next_attempt_at`; a delivery
queued with no attempt yet isn't listed until its progress can be read: read the event again a
moment later.

A member's deliveries to your organization's endpoints show from the organization:
`webhooks.events.list(include_members=True)`, then `get`. Read on behalf of the member, the event
lists only the member's own endpoints (`deliveries == []` without any).

An attempt's `status_code` is `None` when the endpoint didn't answer, and on a **skipped**
attempt (`skipped=True`): a member's endpoint while the organization's `members.webhooks` policy
is off for them gets nothing posted, the attempt's `error` says why, and it doesn't count against
the endpoint's health.

## Currencies

<!-- docs:snippet currencies-list -->
```python
# A public route limited to 60 requests a minute: cache the list at start-up. One bounded
# list: the live currencies; test=True the test networks'; main=True the native coins only.
currencies = client.currencies.list()
for currency in currencies:
    print(currency.id, currency.code, currency.name, currency.chain, currency.decimals)
```
<!-- /docs:snippet -->

`currencies.list` returns the catalog as a plain list (`test=True`: the test networks'
currencies; `main=True`: only the chains' native coins), and `get` one by id (a token's
`main_currency_id`). A `Currency` has its `code` (what requests name it by: `BASE:USDC`, or `ETH`
for a native coin), `symbol`, `name`, `chain`, `decimals`, and `address` (`None` on a native
coin). These routes are public and **limited to 60 requests a minute per IP: cache the list** at
start-up instead of reading it per request. Every response that names a currency carries this
object (`Payment.currency`, `Member.accepted_currencies`, …).

## Pagination and iterators

Paginated lists return a `Page[T]`: `items`, `has_more` (another page follows), and
`next_cursor` (set iff `has_more`: the value to pass back as `cursor=`, verbatim; it is opaque,
never an id to build or parse, at most 200 characters).

<!-- docs:snippet customers-list -->
```python
page = client.customers.list(limit=20)
for customer in page.items:
    print(customer.uuid, customer.email, customer.reference)
if page.has_more:
    print("next page: cursor =", page.next_cursor)  # pass it back, verbatim, as cursor=
```
<!-- /docs:snippet -->

Each paginated list has an `iterate…` twin returning an iterator: it fetches one page at a time,
only as you consume it, keeps your filters and page size, and stops when you `break`, after the
page whose `has_more` is False (a full last page answers False: there is never an extra empty
request), or defensively on a page that claims more without a new `next_cursor` (none, the cursor
just requested, or an empty page). An error is raised from the loop.

<!-- docs:snippet pagination-iterate -->
```python
# Fetches one page at a time, only as the loop consumes it; break stops the fetching. It
# stops after the page whose has_more is False.
for payment in client.payments.iterate(limit=50):
    print(payment.uuid, payment.amount_usd, "USD")
```
<!-- /docs:snippet -->

| Method | Iterator | Page size: default / max |
|---|---|---|
| `products.list`, `customers.list` | `iterate` | 20 / 100 |
| `payments.list`, `transactions.list`, `failures.list` | `iterate` | 20 / 100 |
| `subscriptions.list`, `subscriptions.list_bills` | `iterate`, `iterate_bills` | 20 / 100 |
| `refunds.list` | `iterate` | 20 / 100 |
| `members.list`, `invitations.list` | `iterate` | 20 / 100 |
| `webhooks.endpoints.list`, `webhooks.events.list` | `iterate` | 20 / 100 |

`limit` is sent as given and clamped by the API (0 or less: 20; above 100: 100). The bounded lists
answer one page and return its items as a plain `list`: `currencies.list`, `wallets.list`,
`wallets.list_for_member`, `wallets.list_accepted_currencies`, `members.list_held_funds` and
`accounting.export_json` (a page that ever claims more is followed, under the same guards, so a
list is never cut short silently).

## Errors

Every error the SDK raises derives from `QBitFlowError` and from `ApiError`, which carries the
fields every error has; catch the most specific class you can act on:

| Class | When | Codes and fields worth knowing |
|---|---|---|
| `ValidationError` | 400 `validation_failed`, or input the SDK refused **before sending** (`status` None) | `field_errors`: each failing input by its wire name, dotted when nested (`frequency.unit`) |
| `BadRequestError` | any other 400 | `foreign_key_violation` (`details["field"]`), `test_mode_only`, `sender_is_receiver` |
| `AuthenticationError` | 401 | a missing, unknown, expired or revoked key (a removed member's keys too) |
| `PermissionDeniedError` | 403 | `forbidden` (a role or another space's resource; no details), `policy_disabled`: a member's key doing what its organization's policy doesn't allow members (`details["policy"]` names the policy; `details["field"]` the request field it governs, e.g. a checkout's `successUrl` / `cancelUrl` under `members.checkoutRedirects`) |
| `NotFoundError` | 404 | unknown, deleted, or outside the request's space; also a `get_by_reference` that found nothing (code `not_found`, the list's `request_id`) |
| `ConflictError` | 409 | `unique_violation` (`details["field"]`), `tx_already_sent`, `merchant_not_ready` (`details["reason"]`), `held_funds_pending`, `member_has_no_wallet`, `already_joined`, `payment_not_due`, `subscription_already_stopped_or_inactive`, `idempotency_key_in_use`, `conflict` |
| `GoneError` | 410 | `merchant_closed`: a removed member's or a closed organization's space |
| `IdempotencyError` | 422 `idempotency_key_reused` | an `Idempotency-Key` reused for another request: a bug, never retried |
| `RateLimitError` | 429 | `retry_after` (seconds), `limit`, `period_seconds` |
| `ServerError` | 5xx (503 `network_unavailable`, 504 `timeout`), an unexpected 3xx (redirects are never followed), a 2xx whose body is not the expected JSON | |
| `NetworkError` | no response: DNS, connection, TLS, timeout | the cause is chained (`__cause__`) |
| `WebhookSignatureError` | a webhook signature refused, locally or by `verify_remote` | `reason` |
| `ApiError` | any other HTTP error (e.g. 413 `request_too_large`; 405 `method_not_allowed`, with an `Allow` header, for a path called with the wrong method, which the SDK never does), and the base of all the above | |

Every error carries `status` (`None` without a response), `code` (branch on it, never on
`message`), `message`, `details` (never `None`, and raw: money in it is a string,
`details["max"] == "5"`, but the accounting window's `max` is the integer 92), `request_id`,
`field_errors` and `raw_body`.
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
markup characters), references (`A-Z a-z 0-9 . _ : @ -`, 1 to 100, never `.` or `..` alone, on
creates, on `product_reference` / `customer_reference`, on the `reference` filters and on
`get_by_reference`), emails (the customers' `email` filter too), phone
numbers, absolute `http(s)` URLs, USD amounts (decimal strings with at most 2 decimals, above 0, at
most 1,000,000), percents (decimal strings, at most 2 decimals: `organization_fee_percent` 0 to
50), metadata (keys, values, at most 50 keys), durations (a frequency between 1 unit and 1 year), UUIDs and transaction ids, dates, cursors (at most 200
characters), the checkout's product choice, the enum filters (refund `status`, transaction
`type`, failure `kind` and `category`, invitation `status`), exclusive filters, and argument types
(a float where money is expected included). A failure is a `ValidationError` with `status` None,
`code` `""`, and nothing is sent. What depends on the key's mode or on stored data is left to the
API: the `"5"` USD test-mode cap, `https`-only live URLs, the live subscription minimum
(`"0.25"`), the frequency minimum (1 hour live, 5 minutes test; a development server lowers the
live one to 1 minute, production never does), the 92-day export window, the
50-key cap on merged metadata, uniqueness.

## Retries and idempotency

| | |
|---|---|
| Retried methods | every read (GET), and the 6 creates: `checkout_sessions.create_payment`, `checkout_sessions.create_subscription`, `products.create`, `customers.create`, `webhooks.endpoints.create`, `invitations.create` |
| Never retried | every other write: updates (`subscriptions.update` included), deletes, `checkout_sessions.expire`, `subscriptions.cancel`, `subscriptions.test_bill`, `members.trust`, `members.remove`, `invitations.revoke`, `webhooks.verify_remote`; a 429 on them is raised, not retried |
| Retried on | a network error or timeout, a 5xx, a 429, a 409 `idempotency_key_in_use` |
| Not retried on | any other 4xx (422 `idempotency_key_reused` included), a 3xx, an unusable response |
| Attempts | 3 retries by default (`max_retries=n`; `0` disables them) |
| Back-off | 1 s, 2 s, 4 s…; a 429 waits for its `Retry-After` if longer. A wait above 60 s is not made: the `RateLimitError` is raised at once |

`qbitflow.is_retryable(error)` says whether an error is of a transient kind. `timeout` bounds each
attempt, the response body included; a retried call may take longer in total.

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
    price_usd="4.99",  # a decimal string, never a float
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
    # proxies, transports, tracing… (proxy= needs httpx 0.26+; older: proxies=)
    http_client=httpx.Client(proxy="http://proxy.internal:3128"),
)
```

| Constructor argument | Default | |
|---|---|---|
| `base_url` | `https://api.qbitflow.app/v2` (`qbitflow.DEFAULT_BASE_URL`) | an absolute `http(s)` URL with a host, without credentials (`user@`), query or fragment; a trailing `/` is stripped |
| `timeout` | 30 (`DEFAULT_TIMEOUT`) | seconds, per attempt (connecting, sending, and reading the whole answer); positive and finite |
| `max_retries` | 3 (`DEFAULT_MAX_RETRIES`) | `0` disables retries; negative is refused |
| `http_client` | an `httpx.Client` the SDK creates (and closes) | yours is never closed by the SDK, and never follows redirects for it |
| `on_behalf_of` | none | every request acts in that member's space; `None` or `""`: the organization level (no header) |

| `RequestOptions` field (`options=`, every method) | |
|---|---|
| `on_behalf_of` | acts in that member's space for this call; `""` forces the organization's (the header is omitted, never sent blank) |
| `idempotency_key` | the 6 creates only: your own `Idempotency-Key` |
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
`User-Agent: qbitflow-python/3.1.1` (`qbitflow.__version__`). The SDK is synchronous; a client is
safe to share between threads.

## Migrating from 2.x

3.0.0 is a rewrite for API v2: base URL `/v2`, a new client with keyword-only arguments, UUID ids,
REST routes, money as decimal strings, members and invitations instead of users and claims, a new
webhook signature, typed errors.
**[MIGRATION-v3.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/MIGRATION-v3.md)** maps every 2.x method and type to its replacement, with
before/after code for the common tasks.

## Examples

Runnable scripts in [`examples/`](https://github.com/QBitFlow/qbitflow-python-sdk/tree/main/examples) (`QBITFLOW_API_KEY=sk_… python examples/<name>.py`;
`QBITFLOW_BASE_URL` optional). The code blocks of this README come from their `# docs:start`
regions ([CONTRIBUTING.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/CONTRIBUTING.md#website-snippets)).

| Example | Shows | Other environment |
|---|---|---|
| [`client_setup.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/client_setup.py) | a client and `me()`, `QBitFlow.from_env` | |
| [`checkout.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/checkout.py) | a payment checkout, its status, waiting, expiry; a checkout with fees | `WAIT=1` waits for the payment |
| [`catalog.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/catalog.py) | create and list products, list customers, a checkout for a product | |
| [`payments.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/payments.py) | a page of payments, one payment, every payment, the payments-and-bills feed, `format_amount` | `PAYMENT_UUID` |
| [`refunds.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/refunds.py) | the pending refunds (customers' requests), one refund | |
| [`subscriptions.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/subscriptions.py) | a subscription checkout with a trial; one subscription's access, bills, metadata, a test bill, cancel at period end | `SUBSCRIPTION_UUID`, `TEST_BILL=1`, `CANCEL=1` |
| [`marketplace.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/marketplace.py) | invitations, members, `on_behalf_of`, held funds, fee, trust, removal | `INVITE=1`, `INVITATION_UUID`, `MEMBER_UUID`, `UPDATE_FEE=1`, `TRUST=1`, `REMOVE=1` |
| [`webhook_endpoints.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/webhook_endpoints.py) | create a webhook endpoint, the event log | `CREATE_ENDPOINT=1` |
| [`webhook_fastapi.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/webhook_fastapi.py) | a `WebhookRouter` mounted in FastAPI (needs `fastapi` and `uvicorn`) | `QBITFLOW_WEBHOOK_SECRET` (no API key) |
| [`webhook_handler.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/webhook_handler.py) | a `WebhookRouter` behind a standard-library server: typed handlers (payments, bills, refunds), deduplication, `has_access` | `QBITFLOW_WEBHOOK_SECRET` (no API key) |
| [`webhook_verify.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/webhook_verify.py) | `construct_event` on a delivery signed with `webhooks.sign` (offline) | `QBITFLOW_WEBHOOK_SECRET` (optional, no API key) |
| [`errors_and_retries.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/errors_and_retries.py) | error classes, `is_retryable`, idempotency keys across processes | |
| [`accounting.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/accounting.py) | a year of accounting events, as models and as `qbitflow-2026.csv` | |
| [`currencies.py`](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/examples/currencies.py) | the currencies customers can pay with | |

The examples share the order references `order-1042` (payment), `order-1043` (subscription) and
`order-1044` (a payment with fees), unique per space: those that create a payment checkout expire it before they exit, so they can
run again.

## Testing

```bash
pip install -e ".[dev]"
mypy qbitflow/ && flake8 qbitflow/ tests/ examples/ && black --check qbitflow/ tests/ examples/ && isort --check-only qbitflow/ tests/ examples/ && pytest
```

`pytest` runs the offline suite against stub transports, including the conformance vectors in
`tests/fixtures/vectors/` (the cases every QBitFlow SDK passes). The live checks need an API key
**and** an explicit base URL, and skip without a key:

```bash
QBITFLOW_API_KEY=sk_… QBITFLOW_BASE_URL=https://… pytest tests/test_integration.py -v
```

The read-only checks only read; the write checks also need `QBITFLOW_LIVE_WRITES=1` and a
test-mode key (or `QBITFLOW_ALLOW_LIVE_MODE_WRITES=1`). The same gates run in CI on Python 3.10 to
3.14; [CONTRIBUTING.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/CONTRIBUTING.md)
says which ones a contribution must pass.

## License

This project is licensed under the MPL-2.0 License: see the [LICENSE](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/LICENSE) file. See also
[COMPLIANCE.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/COMPLIANCE.md) and the [trademark policy](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/TRADEMARKS.md).

## Support

- 📖 [Documentation](https://qbitflow.app/docs)
- 📧 [Email Support](mailto:support@qbitflow.app)
- 🐛 [Issue Tracker](https://github.com/QBitFlow/qbitflow-python-sdk/issues)

## Changelog

See [CHANGELOG.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/CHANGELOG.md) for version history.

## Security

For security issues, please email security@qbitflow.app instead of using the issue tracker (see
[SECURITY.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/SECURITY.md)).
