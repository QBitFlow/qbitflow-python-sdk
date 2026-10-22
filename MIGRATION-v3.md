# Migrating from 2.x to 3.0.0

3.0.0 is the Python SDK for **QBitFlow API v2**. API v2 reorganises the platform around spaces
(an organization's, and one per member), invites people instead of provisioning them, names every
resource by a UUID, uses REST routes, writes money as decimal strings and signs webhooks with a new
scheme. The SDK follows: a new client, services named after the API's areas, keyword-only
arguments, and new names for most methods and models.

2.x talks to `/v1` only; 3.0.0 talks to `/v2` only, and **`/v1` is gone**: the v2 launch
migrated v1's data (people, products, payments, subscriptions, customers, wallets, webhook URLs) to
v2's shape, so move your integration to 3.0.0 as a whole.

This guide maps everything 2.1.0 exposed (the last 2.x release) to 3.0.0. The
[README](README.md) documents 3.0.0 in full; [CHANGELOG.md](CHANGELOG.md) lists every change.

## Checklist

1. [Install and imports](#1-install-and-imports): `pip install -U qbitflow`, import from `qbitflow`.
2. [Base URL and API keys](#2-base-url-and-api-keys): `/v2`; pre-v2 keys are refused: create new ones.
3. [The client](#3-the-client): keyword-only options, `on_behalf_of(user_uuid)`, `me()`, `close()`.
4. [Keyword arguments and request options](#4-keyword-arguments-and-request-options).
5. [Method map](#5-method-map): every 2.x method and its replacement.
6. [Ids are UUID strings](#6-ids-are-uuid-strings): products, members, `On-Behalf-Of`.
7. [Users and claims become invitations, members and the trust layer](#7-users-and-claims-become-invitations-members-and-the-trust-layer).
8. [Models](#8-models): renamed models and fields, money and fee rates as decimal strings, metadata.
9. [Enum values and statuses](#9-enum-values-and-statuses): subscription and checkout statuses.
10. [Errors](#10-errors): one class per status, field errors that work.
11. [Webhooks](#11-webhooks): `QBitFlow-Signature` over the raw body, typed events, v2 only.
12. [Pagination](#12-pagination): `Page(items, has_more, next_cursor)` and iterators.
13. [Before and after](#13-before-and-after-common-tasks): common tasks.

## 1. Install and imports

```bash
pip install -U "qbitflow>=3,<4"
```

Python 3.10+, `httpx` and `pydantic>=2.5`. **Import everything from `qbitflow`**: the client,
`RequestOptions`, every model and enum, every error, and `qbitflow.webhooks`.

| 2.x import | 3.0.0 |
|---|---|
| `from qbitflow import QBitFlow` | unchanged |
| `from qbitflow.dto import …`, `from qbitflow.dto.transaction import …` | `from qbitflow import …` (names in § 8) |
| `from qbitflow.exceptions import …` | `from qbitflow import …` (names in § 10) |
| `from qbitflow import Duration` | unchanged (`Duration(value=1, unit=DurationUnit.MONTHS)`) |
| `from qbitflow import verify_webhook_signature, compute_webhook_signature, canonical_json, extract_webhook_headers, TEST_WEBHOOK_ID` | `from qbitflow import webhooks` (§ 11) |
| `qbitflow.requests`, `qbitflow.utils`, `qbitflow.config` | gone (internal) |

## 2. Base URL and API keys

- The default base URL is `https://api.qbitflow.app/v2`. If you set one, it must point at v2.
- API v2 issues keys shaped `sk_<uuid>_<test|live>_<secret>`. **Keys issued before**
  (`sk_<digits>_…`) **are refused by API v2** (`401`): create a new key in the dashboard. Treat a key
  as opaque (the SDK only checks the `sk_` prefix).
- `QBitFlow(...)` refuses a blank key, or one not starting with `sk_`, with a `ValidationError`
  (2.x raised `ValueError` for a blank key, and sent any other). It sends nothing: call
  `client.me()` to check the key online, and assert its mode (`me.space.test`) at start-up.
- A key belongs to one space and one mode. A removed member's keys answer 401.

## 3. The client

| 2.x | 3.0.0 |
|---|---|
| `QBitFlow(api_key, timeout=None, max_retries=None)` | `QBitFlow(api_key, *, base_url=None, timeout=None, max_retries=None, on_behalf_of=None, http_client=None)` |
| `timeout` (whole request) | `timeout`: seconds per attempt (default 30) |
| `max_retries` (GET only) | `max_retries`: reads and the 6 creates (default 3; `0` disables) |
| `client.one_time_payments.on_behalf_of(user_id)` (per service) | `client.on_behalf_of(user_uuid)`: a whole client acting in the member's space (`""` or `None`: the organization level, the header omitted) |
| `client.api_key` | not exposed |
| — | `client.me()`, `client.close()`, `with QBitFlow(...) as client:`, `QBitFlow.from_env()` |

Reads and creates are now retried automatically (README § Retries and idempotency): drop any
retry loop you wrapped around them, or pass `max_retries=0`.

## 4. Keyword arguments and request options

Every method takes its path id (a UUID, a transaction id…) positionally and **everything else as
keyword-only arguments**; there are no `Create…Dto` / `Update…Dto` objects any more. Keyword names
are the API's field names in snake_case (`price_usd`, `first_name`, `hold_funds`). The last
argument of every method is `options=RequestOptions(...)`:

```python
from qbitflow import RequestOptions

payment = client.payments.get(
    "pay@0192f1c2-2222-7c4d-9e5f-6a7b8c9d0e1f",
    options=RequestOptions(
        on_behalf_of="0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f",  # a member's space, this call only
        request_id="support-ticket-981",  # X-Request-Id, echoed in errors
    ),
)
print(payment.amount_usd)
```

| `RequestOptions` field | |
|---|---|
| `on_behalf_of` | act in a member's space for this call (overrides the client's; `""` = the organization, the header omitted) |
| `idempotency_key` | the 6 creates only: your own `Idempotency-Key` |
| `request_id` | sent as `X-Request-Id`, echoed in errors |

Arguments are checked before anything is sent: a wrong value or type is a `ValidationError`
naming the wire field. The update methods change only the arguments you pass; the clearable
fields (`customers.update`'s `last_name`, `phone_number`, `address`; `products.update`'s and
`webhooks.endpoints.update`'s `description`) default to `NOT_GIVEN`, and `""` or `None` clears
them.

## 5. Method map

### Checkout sessions and status (2.x `one_time_payments`, `subscriptions`, `transaction_status`)

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `one_time_payments.create_session(product_id=…, price=…, …)` | `checkout_sessions.create_payment(product_uuid=…, price_usd=…, …)` | `POST /checkout-sessions/payment`; `price_usd` a string (`"4.99"`); new `expires_in_minutes`, `metadata` and `fees`; returns a `CreatedCheckoutSession` (`link`, `uuid`, `expires_at`) |
| `subscriptions.create_session(product_id=…, frequency=…, …)` | `checkout_sessions.create_subscription(product_uuid=…, frequency=Duration(…), …)` | `POST /checkout-sessions/subscription`; inline products allowed; `frequency`, `trial_period`, `min_periods` each optional over a subscription product's terms |
| `transaction_status.get(uuid, transaction_type)` | `checkout_sessions.get(uuid)` | `GET /checkout-sessions/:uuid`; the type is in the id (`pay@…`, `sub@…`); four statuses (§ 9) |
| `transaction_status.get_websocket_url(…)` | removed | use webhooks, or poll `get` (`wait_for_completion`) |
| `one_time_payments.get_session(uuid)`, `subscriptions.get_session(uuid)` | removed | `checkout_sessions.get` for the state; the session's data comes with `checkout.expired` |
| — | `checkout_sessions.expire(uuid)` | new: end an unpaid session |

### Payments

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `one_time_payments.get(uuid)` | `payments.get(uuid, include_members=False)` | `pay@…` or the bare UUID |
| `one_time_payments.get_by_reference(reference)` | `payments.get_by_reference(reference)` | runs `GET /payments?reference=`; a `NotFoundError` when none |
| `one_time_payments.get_all(limit, cursor)` | `payments.list(limit=…, cursor=…, filters…)` / `payments.iterate(…)` | filters: `customer_uuid`, `product_uuid`, `created_after`, `created_before`, `reference`, `refunded`, `include_members` / `user_uuid` |
| `one_time_payments.get_all_combined(limit, cursor)` | `transactions.list(…)` / `transactions.iterate(…)` | `GET /transactions`; `CombinedPaymentItem` → `Transaction`; `source` → `type` (`TransactionKind.PAYMENT`, `TransactionKind.BILL`); + `subscription_uuid` |
| `one_time_payments.get_customer_for_transaction(uuid)` | removed | `payment.customer` (a summary), or `customers.get(payment.customer_uuid)` |
| — | `failures.list(…)` / `failures.iterate(…)` | new: the failed payment attempts |

### Subscriptions (and 2.x pay-as-you-go)

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `subscriptions.get(uuid)` | `subscriptions.get(uuid, include_members=False)` | cancelled subscriptions are returned too: a 404 no longer means "cancelled" |
| `subscriptions.get_by_reference(reference)` | `subscriptions.get_by_reference(reference)` | runs `GET /subscriptions?reference=`; a `NotFoundError` when none |
| `subscriptions.get_payment_history(uuid)` | `subscriptions.list_bills(uuid, limit=…, cursor=…)` / `iterate_bills(uuid)` | `GET /subscriptions/:uuid/bills`: every full bill, page by page (the customer's public 10-bill history is not part of the SDK) |
| `subscriptions.force_cancel(uuid)` → `SuccessResponse` | `subscriptions.cancel(uuid, immediate=None)` → `SubscriptionCancellation` | `POST /subscriptions/:uuid/cancel`, never retried; `pending` for an HTTP 202 (still confirming on-chain); `immediate=False` cancels at the end of the paid period |
| `subscriptions.execute_test_billing_cycle(uuid)` | `subscriptions.test_bill(uuid)` → `TestBill` | `POST /subscriptions/:uuid/test-bill`; `bill_uuid` (`sub-hist@…`), `stage`, `outcome`; `409 payment_not_due` before `next_billing_at`, `400 test_mode_only` for a live one |
| — | `subscriptions.list(…)` / `iterate(…)`, `subscriptions.update(uuid, metadata=…)` (merged), `subscriptions.get_bill(bill_uuid)` (`GET /bills/:uuid`) | new |
| `pay_as_you_go.*` | removed | the API has no pay-as-you-go routes |

### Refunds

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `refunds.get_all()` | `refunds.list(status=[RefundStatus.PENDING])` / `refunds.iterate(…)` | `GET /refunds`, paginated; from the organization's space the members' are included by default (`include_members=False` leaves them out) |
| `refunds.get_all_inactive(limit, cursor)` | `refunds.list(status=[RefundStatus.APPROVED, RefundStatus.REJECTED], limit=…, cursor=…)` / `iterate(…)` | one list, filtered by `status` (a list, up to 5) |
| `refunds.get_by_transaction(uuid)` | `refunds.list(tx_uuid=uuid)` | or `payment.refund` / `bill.refund` (a `RefundSummary`) |
| — | `refunds.get(refund_uuid)` | new: `GET /refunds/:uuid` |

### Customers and products

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `customers.create(CreateCustomerDto(name=…, …))` | `customers.create(first_name=…, email=…, last_name=…, phone_number=…, address=…, reference=…, metadata=…)` | `POST /customers`; `name` → `first_name` |
| `customers.get(uuid)`, `customers.delete(uuid)` | same names | `delete` returns `None` (`204`) |
| `customers.get_by_reference(reference)` | `customers.get_by_reference(reference)` | runs `GET /customers?reference=`; a `NotFoundError` when none |
| `customers.get_by_email(email)` | `customers.list(email=email)` | removed: an email may match several customers |
| `customers.update(uuid, UpdateCustomerDto(...))` | `customers.update(uuid, first_name=…, email=…, last_name=…, phone_number=…, address=…, metadata=…)` | `PATCH`; `""` (or `None`) **clears** `last_name`, `phone_number`, `address`; `metadata` is merged |
| `customers.get_all(limit, cursor)` | `customers.list(limit=…, cursor=…, email=…, reference=…, verified=…)` / `iterate(…)` | |
| `products.create(CreateProductDto(price=…, …))` | `products.create(name=…, price_usd="12.50", description=…, reference=…, subscription=SubscriptionTermsParams(…), metadata=…)` | `POST /products`; `price` → `price_usd` (a string) |
| `products.get(product_id: int)` | `products.get(uuid: str)` | `GET /products/:uuid` |
| `products.get_all()` | `products.list(limit=…, cursor=…, include_hidden=…, subscription=…, reference=…)` / `iterate(…)` | paginated now |
| `products.get_by_reference(reference)` | `products.get_by_reference(reference)` | runs `GET /products?reference=` (hidden ones included); a `NotFoundError` when none |
| `products.update(product_id, UpdateProductDto(...))` | `products.update(uuid, name=…, description=…, price_usd=…, is_active=…, subscription=…, remove_subscription=…, metadata=…)` | `PATCH`; `metadata` merged |
| `products.delete(product_id)` → `SuccessResponse` | `products.delete(uuid)` → `None` | `204` |

### Users, claims and API keys (→ § 7)

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `users.create(CreateUserDto(...))` | `invitations.create(email=…, hold_funds=…, organization_fee_percent=…, redirect_url=…)` | not a rename: the person exists once they accept (`member.joined`); `hold_funds` is required |
| `users.get_all()` | `members.list(…)` / `members.iterate(…)` | |
| `users.get()` (the key's user) | `client.me()` | what the key is: its role, space and mode |
| `users.get_by_id(user_id)` | `members.get(user_uuid)` | |
| `users.get_by_email(email)` | removed | iterate `members` and match `member.email` |
| `users.update(user_id, UpdateUserDto(organization_fee_bps=…))` | `members.update(user_uuid, organization_fee_percent="2.5")` | `PATCH`; only the organization fee (a required string): names and emails are the person's own |
| `users.delete(user_id)` | `members.remove(user_uuid)` → `None` | ends the membership (`204`; `409 held_funds_pending` while you hold their funds) |
| `claim.create_request(user_id)`, `claim.get_request(user_id)` | `invitations.create`, `invitations.list` | the invitation link replaces the claim link |
| `claim.get_funds()` | `members.list_held_funds()` (a `list[MemberHeldFunds]`), `members.get_held_funds(user_uuid)`, `members.get_own_held_funds()` (`GET /held-funds`) | |
| `claim.trigger_test_claim_funds(user_id)` | removed | release held funds in the dashboard; `members.trust(user_uuid)` pays new payments directly |
| `api_keys.get_all()`, `api_keys.get_for_user(user_id)` | removed | keys are managed in the dashboard; `client.me()` describes the current one |
| — | `invitations.revoke(uuid)` → `None` (`204`), `invitations.iterate`, `members.trust` | new |

### Wallets, accounting, currencies

| 2.x | 3.0.0 | Notes |
|---|---|---|
| — | `wallets.list(with_balances=…)`, `wallets.list_for_member(user_uuid)` (`GET /members/:userUuid/wallets`), `wallets.list_accepted_currencies(user_uuid=…)` (`GET /wallets/accepted-currencies`) | new; each returns a `list` |
| `accounting.export(from_date, to_date, "json")` | `accounting.export_json(from_date, to_date)` → `list[AccountingEvent]` | dates `YYYY-MM-DD` (or `datetime.date`); the API allows 92 days at most, both included (`export_json_range` for more) |
| `accounting.export(from_date, to_date, "csv")` | `accounting.export_csv(from_date, to_date)` → `str` | |
| — | `accounting.export_json_range`, `export_csv_range` | any range, in windows of at most 92 days |
| `currencies.get_all_available(test=False)` | `currencies.list(test=False)` | `GET /currencies`, a `list` |
| `currencies.get_all_main(test=False)` | `currencies.list(test=False, main=True)` | |
| — | `currencies.get(id)` | new: `GET /currencies/:id` |

### Webhooks (→ § 11)

| 2.x | 3.0.0 | Notes |
|---|---|---|
| `verify_webhook_signature(…)`, `client.webhooks.verify(payload, signature, timestamp)` | `webhooks.verify(raw_body, signature_header, secret)` (also `client.webhooks.verify`) | returns `None` or raises `WebhookSignatureError` (`reason`) |
| — | `client.webhooks.verify_remote(endpoint_uuid, raw_body, signature_header)` | the API checks it with the endpoint's current secret; `None` = valid |
| — | `webhooks.construct_event(raw_body, header, secret)`, `webhooks.parse_event(raw_body)`, `webhooks.WebhookRouter(secret)` | verify and parse into a typed event; the router dispatches it |
| `compute_webhook_signature`, `canonical_json` | removed | the signature covers the raw body; `webhooks.sign(raw_body, secret)` builds a header for tests |
| `extract_webhook_headers`, `client.webhooks.get_signature_header()` / `get_timestamp_header()` / `get_webhook_id_header()` | `webhooks.SIGNATURE_HEADER` (`QBitFlow-Signature`), `EVENT_ID_HEADER`, `EVENT_TYPE_HEADER`, `WEBHOOK_VERSION_HEADER` | |
| `TEST_WEBHOOK_ID` | `EventType.WEBHOOK_TEST` | the dashboard's test is a `webhook.test` event |
| parsing the payload yourself (`SessionWebhookResponse`…) | a typed event (`PaymentCompletedEvent`, …) | § 11 |
| — | `client.webhooks.endpoints.*` (`list` / `iterate` paginated, `create`, `get`, `update` (PATCH), `delete`), `client.webhooks.events.*` (`list`, `iterate`, `get`) | new: endpoints and the event log |

## 6. Ids are UUID strings

Every id but a currency's is a UUID string now, and no resource names its organization:

- **Products:** `Product.id: int` → `Product.uuid: str`; `product_id` → `product_uuid` on
  payments, bills, subscriptions, sessions and the accounting export; checkouts take
  `product_uuid`.
- **Members and `On-Behalf-Of`:** a member is named by their **user UUID** (`Member.user_uuid`).
  `on_behalf_of(123)` becomes `client.on_behalf_of("0192f1c2-…")`; a numeric value is refused.
  `user_id` → `user_uuid` everywhere (`None` for the organization's own rows).
- **`organization_id` is gone** from every model; `client.me().space.organization_uuid` names the
  organization.
- **Transactions** keep their prefixed ids (`pay@…`, `sub@…`, `sub-hist@…`, `refund@…`,
  `transfer@…`, `release@…`), as opaque strings; every route also takes the bare UUID. `tx_id` →
  `tx_uuid`, `transaction_hash` → `tx_hash`.
- Currencies keep numeric ids (`int`).

**Map the numeric ids you stored**: walk your products
(`client.products.iterate(include_hidden=True)`, in each space you act in) and match them on
`reference`, which did not change, and your members (`client.members.iterate()`, in each mode) on
`email`; store the UUIDs next to your old ids. The SDK does not expose the API's temporary
`legacyId` field.

## 7. Users and claims become invitations, members and the trust layer

v1 provisioned sellers (`users.create`) and could sell for them at once, the seller claiming the
account and its funds later. **v2 creates no accounts: a seller sells only once they accepted an
invitation.**

1. `client.invitations.create(email=…, hold_funds=…, organization_fee_percent=…, redirect_url=…)`
   returns a `CreatedInvitation`: the invitation's fields and its `link` (also emailed).
2. Wait for the `member.joined` webhook and store its `user_uuid` (match `invitation_uuid`).
3. Sell with `client.on_behalf_of(user_uuid)`.

`hold_funds=True` (the v1 "claim" model; always sent) holds the seller's payments in your wallet
until you trust them: `members.get_held_funds` shows what you owe, `members.trust` makes new
payments go to the seller directly, and the release of what is held is signed in the dashboard.
Sellers v1 provisioned are already members; those who never claimed are members whose funds you
hold (`trusted_at is None`). The [README](README.md#marketplaces) walks the flow.

## 8. Models

**Money is a decimal string, never a float**, in requests and in responses: USD amounts
(`price_usd="4.99"`, `amount_usd`, `paid_usd`, `total_usd`), token amounts in the token's units
(`amount == "10"` for 10 USDC, next to `amount_min_units == "10000000"` and the `currency` object)
and fee rates in **percent** (`fee_bps=150` → `fee_percent == "1.5"`, `organization_fee_bps=250` →
`organization_fee_percent="2.5"`, `refund_percent == "50"`). The money inputs take a `str` or a
`decimal.Decimal` (sent as `str(value)`); a `float` or an `int` is a `ValidationError` (the API
answers 400 to a JSON number, and a float cannot carry `0.1` exactly). Inputs are validated before
sending (at most 2 decimals, no sign or exponent). Compute with `decimal.Decimal`, or
`format_amount` / `parse_amount` for token amounts:

```python
from decimal import Decimal

product = client.products.create(name="T-shirt", price_usd=Decimal("4.99"))  # sent as "4.99"
total = Decimal(product.price_usd) * 3  # never float(product.price_usd)
```

Models are pydantic v2 models with snake_case attributes and **explicit wire aliases**:
`model.to_dict()` (or `model_dump(by_alias=True)`) writes camelCase keys exactly as the API does
(2.x's alias generator wrote `customerUUID`). A field the API always sends is never `None` (an
absent value decodes to `""`, `0`, `False`, `[]`, `{}` or `ZERO_TIME`); a field the API leaves out
without a value is `Optional[...]` (`None` when absent). A value of the wrong JSON type is a
`ServerError`, never a silent coercion.

| 2.x (`qbitflow.dto…`) | 3.0.0 (`qbitflow`) | What changed |
|---|---|---|
| `LinkResponse` | `CreatedCheckoutSession` | `link`, `uuid`, `expires_at` (always set) |
| `TransactionStatus` | `CheckoutSessionStatus` | `status` is a `CheckoutSessionStatusValue`; + `uuid`, `tx_hash`, `message`, `last_attempt`, `expires_at`; `settlement_details` removed |
| `OneTimePaymentSession`, `SubscriptionSession`, `PaygSubscriptionSession`, `AnySession`, `BaseSession`, `SessionWebhookResponse`, `StatusLinkResponse` | removed | `PaymentSessionData` / `SubscriptionSessionData` in `checkout.expired` (`price_usd`, `fees`, `amount_usd`, `available_currencies`, `metadata`) |
| `CreatePaymentSessionDto`, `CreateSubscriptionSessionDto`, `CreateCustomerDto`, `UpdateCustomerDto`, `CreateProductDto`, `UpdateProductDto`, `CreateUserDto`, `UpdateUserDto` | removed | keyword arguments of the methods; `SubscriptionTermsParams` for a product's terms, `CheckoutFees` / `FeeItem` for a checkout's fees |
| `Payment` | `Payment` | `amount` is now the **token amount** (a string), its USD value `amount_usd`; `transaction_hash` → `tx_hash`; `name` / `description` → `product_name` / `product_description`; `product_id` → `product_uuid`; `currency_id` → the `currency` object (always set); `metadata` (the fee split) → `settlement`, and `metadata` is now your checkout's `dict[str, str]`; `user_id` → `user_uuid`; `organization_id` removed; + `price_usd`, `fees`, `chain`, `explorer_url`, `customer_reference`, `customer`, `refund`, `refundable`, `paid`, `paid_min_units`, `paid_usd`, `confirmed_at` |
| `CombinedPaymentItem` | `Transaction` (`transactions.list`) | `source` → `type` (`TransactionKind`: `payment`, `bill`); the `Payment` renames; + `price_usd`, `fees`, `period_start`, `period_end`, `settlement`, `paid*`, `metadata`, `subscription_reference` |
| `Subscription` | `Subscription` | `subscription_status` → `status`; `stopped` → the status `stopped`; `frequency` (seconds) → `Duration`; `product_id` → `product_uuid`; `last_billing_date` → `last_billed_at`, `next_billing_date` → `next_billing_at`, `minimum_cancellation_date` → `cancellable_at` (all `Optional[datetime]`); `allowance` (min units) and `max_amount_per_period` → `allowance: Optional[Allowance]` (`amount`, `amount_min_units`, `amount_usd`, `remaining_periods`, `max_per_period`, `max_per_period_min_units`); `currency_id` → `currency`; `from_`, `product_uuid`, `subscription_hash` `None` when unknown; + `current_period_end`, `action_required`, `price_usd`, `fees`, `cancelled_at`, `cancellation_reason`, `metadata`, `management_page_link`, `customer_reference`, `customer`, `dunning` |
| `PayAsYouGoSubscription` | removed | |
| `SubscriptionHistory` | `Bill` | the `Payment` renames (no `metadata`, no `price_usd`: read the subscription's); + `settlement`, `period_start`, `period_end`, `subscription_uuid` |
| `RefundEntry` | `Refund` | `tx_id` → `tx_uuid`; amounts as strings; `metadata` → `settlement` (a `TransferSettlement`, once approved); `currency_id` → `currency`; + `initiated_by`, `refund_percent`, `paid`, `paid_min_units`, `paid_usd`, `amount`, `amount_min_units`, `amount_usd`, `held`, `chain`, `explorer_url`, `approval`, `customer` |
| `Customer` | `Customer` | `name` → `first_name`; `last_name` optional; `organization_id` removed, `user_id` → `user_uuid`; + `verified`, `metadata` |
| `Product` | `Product` | `id: int` → `uuid: str`; `price` (a float) → `price_usd` (a string); `description` optional; + `subscription` (terms), `payment_link`, `metadata` |
| `User` | `Member` (or `Me`) | `id` → `user_uuid`; `name` → `first_name`; `organization_fee_bps` → `organization_fee_percent` (a string); `claimed_at` → `trusted_at`; + `joined_at`, `accepted_currencies` (`list[Currency]`), `space_uuid` |
| — | `HeldFunds`, `LedgerEntry`, `MemberHeldFunds` | `total_usd`; each line's `amount_usd`, `settlement`, `currency`, `owed`, `owed_min_units`, `owed_usd` |
| — | `Invitation`, `CreatedInvitation` | `hold_funds`, `organization_fee_percent` (a string); `CreatedInvitation` is flat: the invitation's fields and `link` |
| — | `Wallet`, `TokenWallet`, `Balance` | `Wallet.address`, `Wallet.currency`; `TokenWallet.currency`; `Balance` = its `currency` + `amount`, `amount_min_units`, `amount_usd` (a `TokenAmount`) |
| `UserRole` | `Role` (+ `OWNER`, `HANDLE`) | |
| `AccountingEvent` | `AccountingEvent` | `payment_id` → `tx_uuid`; `related_payment_id` → `related_tx_uuid`; the payment references → `reference` / `related_reference`; `product_id` → `product_uuid`; `token_symbol` → `currency` (always set, a native currency's too); every amount, USD amount and rate is a decimal string, the amounts in the currency's units (`"7.5"`, not `"7500000"`) with a `…_min_units` twin; a fee that doesn't apply is `None`, never `"0"`; network fees are never part of `net_amount`; `type` and `chain` are enums; fields in the CSV's column order; + `user_uuid`, `referral_fee*`, `currency_price_usd`, `network_fees_paid_by` (`NetworkFeesPayer`), `network_fees_currency`, `network_fees_currency_decimals`, `network_fees_currency_price_usd` |
| `PaymentMetadata` | `Settlement` | `fee_bps` → `fee_percent` (a string); `tx_amounts` → `split` (`platform`, `organization`, `referral`, `merchant`, `network_fee`, each a `TokenAmount`; `platform` no longer includes the referrer's share); the transaction's block and fees → `transaction` (`SettlementTransaction`: `block_number`, `block_time`, `gas_used`, `fee`, `l1_fee`, `native_price_usd`). `TxMetadata`, `BlockData`, `NetworkFees`, `TxAmounts*` are gone |
| `OrganizationFee(organization_id, organization, fee_bps)` | `OrganizationFee(address, fee_percent)` | |
| `ReferralFee(referral_id, referrer, fee_bps, deadline)` | `ReferralFee(address, fee_percent, deadline)` | |
| `Currency` | `Currency` | + `code` (`BASE:USDC`), `chain`; `address` `None` on a native coin; no nested `main_currency` (`main_currency_id` stays) |
| `Duration` | `Duration` | `Duration(value=0)` means none; the unit is a `DurationUnit` |
| `CursorData[T, str]` | `Page[T]` | `items`, `has_more` (a field), `next_cursor` (`None` on the last page) |
| `ApiKey`, `ClaimRequest`, `Organization`, `CreateClaimRequestResponse`, `ClaimFund`, `StatusResponse`, `StatusResponseError`, `TransactionShortType`, `SuccessResponse` | removed | |

**Metadata** is new: your own `dict[str, str]` on products, customers, checkouts (copied onto the
payment or subscription and into the webhooks) and subscriptions (`subscriptions.update`). Pass
it as `metadata={"orderId": "order-1042"}`: at most 50 keys of 1 to 40 characters among
`A-Z a-z 0-9 _ - . :`, values of at most 500 characters without control or bidirectional
characters; an update merges it (a key set to `""` deletes it). Never put secrets or personal
data in it.

## 9. Enum values and statuses

Enum values are lowerCamelCase on the wire, and every enum keeps unknown values as raw strings
(the members are `StrEnum`s: compare with `==`).

**Subscription statuses**

| 2.x `SubscriptionStatus` | 3.0.0 |
|---|---|
| `ACTIVE` (`active`) | `SubscriptionStatus.ACTIVE` |
| `PAST_DUE` (`past_due`) | `SubscriptionStatus.PAST_DUE` (`pastDue`) |
| `TRIAL` (`trial`) | `SubscriptionStatus.TRIAL` |
| `TRIAL_EXPIRED` (`trial_expired`) | `SubscriptionStatus.TRIAL_EXPIRED` (`trialExpired`) |
| `CANCELLED` (`cancelled`) | `SubscriptionStatus.CANCELLED` |
| `LOW_ON_FUNDS` (`low_on_funds`) | no status: `action_required == ActionRequired.TOP_UP_ALLOWANCE` |
| `PENDING` (`pending`) | no status: `action_required == ActionRequired.RAISE_MAXIMUM` |
| `subscription.stopped is True` | `SubscriptionStatus.STOPPED` (`stopped`): cancelled at `next_billing_at` |
| — | `SubscriptionStatus.PAUSED` (`paused`): paused by the customer |

**Grant access while `now < current_period_end`** (`subscription.has_access()`), whatever the
status: a check like `status == ACTIVE` cuts off paying customers (`stopped`, `paused`) and keeps
serving `pastDue` ones.

**Checkout statuses**: 2.x's seven `TransactionStatusValue`s become four
`CheckoutSessionStatusValue`s: `CREATED`, `WAITING_CONFIRMATION`, `COMPLETED`, `EXPIRED`. `PENDING`,
`FAILED` and `CANCELLED` are gone: **a failed attempt is `created` with `last_attempt` set** (its
`code` says why). It is never final: the customer may still pay until the session expires, so
never cancel an order on it.

**Other values**

| 2.x | 3.0.0 |
|---|---|
| `TransactionType.ONE_TIME_PAYMENT` | `TransactionType.PAYMENT` (`payment`) |
| `TransactionType.EXECUTE_SUBSCRIPTION_PAYMENT` | `TransactionType.EXECUTE_SUBSCRIPTION` |
| `TransactionType.CREATE_PAYG_SUBSCRIPTION` / `CANCEL_PAYG_SUBSCRIPTION` (`createPAYGSubscription`…) | same names, values `createPaygSubscription` / `cancelPaygSubscription` |
| — | `TransactionType.FORCE_CANCEL_SUBSCRIPTION`, `TransactionType.RELEASE_HELD_FUNDS` |
| `RefundStatus` (`dto.transaction`) | `RefundStatus`: `PENDING` (a customer's request), `APPROVED`, `REJECTED`; `FAILED` is declared, never set |
| `CombinedPaymentItem.source` `"subscription_history"` | `Transaction.type` `TransactionKind.BILL` (`bill`) |
| `AccountingEvent.type` (a `str`) | `AccountingEventType` (`subscription_history` → `AccountingEventType.BILL`, `bill`) |
| — | `LedgerEntryType` (held-funds lines): `LedgerEntryType.PAYMENT`, `LedgerEntryType.REFUND` (a held seller sells no subscription: no bill line) |

## 10. Errors

| 2.x (`qbitflow.exceptions`) | 3.0.0 (`qbitflow`) |
|---|---|
| `QBitFlowError` | `QBitFlowError` (the base of every SDK error) |
| `APIError` | `ApiError` (the base of every error below, and any other HTTP error) |
| `ValidationError` (every 400, 422, and pydantic DTO failures) | `ValidationError`: 400 `validation_failed` and client-side checks (`status` None) |
| `InvalidRequestError` | `BadRequestError` (other 400s), or `ValidationError` |
| `AuthenticationError` | `AuthenticationError` (401) |
| — | `PermissionDeniedError` (403) |
| `NotFoundException` | `NotFoundError` (404, and `get_by_reference` with no match) |
| — | `ConflictError` (409), `GoneError` (410), `IdempotencyError` (422 `idempotency_key_reused`) |
| `RateLimitError` | `RateLimitError` (429: `retry_after`, `limit`, `period_seconds`) |
| — | `ServerError` (5xx, unexpected 3xx, a 2xx that is not the expected JSON) |
| `NetworkError` | `NetworkError` (no response; the cause is chained) |
| — | `WebhookSignatureError` (`reason`) |

- Every error carries `status`, `code`, `message`, `details`, `request_id`, `field_errors`
  (`FieldError(field, message)`) and `raw_body`.
- **Field errors work now.** 2.x read a validation error's fields from the wrong key (a top-level
  `errors` list), so they came back empty. 3.0.0 reads `details.errors`: `field_errors` names
  each failing input by its wire name, dotted when nested (`frequency.unit`).
- **Branch on `code`**, never on `message`: `unique_violation` (`details["field"]`),
  `merchant_not_ready`, `tx_already_sent`, `policy_disabled`…
- **`get_by_reference`** runs the list's `?reference=` filter: no match is a `NotFoundError`
  (status 404, code `not_found`), like an unknown UUID.
- Every error carries the request's `request_id`: log it, and quote it to support.
- `qbitflow.is_retryable(error)` says whether an error is transient.

## 11. Webhooks

The webhook scheme is new; 2.x verification code does not carry over.

| | 2.x | 3.0.0 |
|---|---|---|
| Header | `X-Webhook-Signature-256: sha256=<hex>`, `X-Webhook-Timestamp`, `X-Webhook-Id` | `QBitFlow-Signature: t=<unix>,v1=<hex>[,v1=<hex>]`, `QBitFlow-Event-Id`, `QBitFlow-Event-Type` |
| Signed content | `timestamp.` + the body re-encoded as canonical JSON | `t.` + the **raw body**, exactly as received |
| Rotation | one secret | two `v1=` for 24 hours after a rotation; either secret verifies |
| Body | `SessionWebhookResponse` or a subscription status transition | the event envelope `{id, type, version, createdAt, test, userUuid, data}` |
| Result | `verify(...)` returned `True` / `False` | `verify(...)` returns `None` or raises `WebhookSignatureError` (`reason`) |
| Dashboard test | `X-Webhook-Id: test-webhook-id` | a `webhook.test` event |

- **Read the raw body and never re-serialize it** before verifying (FastAPI: `await
  request.body()`; Flask: `request.get_data()`; Django: `request.body`). The router's adapters
  (`flask_view`, `django_view`, `fastapi_endpoint`) do it for you.
- **v2 only.** Every endpoint receives the v2 envelope (v1 is retired and every endpoint was moved
  to v2); a body of another version is a `ValidationError` from `parse_event`.
- **Event types** replace the two 2.x payloads: v1's transaction webhook becomes
  `payment.completed` / `subscription.created`, its subscription webhook `subscription.billed` /
  `subscription.statusChanged`, plus 11 new types (`checkout.expired`, `refund.requested`,
  `refund.approved`, `refund.rejected`, `member.joined`, …). Each parses into its own class
  (`PaymentCompletedEvent`, `RefundApprovedEvent`, …) with a typed `data`; narrow with
  `isinstance`, or register a handler on a `webhooks.WebhookRouter`
  (`@router.on("refund.approved")`).
- `subscription.billed`'s data is a `SubscriptionBilled` with `bill` (the bill paid) and
  `subscription` (as it leaves it): read `data.subscription.reference` / `.status`.
  `subscription.created`'s data is the `Subscription`. `subscription.upcomingBill` has
  `billing_at` and a string `amount_usd`. Money in event data is decimal strings, as in the API's
  answers.
- Deliveries are at least once: deduplicate on `event.id`, and answer 2xx to the types you ignore.
- Endpoints are created per space with `client.webhooks.endpoints.create`, whose answer carries
  the `whsec_…` secret once.

## 12. Pagination

`get_all(limit, cursor)` becomes `list(limit=…, cursor=…, filters…)`, returning a `Page[T]`
(`items`, `has_more`, `next_cursor`). While `page.has_more`, pass `page.next_cursor` back as
`cursor`, verbatim (it is opaque). Every paginated list also has an iterator that walks every page
lazily, and stops after the page whose `has_more` is false. The short bounded lists
(`currencies.list`, `wallets.*`, `members.list_held_funds`, `accounting.export_json`) return a
`list`:

```python
for sub in client.subscriptions.iterate(limit=100):
    print(sub.uuid, sub.status)
```

## 13. Before and after: common tasks

### Create the client

```python
# 2.x
# client = QBitFlow(api_key="sk_…", timeout=60, max_retries=5)
# seller = client.one_time_payments.on_behalf_of(42)

# 3.0.0
import os

from qbitflow import QBitFlow

client = QBitFlow(os.environ["QBITFLOW_API_KEY"], timeout=60, max_retries=5)
me = client.me()  # check the key and its mode at start-up
seller = client.on_behalf_of("0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f")  # a member's user UUID
```

### Open a payment checkout and read its outcome

```python
# 2.x
# link = client.one_time_payments.create_session(product_id=1, success_url="https://…")
# status = client.transaction_status.get(link.uuid, TransactionType.ONE_TIME_PAYMENT)
# if status.status == TransactionStatusValue.FAILED: ...

# 3.0.0
from qbitflow import CheckoutSessionStatusValue

session = client.checkout_sessions.create_payment(
    product_uuid="0192f1c2-1111-7c4d-9e5f-6a7b8c9d0e1f",
    reference="order-1042",
    success_url="https://shop.example.com/thanks?session={{UUID}}",
)
status = client.checkout_sessions.get(session.uuid)
if status.status == CheckoutSessionStatusValue.COMPLETED:
    payment = client.payments.get(session.uuid)  # the payment has the session's id
    print(payment.amount_usd, payment.tx_hash)
elif status.last_attempt is not None:
    print("an attempt failed, not final:", status.last_attempt.code)
```

### Sell an inline product with a price

```python
# 2.x
# client.one_time_payments.create_session(product_name="T-shirt", price=4.99)

# 3.0.0
session = client.checkout_sessions.create_payment(
    product_name="T-shirt",
    price_usd="4.99",  # a decimal string (or a Decimal), never a float
    metadata={"orderId": "order-1043"},  # yours, copied onto the payment and its webhooks
)
```

### List a seller's payments

```python
# 2.x
# page = client.one_time_payments.on_behalf_of(42).get_all(limit=50)

# 3.0.0
from datetime import datetime, timedelta, timezone

seller = client.on_behalf_of("0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f")  # Member.user_uuid
for payment in seller.payments.iterate(
    created_after=datetime.now(timezone.utc) - timedelta(days=30),
    limit=50,
):
    print(payment.uuid, payment.amount_usd, "USD", payment.settlement.fee_percent)
```

### Find a customer by email

```python
# 2.x
# customer = client.customers.get_by_email("ada@example.com")

# 3.0.0: an email may match several customers
for customer in client.customers.iterate(email="ada@example.com"):
    print(customer.uuid, customer.first_name, customer.verified)
```

### Cancel a subscription

```python
# 2.x
# client.subscriptions.force_cancel("sub@…")

# 3.0.0
result = client.subscriptions.cancel("sub@0192f1c2-3333-7c4d-9e5f-6a7b8c9d0e1f", immediate=False)
print("confirming on-chain" if result.pending else result.subscription.status)
```

### Receive a webhook

```python
# 2.x
# ok = client.webhooks.verify(payload, signature, timestamp)  # canonical JSON
# data = SessionWebhookResponse.model_validate_json(payload)

# 3.0.0
import os

from qbitflow import Event, PaymentCompleted, Refund, webhooks

router = webhooks.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])


@router.on("payment.completed")
def fulfil(data: PaymentCompleted, event: Event) -> None:
    print("fulfil", data.reference, "once for", event.id)  # deduplicate on event.id


@router.on("refund.approved")  # was refund.completed
def refunded(data: Refund, event: Event) -> None:
    print("reverse", data.tx_uuid, data.refund_percent, "%")


# In your framework: router.flask_view(), router.django_view(), router.fastapi_endpoint(),
# or result = router.handle(raw_body, signature_header) -> WebhookResult(status, event, error).
```

Or, lower level, `webhooks.construct_event(raw_body, signature_header, secret)` and
`isinstance(event, PaymentCompletedEvent)`.

### Handle an error

```python
# 2.x
# except NotFoundException: ...
# except ValidationError as e: print(e)  # field errors empty

# 3.0.0
from qbitflow import ApiError, NotFoundError, ValidationError

try:
    client.customers.create(first_name="Ada", email="ada@example.com", reference="crm-42")
except ValidationError as exc:
    for f in exc.field_errors:
        print(f.field, f.message)
except NotFoundError:
    print("not found")
except ApiError as exc:
    print(exc.status, exc.code, exc.request_id)
```

## Names from the unreleased 2.5.0

2.5.0 was prepared but never published. If you tried it from source: `ForbiddenException` →
`PermissionDeniedError`, `NotFoundException` → `NotFoundError`, `ConflictError` and `ServerError`
keep their names, `GO_ZERO_TIME` → `ZERO_TIME`, `parse_session_webhook` /
`parse_subscription_webhook` / `WebhookHeaders` → `webhooks.parse_event` (v2 events), and the
deprecated `claim` alias and the 2.x services it kept are gone.

## Names from the 3.0.0 previews

3.0.0 was rebuilt against API v2's final contract before its release; if you tried a preview
build, these names changed: `checkout_sessions.get_status` → `get`; `payments.list_combined` /
`iterate_combined` → `transactions.list` / `iterate` (`CombinedPayment` → `Transaction`, `source`
→ `type`, `CombinedPaymentSource` → `TransactionKind`); `subscriptions.execute_test_billing` →
`test_bill` (`BillingState` → `TestBill`); `refunds.initiate` is removed (refunds are read only:
a merchant's refund is sent from the dashboard); `refunds.list_inactive` / `iterate_inactive` →
`refunds.list` / `iterate` with `status`;
`wallets.list_supported_currencies` → `list_accepted_currencies`; `currencies.list_available` /
`list_main` → `currencies.list(main=…)`; `CheckoutSession` → `CreatedCheckoutSession`;
`InvitationCreated` → `CreatedInvitation` (flat); `MemberHeldFundsSummary` → `MemberHeldFunds`;
`invitations.create(trust_layer=…)` → `hold_funds=…` (required); `PaymentMetadata` & co. →
`Settlement`; the `Page.has_more` property → a field; `EventType.REFUND_COMPLETED` /
`REFUND_DENIED` (`RefundCompletedEvent` / `RefundDeniedEvent`) → `EventType.REFUND_APPROVED` /
`REFUND_REJECTED` (`RefundApprovedEvent` / `RefundRejectedEvent`); `SubscriptionCreated` →
`Subscription`; `customers.get_by_email` and `subscriptions.get_public_history` are removed;
`invitations.revoke` returns `None`; money, percents and fee amounts are strings (`price=4.99` →
`price_usd="4.99"`, a float refused), and the routes moved off `/transaction/…`.
