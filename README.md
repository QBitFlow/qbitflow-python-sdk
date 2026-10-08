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

```python
import os

from qbitflow import QBitFlow

# One client per API key, shared by the whole program. `with` closes its connections.
with QBitFlow(os.environ["QBITFLOW_API_KEY"]) as client:  # ValidationError: not an sk_… key
    # The recommended start-up check: what is this key, and which mode is it in?
    me = client.me()  # AuthenticationError for an unknown or revoked key
    if me.space is not None:
        print(f"{me.space.organization_name}, role {me.role}, test mode {me.space.test}")

    # A hosted checkout for a one-time payment of 4.99 USD.
    session = client.checkout_sessions.create_payment(
        product_name="Premium access",
        price=4.99,
        reference="order-1042",
        success_url="https://shop.example.com/thanks?session={{UUID}}",
        cancel_url="https://shop.example.com/cart",
    )
    print("Send the customer to", session.link)
```

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

```python
import os

from qbitflow import Event, PaymentCompleted, SubscriptionStatusChanged, WebhookRouter

router = WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])


def mark_order_paid(reference: str, event_id: str) -> None: ...  # your code (idempotent)


def update_access(subscription_uuid: str, has_access: bool) -> None: ...  # your code


@router.on("payment.completed")
def fulfil(data: PaymentCompleted, event: Event) -> None:
    # At least once: the same event can arrive twice, deduplicate on event.id.
    mark_order_paid(data.reference or data.uuid, event_id=event.id)


@router.on("subscription.statusChanged")
def access_changed(data: SubscriptionStatusChanged, event: Event) -> None:
    update_access(data.uuid, data.has_access())
```

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

**FastAPI** (or Starlette's `Route(..., router.fastapi_endpoint(), methods=["POST"])`):

```python
from fastapi import FastAPI

app = FastAPI()
app.add_api_route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
```

Inside a route of your own, `return await router.handle_asgi(request)` answers the Starlette
`Request`. Anything else (a queue consumer, another framework): `router.handle(raw_body,
signature_header)` returns a `WebhookResult` whose `status` you answer. The details are in
[Webhooks](#webhooks).

### Checkout, success page, and waiting in a script

```python
from qbitflow import PLACEHOLDER_UUID, CheckoutSessionStatusValue

session = client.checkout_sessions.create_payment(
    product_name="Premium access",
    price=4.99,
    reference="order-1042",
    # QBitFlow replaces {{UUID}} with the session's id when it redirects the customer.
    success_url=f"https://shop.example.com/thanks?session={PLACEHOLDER_UUID}",
)

# On the success page: show the state, but fulfil on the webhook (anyone can open the URL).
status = client.checkout_sessions.get_status(session.uuid)

# In a script, a test or a back-office job: poll until completed or expired (10 minutes at most).
final = client.checkout_sessions.wait_for_completion(session.uuid, timeout=600, interval=3)
if final.status != CheckoutSessionStatusValue.COMPLETED:
    print("not paid:", final.status)  # expired, or still pending when the timeout elapsed
```

### Access control

```python
if sub.has_access():  # current_period_end is set and now is before it, whatever the status
    print("grant access")
```

### Displaying amounts

Amounts in a token's smallest unit are exact decimal strings: convert them with string
arithmetic, never through a `float`.

```python
from qbitflow import format_amount, parse_amount

payment = client.payments.get("pay@0192f1c2-2222-7c4d-9e5f-6a7b8c9d0e1f")
if payment.currency is not None:
    shown = payment.currency.format_amount(payment.amount_min_units)  # "10" for "10000000"
    print(shown, payment.currency.symbol)

assert format_amount("1500000", 6) == "1.5"
assert parse_amount("1.5", 6) == "1500000"  # ValidationError beyond 6 decimal places
```

### A yearly accounting export

```python
from pathlib import Path

# The API serves at most 95 days per export: these split the range and join the parts.
events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
Path("qbitflow-2026.csv").write_text(client.accounting.export_csv_range("2026-01-01", "2026-12-31"))
```

### A client from the environment

```python
from qbitflow import QBitFlow

# QBITFLOW_API_KEY (required), QBITFLOW_BASE_URL and QBITFLOW_ON_BEHALF_OF (optional).
client = QBitFlow.from_env(timeout=10)  # keyword arguments override the environment
```

## Authentication and acting for a member

Every request sends your API key in `X-API-Key`. Keys are created in the QBitFlow dashboard; each
belongs to one **space** (your organization's, or one of its members') and one **mode** (test or
live). `QBitFlow(...)` only checks the key's shape (non-blank, starting with `sk_`) and sends
nothing: call `me()` to check it online.

```python
me = client.me()
if me.space is None or not me.space.test:
    raise SystemExit("this job must run with a test-mode key")
print("acting as", me.role, "in", me.space.organization_name)  # admin: an organization key
```

Keep the key in a secret store or an environment variable, never in code. Keys issued before API v2
(`sk_<digits>_…`) still work; rotate them in the dashboard to the `sk_<uuid>_…` format.

### `On-Behalf-Of`: acting in a member's space

A marketplace's **organization key** can act in any of its members' spaces: create their products
and checkouts, read their payments. Name the member by their **user UUID** (`Member.user_uuid`,
also in the `member.joined` webhook). A non-member, an owner or admin of the team, or a member of
the other mode answers 404.

```python
from qbitflow import RequestOptions

member_uuid = "0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f"  # Member.user_uuid

# A client acting in the member's space. It shares the connections and settings of client.
seller = client.on_behalf_of(member_uuid)
print(len(seller.products.list()), "products in the seller's space")

# One request only: the request option wins over the client's.
page = client.payments.list(options=RequestOptions(on_behalf_of=member_uuid))
print(len(page.items), "payments of the seller")

# "" forces the organization's own space for one request of the seller's client.
own = seller.products.list(options=RequestOptions(on_behalf_of=""))
print(len(own), "products of the organization")
```

`QBitFlow(key, on_behalf_of=uuid)` sets it for every request of a client. A value that is not a
UUID (or the nil UUID) is a `ValidationError`, raised at once, and nothing is sent.

## Checkout sessions

A checkout session is a hosted payment page. Create it, send your customer to its `link`, and act
on the webhook. The session's id (`pay@…` or `sub@…`) is also the id of the payment or the
subscription it creates once the customer's transaction is confirmed.

Name the product with **exactly one** of `product_uuid`, `product_reference`, or an inline
product (`product_name` + `price`, `description` optional):

```python
session = client.checkout_sessions.create_payment(
    product_uuid="0192f1c2-1111-7c4d-9e5f-6a7b8c9d0e1f",  # or product_reference="tshirt-blue-m"
    reference="order-1043",  # your order id: unique per space
    customer_reference="crm-42",  # kept on the payment
    success_url="https://shop.example.com/orders/1043?session={{UUID}}&type={{TRANSACTION_TYPE}}",
    cancel_url="https://shop.example.com/cart",
    expires_in_minutes=30,  # 10 to 1440
)
print("pay at", session.link, "- session", session.uuid)
```

A subscription checkout takes the same arguments plus its terms, each optional over a
subscription product's:

```python
from qbitflow import Duration, DurationUnit

session = client.checkout_sessions.create_subscription(
    product_name="Pro plan",
    price=4.99,  # USD per period
    frequency=Duration(value=1, unit=DurationUnit.MONTHS),
    trial_period=Duration(value=14, unit=DurationUnit.DAYS),
    min_periods=3,  # the customer commits to 3 periods
    success_url="https://app.example.com/billing?subscription={{UUID}}",
)
print("subscribe at", session.link)
```

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

```python
from qbitflow import CheckoutSessionStatusValue

status = client.checkout_sessions.get_status(session.uuid)
if status.status == CheckoutSessionStatusValue.COMPLETED:
    print("paid, tx", status.tx_hash)
elif status.status == CheckoutSessionStatusValue.EXPIRED:
    print("expired unpaid:", status.message)
elif status.status == CheckoutSessionStatusValue.WAITING_CONFIRMATION:
    print("sent, waiting for the network")
elif status.last_attempt is not None:  # created, or a status this SDK does not know
    print("last attempt failed:", status.last_attempt.code)  # the customer may try again
```

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
to fulfil orders.

```python
final = client.checkout_sessions.wait_for_completion(session.uuid, timeout=120, interval=5)
print(final.status)  # completed, expired, or still created/waitingConfirmation after 120 s
```

### Expire

End a session early (an order cancelled on your side). It answers its status, and
`checkout.expired` follows. Once the customer paid or is paying it is a `409 tx_already_sent`.

```python
expired = client.checkout_sessions.expire(session.uuid)
print(expired.status)  # expired
```

## Products and customers

Products are optional (a checkout can name an inline product) and give you a reusable catalog
with payment links. A subscription product carries its terms.

```python
from qbitflow import Duration, DurationUnit, SubscriptionTermsParams

product = client.products.create(
    name="Pro plan",
    description="Everything, billed monthly",
    price=4.99,
    reference="pro-monthly",  # unique per space; generated when left out
    subscription=SubscriptionTermsParams(frequency=Duration(value=1, unit=DurationUnit.MONTHS)),
)

# Only the arguments given change. A new price applies to new checkouts and subscribers only.
product = client.products.update(product.uuid, price=5.99, is_active=False)  # hidden from list()

everything = client.products.list(include_hidden=True, subscription=True)
print(product.payment_link, len(everything))
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

```python
from datetime import datetime, timedelta, timezone

since = datetime.now(timezone.utc) - timedelta(days=30)  # aware datetimes only
page = client.payments.list(
    created_after=since,
    include_members=True,  # organization key: the members' payments too
    limit=50,
)
for p in page.items:
    print(
        f"{p.uuid} {p.reference!r}: {p.amount:.2f} USD ({p.explorer_url}), "
        f"merchant got {p.metadata.tx_amounts.usd.merchant:.2f} USD"
    )

payment = client.payments.get("pay@0192f1c2-2222-7c4d-9e5f-6a7b8c9d0e1f")
by_ref = client.payments.get_by_reference("order-1042")
print(payment.tx_hash, by_ref.uuid, payment.refundable)
```

- **Filters**: `customer_uuid`, `product_uuid`, `created_after` / `created_before` (both
  excluded), `refunded`, and, with an organization key acting for itself, `include_members`
  (every member's rows, each naming its `user_uuid`) or `user_uuid` (one member's). The last two
  exclude each other.
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

```python
from datetime import datetime, timezone

print(sub.has_access())  # current_period_end is set and now is before it
print(sub.has_access(datetime(2026, 12, 1, tzinfo=timezone.utc)))  # at a given time (naive: UTC)
```

Every subscription model has it, the subscription webhooks' data included.

`action_required` says what the customer must do (`topUpAllowance`, `raiseMaximum`,
`confirmTrial`; `None`: nothing): point them to the `management_page_link` the subscription
webhooks carry.

```python
from qbitflow import SubscriptionStatus

page = client.subscriptions.list(status=SubscriptionStatus.PAST_DUE)
for sub in page.items:
    if sub.dunning is not None:
        print(sub.uuid, sub.dunning.remaining_attempts, "attempts left")

sub = client.subscriptions.get("sub@0192f1c2-3333-7c4d-9e5f-6a7b8c9d0e1f")  # cancelled ones too
print(sub.status, sub.price_usd, "USD per period")

# Every bill, newest first: the iterator fetches the pages lazily.
for bill in client.subscriptions.iterate_bills(sub.uuid):
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

```python
result = client.subscriptions.cancel(sub.uuid, immediate=False)
# ConflictError 409 subscription_already_stopped_or_inactive; NotFoundError once cancelled
if result.pending:
    # HTTP 202: the on-chain cancellation is still confirming and the status is not updated yet.
    # It goes on regardless; subscription.statusChanged tells the end.
    print("cancellation confirming")
else:
    print("now", result.subscription.status)  # stopped
```

`cancel` answers 200 when done and 202 (`pending`) while confirming on-chain. It is never retried
automatically.

### Test billing

In test mode a subscription is billed only when you ask, with live's statuses and webhooks:

```python
state = client.subscriptions.execute_test_billing(sub.uuid)
# ConflictError 409 payment_not_due before next_billing_date; BadRequestError for a live one
print(state.stage, state.outcome, state.failure_code)
```

Walk the timeline once in test mode: a 5-minute frequency, pay from a test wallet, trigger the
bill, then empty the wallet and trigger it again to see `subscription.billingFailed` and
`pastDue`.

## Refunds

```python
# Refunds waiting for an answer. From the organization's space the members' are included by
# default: include_members=False leaves them out.
for r in client.refunds.list(include_members=False):
    print(r.uuid, r.tx_uuid, r.initiated_by, r.reason, r.amount_usd)

# Answered refunds (approved or rejected), page by page.
for r in client.refunds.iterate_inactive():
    print(r.uuid, r.status, r.explorer_url)
```

`refunds.initiate` starts a refund of a payment (`pay@…`) or a bill (`sub-hist@…`) of the space.
**It creates a pending refund: no money moves until you sign the transfer in the dashboard**, from
the wallet that was paid. `refund.completed` tells you when it is sent.

```python
from qbitflow import ConflictError

try:
    refund = client.refunds.initiate(
        tx_uuid="pay@0192f1c2-2222-7c4d-9e5f-6a7b8c9d0e1f",
        refund_percent=50.0,  # of everything the customer paid, network fee included; None = 100
        reason="Damaged in transit",
        merchant_message="Sorry about that: half of your payment is on its way back.",
    )
    print(refund.uuid, refund.status)  # pending
except ConflictError as exc:
    if exc.code != "refund_already_exists":
        raise
    print("already refunded:", exc.details["refundUuid"])  # one refund per transaction
```

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

```python
created = client.invitations.create(
    email="seller@example.com",
    trust_layer=True,  # hold their payments until members.trust
    organization_fee_percent=5.0,  # your commission: 0 to 50 %, at most 2 decimals
    redirect_url="https://market.example.com/welcome",
)  # ConflictError 409 already_joined for a member; RateLimitError beyond 50 invitations an hour
print(created.invitation.uuid, created.link)  # the link is also emailed
```

**2. Wait for `member.joined`.** The seller exists once they accepted: store the event's
`user_uuid` and match `invitation_uuid` to your invitation. Never trust the redirect's
`?invitationUuid=` (anyone can open it).

```python
from qbitflow import MemberJoinedEvent

if isinstance(event, MemberJoinedEvent):
    print("invitation", event.data.invitation_uuid, "accepted by", event.data.user_uuid)
```

**3. Sell for them.** The seller adds their receiving wallet in their QBitFlow dashboard (only
they can, not needed while you hold their funds). Then act in their space:

```python
if not client.wallets.list_supported_currencies(user_uuid=member_uuid):
    raise SystemExit("the seller cannot be paid yet: their checkouts would answer 409 merchant_not_ready")

seller = client.on_behalf_of(member_uuid)
session = seller.checkout_sessions.create_payment(
    product_name="Handmade mug",
    price=4.5,
    success_url="https://market.example.com/orders/{{UUID}}",
)  # PermissionDeniedError 403 policy_disabled when your policies don't let members do this
print(session.link)
```

**4. Hear of every sale.** An organization webhook endpoint receives every seller's events by
default; the event's `user_uuid` names the seller. Use it as `on_behalf_of` for follow-up reads.

**5. Commission and held funds.** Each payment records your fee in `metadata.organization_fee`
and `metadata.tx_amounts`. While you hold a seller's funds (`trust_layer` True,
`Member.trusted_at` None), their payments go to your wallet and the net is owed to them:

```python
held = client.members.get_held_funds(member_uuid)
print(f"owed to the seller: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")

# Their new payments go to their own wallets from now on. What is held stays held until you
# release it from the dashboard (heldFunds.released tells you).
member = client.members.trust(member_uuid)
if member.trusted_at is not None:
    print("trusted since", member.trusted_at.isoformat())

# Change the commission (a checkout already created keeps its fee).
client.members.update(member_uuid, organization_fee_percent=7.5)
```

- `members.list` / `iterate` / `get`, `members.list_held_funds` (every member owed), and
  `seller.members.get_own_held_funds()` (the seller's side) complete the reads.
- `members.remove` ends a seller's membership in the key's mode: their keys stop working and
  their checkouts close. It is a `409 held_funds_pending` while you hold their live funds: release
  them first.
- `invitations.list` / `iterate` (by `status`) and `invitations.revoke` manage the invitations.
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
both included), as models or as CSV text:

```python
from pathlib import Path

for e in client.accounting.export_json("2026-09-01", "2026-09-30"):
    print(e.type, e.payment_uuid, e.tx_time_utc, e.token_symbol, e.gross_amount, e.net_amount)

csv = client.accounting.export_csv("2026-09-01", "2026-09-30")
Path("qbitflow-2026-09.csv").write_text(csv)
```

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

```python
from qbitflow import EventType

created = client.webhooks.endpoints.create(
    url="https://shop.example.com/webhooks/qbitflow",
    events=[  # None: every type, including the ones added later
        EventType.PAYMENT_COMPLETED,
        EventType.CHECKOUT_EXPIRED,
        EventType.SUBSCRIPTION_STATUS_CHANGED,
    ],
    description="Order fulfilment",
)
# The whsec_… secret is shown only this once: put it in your secret store now.
print(created.uuid, created.secret)
```

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
`webhooks.parse_event` only parses (a `ValidationError` for a body that is not a v2 event):

```python
from typing import Optional

from qbitflow import PaymentCompletedEvent, ValidationError, WebhookSignatureError, webhooks


def handle_delivery(raw_body: bytes, signature_header: Optional[str], secret: str) -> int:
    """Returns the HTTP status to answer."""
    try:
        event = webhooks.construct_event(raw_body, signature_header, secret)
    except WebhookSignatureError as exc:
        print("rejected:", exc.reason)  # e.g. noMatchingSignature, timestampOutsideTolerance
        return 400
    except ValidationError:
        return 400  # not a v2 event: an endpoint still on v1
    if isinstance(event, PaymentCompletedEvent):  # narrow the union by class
        print("fulfil order", event.data.reference)
    return 200  # any other type, or one added after this SDK (UnknownEvent): acknowledge it
```

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

Every event of the space, newest first, with each one's deliveries:

```python
from qbitflow import EventType

for logged in client.webhooks.events.iterate(type=EventType.PAYMENT_COMPLETED):
    detail = client.webhooks.events.get(logged.id)
    for d in detail.deliveries:
        print(detail.event.id, d.url, d.delivered, len(d.attempts))
    break  # the first one is enough here: breaking stops the fetching
```

## Currencies

```python
currencies = client.currencies.list_available(test=True)
by_id = {c.id: c for c in currencies}  # e.g. 6-decimal USDC

if currencies:
    c = client.currencies.get(currencies[0].id)  # resolve one id
    print(c.symbol, c.decimals, len(by_id))
```

`list_available` lists every currency checkouts can take, `list_main` the chains' native coins,
and `get` one by id, to resolve the `currency_id`, `available_currency_ids` and
`accepted_currency_ids` fields. These routes are public and **limited to 60 requests a minute per
IP: cache the list** at start-up instead of reading it per request. Payments, bills and
subscriptions already carry their `currency`.

## Pagination and iterators

Paginated lists return a `Page[T]`: `items`, and `next_cursor` (`None` on the last page, else
the value to pass back as `cursor=`, verbatim); `page.has_more` says whether another page follows.

```python
cursor = None
while True:
    customers = client.customers.list(limit=100, cursor=cursor)
    for c in customers.items:
        print(c.email)
    if not customers.has_more:
        break
    cursor = customers.next_cursor
```

Each paginated list has an `iterate…` twin returning an iterator: it fetches one page at a time,
only as you consume it, keeps your filters and page size, and stops when you `break`. An error is
raised from the loop.

```python
for c in client.customers.iterate(verified=True):
    print(c.uuid, c.email)
```

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

```python
from qbitflow import ApiError, ConflictError, RateLimitError, ValidationError

try:
    client.customers.create(name="Ada", email="ada@example.com")
    print("created")
except ValidationError as exc:
    for f in exc.field_errors:
        print(f"{f.field}: {f.message}")  # show it next to the form field
except ConflictError as exc:
    if exc.code != "unique_violation":
        raise
    print("taken:", exc.details.get("field"))  # email or reference
except RateLimitError as exc:
    print("slow down, retry in", exc.retry_after, "s")
except ApiError as exc:
    # Quote the request id to support.
    print(f"QBitFlow error {exc.status} {exc.code} (request {exc.request_id})")
```

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

```python
from qbitflow import IdempotencyError, RequestOptions

order_id = "order-1044"
try:
    session = client.checkout_sessions.create_payment(
        product_name="T-shirt",
        price=4.99,
        reference=order_id,
        options=RequestOptions(
            idempotency_key="checkout-" + order_id,  # the same key returns the same session
            request_id="job-7781",  # sent as X-Request-Id, echoed in errors
        ),
    )
    print(session.link)
except IdempotencyError:
    raise SystemExit("this key was already used with other params")  # 422 idempotency_key_reused
```

A key is 1 to 255 printable ASCII characters without spaces, and only successful answers are kept
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

Runnable scripts in [`examples/`](examples) (`QBITFLOW_API_KEY=sk_… python examples/<name>.py`):

| Example | Shows |
|---|---|
| [`checkout.py`](examples/checkout.py) | a payment checkout, its status, expiry |
| [`subscriptions.py`](examples/subscriptions.py) | a subscription checkout with a trial, filtered lists, bills, cancel at period end |
| [`marketplace.py`](examples/marketplace.py) | invite a seller, sell `on_behalf_of`, held funds, trust |
| [`webhook_handler.py`](examples/webhook_handler.py) | a `WebhookRouter` behind a standard-library server: typed handlers, deduplication, `has_access` |
| [`errors_and_retries.py`](examples/errors_and_retries.py) | error classes, `is_retryable`, idempotency keys across processes |

## Testing

```bash
pip install -e ".[dev]"
mypy qbitflow/ && flake8 qbitflow/ tests/ && black --check qbitflow/ tests/ && isort --check-only qbitflow/ tests/ && pytest
```

`pytest` runs the offline suite against stub transports, including the cross-SDK conformance
vectors in `tests/fixtures/vectors/`. The live checks need an API key **and** an explicit base
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
