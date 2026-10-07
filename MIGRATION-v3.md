# Migrating from 2.x to 3.0.0

3.0.0 is the Python SDK for **QBitFlow API v2**. API v2 reorganises the platform around spaces
(an organization's, and one per member), invites people instead of provisioning them, names every
resource by a UUID and signs webhooks with a new scheme. The SDK follows: a new client, services
named after the API's areas, keyword-only arguments, and new names for most methods and models.

API v1 keeps running next to v2, **against the same data**, for some weeks after v2 ships: your
2.x integration keeps working meanwhile, so you can move one part at a time. 2.x talks to `/v1`
only; 3.0.0 talks to `/v2` only.

This guide maps everything 2.1.0 exposed (the last 2.x release) to 3.0.0. The
[README](README.md) documents 3.0.0 in full; [CHANGELOG.md](CHANGELOG.md) lists every change.

## Checklist

1. [Install and imports](#1-install-and-imports): `pip install -U qbitflow`, import from `qbitflow`.
2. [Base URL and API keys](#2-base-url-and-api-keys): `/v2`; rotate pre-v2 keys.
3. [The client](#3-the-client): keyword-only options, `on_behalf_of(user_uuid)`, `me()`, `close()`.
4. [Keyword arguments and request options](#4-keyword-arguments-and-request-options).
5. [Method map](#5-method-map): every 2.x method and its replacement.
6. [Ids are UUID strings](#6-ids-are-uuid-strings): products, members, `On-Behalf-Of`.
7. [Users and claims become invitations, members and the trust layer](#7-users-and-claims-become-invitations-members-and-the-trust-layer).
8. [Models](#8-models): renamed models and fields, fees as percents.
9. [Enum values and statuses](#9-enum-values-and-statuses): subscription and checkout statuses.
10. [Errors](#10-errors): one class per status, field errors that work.
11. [Webhooks](#11-webhooks): `QBitFlow-Signature` over the raw body, typed events, v2 endpoints.
12. [Pagination](#12-pagination): `Page` and iterators.
13. [Before and after](#13-before-and-after-five-common-tasks): five common tasks.

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
- API v2 issues keys shaped `sk_<uuid>_<test|live>_<secret>`. **Keys issued before** (`sk_<digits>_…`)
  **still authenticate**: rotate them in the dashboard when you move to v2. Treat a key as opaque.
- `QBitFlow(...)` refuses a blank key, or one not starting with `sk_`, with a `ValidationError`
  (2.x raised `ValueError` for a blank key, and sent any other). It sends nothing: call
  `client.me()` to check the key online, and assert its mode (`me.space.test`) at start-up.
- A key belongs to one space and one mode. A removed member's keys answer 401.

## 3. The client

| 2.x | 3.0.0 |
|---|---|
| `QBitFlow(api_key, timeout=None, max_retries=None)` | `QBitFlow(api_key, *, base_url=None, timeout=None, max_retries=None, on_behalf_of=None, http_client=None)` |
| `timeout` (whole request) | `timeout`: seconds per attempt (default 30) |
| `max_retries` (GET only) | `max_retries`: reads and the 7 creates (default 3; `0` disables) |
| `client.one_time_payments.on_behalf_of(user_id)` (per service) | `client.on_behalf_of(user_uuid)`: a whole client acting in the member's space |
| `client.api_key` | not exposed |
| — | `client.me()`, `client.close()`, `with QBitFlow(...) as client:` |

## 4. Keyword arguments and request options

Every method takes its path id (a UUID, a transaction id, a reference…) positionally and
**everything else as keyword-only arguments**; there are no `Create…Dto` / `Update…Dto` objects
any more. The last argument of every method is `options=RequestOptions(...)`:

```python
from qbitflow import RequestOptions

member_uuid = "0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f"
products = client.products.list(
    include_hidden=True,
    options=RequestOptions(on_behalf_of=member_uuid, request_id="job-42"),
)
```

| `RequestOptions` field | |
|---|---|
| `on_behalf_of` | act in a member's space for this call (overrides the client's; `""` = the organization) |
| `idempotency_key` | the 7 creates only: your own `Idempotency-Key` |
| `request_id` | sent as `X-Request-Id`, echoed in errors |

Arguments are checked before anything is sent: a wrong value or type is a `ValidationError`
naming the wire field. The update methods change only the arguments you pass; the clearable
fields (`phone_number`, `address`, `description`) default to `NOT_GIVEN`, and `""` or `None`
clears them.

## 5. Method map

### Checkout sessions and status (2.x `one_time_payments`, `subscriptions`, `transaction_status`)

| 2.x | 3.0.0 |
|---|---|
| `one_time_payments.create_session(product_id=…, …)` | `checkout_sessions.create_payment(product_uuid=…, …)` → `CheckoutSession` |
| `subscriptions.create_session(product_id=…, frequency=…, …)` | `checkout_sessions.create_subscription(product_uuid=…, frequency=Duration(…), …)` (inline products allowed) |
| `one_time_payments.get_session(uuid)`, `subscriptions.get_session(uuid)` | removed: `checkout_sessions.get_status(uuid)`; the session's data comes in `checkout.expired` |
| `transaction_status.get(uuid, transaction_type)` | `checkout_sessions.get_status(uuid)` (the type is in the id: `pay@…`, `sub@…`) |
| `transaction_status.get_websocket_url(…)` | removed |
| — | `checkout_sessions.expire(uuid)` |

### Payments

| 2.x | 3.0.0 |
|---|---|
| `one_time_payments.get(uuid)` | `payments.get(uuid, include_members=False)` |
| `one_time_payments.get_by_reference(reference)` | `payments.get_by_reference(reference)` |
| `one_time_payments.get_all(limit, cursor)` | `payments.list(limit=…, cursor=…, filters…)` / `payments.iterate(…)` |
| `one_time_payments.get_all_combined(limit, cursor)` | `payments.list_combined(…)` / `payments.iterate_combined(…)` |
| `one_time_payments.get_customer_for_transaction(uuid)` | removed: `payment.customer` (or `customers.get(payment.customer_uuid)`) |
| — | `failures.list(…)` / `failures.iterate(…)`: the failed attempts |

### Subscriptions

| 2.x | 3.0.0 |
|---|---|
| `subscriptions.get(uuid)` | `subscriptions.get(uuid, include_members=False)` (cancelled ones too) |
| `subscriptions.get_by_reference(reference)` | `subscriptions.get_by_reference(reference)` |
| `subscriptions.get_payment_history(uuid)` | `subscriptions.list_bills(uuid)` / `iterate_bills(uuid)`, or `get_public_history(uuid)` (the customer's view) |
| `subscriptions.force_cancel(uuid)` → `SuccessResponse` | `subscriptions.cancel(uuid, immediate=True)` → `SubscriptionCancellation` (`pending` for an HTTP 202) |
| `subscriptions.execute_test_billing_cycle(uuid)` | `subscriptions.execute_test_billing(uuid)` → `BillingState` |
| — | `subscriptions.list(…)` / `iterate(…)`, `subscriptions.get_bill(bill_uuid)` |
| pay-as-you-go | removed (not part of API v2's integrator surface) |

### Refunds

| 2.x | 3.0.0 |
|---|---|
| `refunds.get_all()` | `refunds.list(include_members=…, user_uuid=…, held=…)` |
| `refunds.get_all_inactive(limit, cursor)` | `refunds.list_inactive(…)` / `iterate_inactive(…)` |
| `refunds.get_by_transaction(uuid)` | removed: `payment.refund` / `bill.refund` |
| — | `refunds.initiate(tx_uuid=…, refund_percent=…, reason=…, merchant_message=…)` |

### Customers and products

| 2.x | 3.0.0 |
|---|---|
| `customers.create(CreateCustomerDto(...))` | `customers.create(name=…, email=…, last_name=…, …)` |
| `customers.get(uuid)`, `get_by_reference`, `get_by_email` | unchanged names |
| `customers.get_all(limit, cursor)` | `customers.list(limit=…, cursor=…, email=…, verified=…)` / `iterate(…)` |
| `customers.update(uuid, UpdateCustomerDto(...))` | `customers.update(uuid, name=…, phone_number=…, …)` |
| `customers.delete(uuid)` → `SuccessResponse` | `customers.delete(uuid)` → `None` |
| `products.create(CreateProductDto(...))` | `products.create(name=…, price=…, description=…, reference=…, subscription=SubscriptionTermsParams(…))` |
| `products.get(product_id: int)` | `products.get(uuid: str)` |
| `products.get_all()` | `products.list(include_hidden=…, subscription=…)` |
| `products.get_by_reference(reference)` | unchanged |
| `products.update(product_id, UpdateProductDto(...))` | `products.update(uuid, name=…, price=…, is_active=…, subscription=…, remove_subscription=…)` |
| `products.delete(product_id)` → `SuccessResponse` | `products.delete(uuid)` → `None` |

### Users, claims and API keys (→ § 7)

| 2.x | 3.0.0 |
|---|---|
| `users.create(CreateUserDto(...))` | `invitations.create(email=…, trust_layer=…, organization_fee_percent=…, redirect_url=…)` (the person joins when they accept) |
| `users.get_all()` | `members.list()` / `members.iterate()` |
| `users.get()` (the key's user) | `client.me()` |
| `users.get_by_id(user_id)`, `users.get_by_email(email)` | `members.get(user_uuid)` |
| `users.update(user_id, UpdateUserDto(organization_fee_bps=…))` | `members.update(user_uuid, organization_fee_percent=…)` |
| `users.delete(user_id)` | `members.remove(user_uuid)` |
| `claim.get_request(user_id)`, `claim.create_request(user_id)` | removed: invitations replace claim requests |
| `claim.get_funds()` | `members.list_held_funds()`, `members.get_held_funds(user_uuid)`, `members.get_own_held_funds()` |
| `claim.trigger_test_claim_funds(user_id)` | removed: `members.trust(user_uuid)`; held funds are released from the dashboard |
| `api_keys.get_all()`, `api_keys.get_for_user(user_id)` | removed: keys are managed in the dashboard; `client.me()` describes the current key |
| — | `invitations.list(…)` / `iterate(…)`, `invitations.revoke(uuid)` |

### Wallets, accounting, currencies

| 2.x | 3.0.0 |
|---|---|
| — | `wallets.list(with_balances=…)`, `wallets.list_for_member(user_uuid)`, `wallets.list_supported_currencies(user_uuid=…)` |
| `accounting.export(from_date, to_date, "json")` | `accounting.export_json(from_date, to_date)` → `list[AccountingEvent]` |
| `accounting.export(from_date, to_date, "csv")` | `accounting.export_csv(from_date, to_date)` → `str` |
| `currencies.get_all_available(test=False)` | `currencies.list_available(test=False)` |
| `currencies.get_all_main(test=False)` | `currencies.list_main(test=False)` |
| — | `currencies.get(id)` |

### Webhooks (→ § 11)

| 2.x | 3.0.0 |
|---|---|
| `verify_webhook_signature(…)`, `client.webhooks.verify(payload, signature, timestamp)` | `webhooks.verify(raw_body, signature_header, secret)` (raises `WebhookSignatureError`; returns `None`) |
| `compute_webhook_signature`, `canonical_json` | removed: v2 signs the raw body |
| `extract_webhook_headers`, `client.webhooks.get_signature_header()` / `get_timestamp_header()` / `get_webhook_id_header()` | `webhooks.SIGNATURE_HEADER` (`QBitFlow-Signature`), `EVENT_ID_HEADER`, `EVENT_TYPE_HEADER` |
| parsing the payload yourself (`SessionWebhookResponse`…) | `webhooks.construct_event(raw_body, header, secret)` / `webhooks.parse_event(raw_body)` → a typed event |
| — | `client.webhooks.verify_remote(endpoint_uuid, raw_body, header)` |
| — | `client.webhooks.endpoints.*` (`list`, `create`, `get`, `update`, `delete`), `client.webhooks.events.*` (`list`, `iterate`, `get`) |

## 6. Ids are UUID strings

- **Products** are named by `uuid` (was the numeric `id`); `product_id` is `product_uuid` in every
  argument and model.
- **People** are named by their user UUID: `Member.user_uuid`, `Payment.user_uuid`… (was the
  numeric `user_id`). `On-Behalf-Of` takes that UUID: `client.on_behalf_of(user_uuid)`.
- `organization_id` is gone from every model: a request's space comes from its key (and
  `On-Behalf-Of`).
- Transactions keep prefixed ids, passed back verbatim: `pay@…` (a payment, also its checkout
  session), `sub@…` (a subscription), `sub-hist@…` (a bill), `refund@…`.
- Currencies keep numeric ids (`int`).

## 7. Users and claims become invitations, members and the trust layer

v1 provisioned sellers (`users.create`) and could sell for them at once, the seller claiming the
account and its funds later. **v2 creates no accounts: a seller sells only once they accepted an
invitation.**

1. `client.invitations.create(email=…, trust_layer=…, organization_fee_percent=…, redirect_url=…)`
   returns the invitation and its link (also emailed).
2. Wait for the `member.joined` webhook and store its `user_uuid` (match `invitation_uuid`).
3. Sell with `client.on_behalf_of(user_uuid)`.

`trust_layer=True` (the v1 "claim" model) holds the seller's payments in your wallet until you
trust them: `members.get_held_funds` shows what you owe, `members.trust` makes new payments go to
the seller directly, and the release of what is held is signed in the dashboard. Sellers v1
provisioned are already members; those who never claimed are members whose funds you hold
(`trusted_at is None`). The [README](README.md#marketplaces) walks the flow.

## 8. Models

Fee rates are **percents** now, everywhere: `fee_bps=150` → `fee_percent=1.5`,
`organization_fee_bps=250` → `organization_fee_percent=2.5`.

Models are pydantic v2 models with snake_case attributes and **explicit wire aliases**:
`model.to_dict()` (or `model_dump(by_alias=True)`) writes camelCase keys exactly as the API does
(2.x's alias generator wrote `customerUUID`). A field the API always sends is never `None` (an
absent value decodes to `""`, `0`, `False`, `[]` or `ZERO_TIME`); optional fields are
`Optional[...]`. A value of the wrong JSON type is a `ServerError`, never a silent coercion.

| 2.x (`qbitflow.dto…`) | 3.0.0 (`qbitflow`) | What changed |
|---|---|---|
| `LinkResponse` | `CheckoutSession` | + `expires_at` |
| `TransactionStatus` | `CheckoutSessionStatus` | `status` is a `CheckoutSessionStatusValue`; + `uuid`, `last_attempt`; `settlement_details` removed |
| `OneTimePaymentSession`, `SubscriptionSession`, `PaygSubscriptionSession`, `AnySession`, `BaseSession`, `SessionWebhookResponse`, `StatusLinkResponse` | removed | `PaymentSessionData` / `SubscriptionSessionData` in `checkout.expired` |
| `CreatePaymentSessionDto`, `CreateSubscriptionSessionDto`, `CreateCustomerDto`, `UpdateCustomerDto`, `CreateProductDto`, `UpdateProductDto`, `CreateUserDto`, `UpdateUserDto` | removed | keyword arguments of the methods; `SubscriptionTermsParams` for a product's terms |
| `Payment` | `Payment` | `transaction_hash` → `tx_hash`; `product_id` → `product_uuid`; `user_id` → `user_uuid`; `organization_id` removed; `currency` optional; `metadata` always set; + `chain`, `explorer_url`, `customer_reference`, `customer`, `refund`, `refundable`, `paid_min_units`, `paid_usd`, `confirmed_at` |
| `CombinedPaymentItem` | `CombinedPayment` | `source` is a `CombinedPaymentSource` (`subscription_history` → `subscriptionHistory`); + `refund`, `reference`, `subscription_reference` |
| `Subscription` | `Subscription` | `subscription_status` → `status`; `stopped` → the status `stopped`; `frequency` (seconds) → `Duration`; `product_id` → `product_uuid`; `next_billing_date` optional (None once cancelled); `last_billing_date` always set; + `current_period_end`, `action_required`, `price_usd`, `max_amount_per_period`, `cancelled_at`, `cancellation_reason`, `customer_reference`, `customer`, `dunning` |
| `PayAsYouGoSubscription` | removed | |
| `SubscriptionHistory` | `Bill` | the `Payment` renames; + `period_start`, `period_end`, `subscription_uuid` |
| `RefundEntry` | `Refund` | `tx_id` → `tx_uuid`; + `initiated_by`, `refund_percent`, `paid_min_units`, `paid_usd`, `amount_usd`, `currency_id`, `held`, `chain`, `explorer_url`, `customer` |
| `Customer` | `Customer` | `last_name` optional; + `verified`; `organization_id`, `user_id` → `user_uuid` |
| `Product` | `Product` | `id: int` → `uuid: str`; + `subscription` (terms), `payment_link` |
| `User` | `Member` (or `Me`) | `id` → `user_uuid`; `organization_fee_bps` → `organization_fee_percent`; `claimed_at` → `trusted_at`; + `joined_at`, `accepted_currency_ids`, `space_uuid` |
| `UserRole` | `Role` (+ `HANDLE`) | |
| `ApiKey`, `ClaimRequest`, `Organization`, `CreateClaimRequestResponse`, `ClaimFund`, `StatusResponse`, `StatusResponseError`, `TransactionShortType`, `SuccessResponse` | removed | |
| `AccountingEvent` | `AccountingEvent` | `payment_id` → `payment_uuid`; `related_payment_id` → `related_payment_uuid`; `product_id` → `product_uuid`; `type` and `chain` are enums; + `user_uuid`, member and customer names |
| `PaymentMetadata` | `PaymentMetadata` | `fee_bps` → `fee_percent`; `tx_amounts` is a `TxAmounts` (`TxAmountsFull` renamed, `TxAmountsUSD` → `TxAmountsUsd`); + network fees |
| `OrganizationFee`, `ReferralFee` | same names | `fee_bps` → `fee_percent`; the ids are removed |
| `Currency` | `Currency` | + `main_currency` |
| `Duration` | `Duration` | `Duration(value=0)` means none; the unit is a `DurationUnit` |
| `CursorData[T, str]` | `Page[T]` | `items`, `next_cursor`; `has_more()` → the `has_more` property |

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
| `subscription.stopped is True` | `SubscriptionStatus.STOPPED` (`stopped`): cancelled at `next_billing_date` |
| — | `SubscriptionStatus.PAUSED` (`paused`): paused by the customer |

**Grant access while `now < current_period_end`**, whatever the status: a check like
`status == ACTIVE` cuts off paying customers (`stopped`, `paused`) and keeps serving `pastDue`
ones.

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
| `RefundStatus` (`dto.transaction`) | `RefundStatus` (`PENDING`, `APPROVED`, `REJECTED`) |
| `CombinedPaymentItem.source` `"subscription_history"` | `CombinedPaymentSource.SUBSCRIPTION_HISTORY` (`subscriptionHistory`) |
| `AccountingEvent.type` (a `str`) | `AccountingEventType` |

## 10. Errors

| 2.x (`qbitflow.exceptions`) | 3.0.0 (`qbitflow`) |
|---|---|
| `QBitFlowError` | `QBitFlowError` (the base of every SDK error) |
| `APIError` | `ApiError` (the base of every error below, and any other HTTP error) |
| `ValidationError` (every 400, 422, and pydantic DTO failures) | `ValidationError`: 400 `validation_failed` and client-side checks (`status` None) |
| `InvalidRequestError` | `BadRequestError` (other 400s), or `ValidationError` |
| `AuthenticationError` | `AuthenticationError` (401) |
| — | `PermissionDeniedError` (403) |
| `NotFoundException` | `NotFoundError` (404) |
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
  request.body()`; Flask: `request.get_data()`).
- **Endpoints must be on payload version v2.** v1 webhook URLs were migrated as endpoints with
  `payload_version` `v1`, which still receive v1's bodies; 3.0.0 does not parse them
  (`parse_event` raises a `ValidationError`). Move each endpoint to v2 in the dashboard, or with
  `client.webhooks.endpoints.update(uuid, payload_version=WebhookPayloadVersion.V2)`, when your
  receiver runs 3.0.0. Moving keeps the endpoint's secret.
- **Event types** replace the two 2.x payloads: v1's transaction webhook becomes
  `payment.completed` / `subscription.created`, its subscription webhook `subscription.billed` /
  `subscription.statusChanged`, plus 11 new types (`checkout.expired`, `refund.*`,
  `member.joined`, …). Each parses into its own class (`PaymentCompletedEvent`, …) with a typed
  `data`; narrow with `isinstance`.
- Deliveries are at least once: deduplicate on `event.id`, and answer 2xx to the types you ignore.
- Endpoints are created per space with `client.webhooks.endpoints.create`, whose answer carries
  the `whsec_…` secret once.

## 12. Pagination

`get_all(limit, cursor)` becomes `list(limit=…, cursor=…, filters…)`, returning a `Page[T]`
(`items`, `next_cursor`, `has_more`). Pass `page.next_cursor` back as `cursor`, verbatim. Every
paginated list also has an iterator that walks every page lazily:

```python
for sub in client.subscriptions.iterate(limit=100):
    print(sub.uuid, sub.status)
```

## 13. Before and after: five common tasks

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
status = client.checkout_sessions.get_status(session.uuid)
if status.status == CheckoutSessionStatusValue.COMPLETED:
    payment = client.payments.get(session.uuid)  # the same id
    print(payment.amount, payment.tx_hash)
elif status.last_attempt is not None:
    print("an attempt failed, not final:", status.last_attempt.code)
```

### List a seller's payments

```python
# 2.x
# page = client.one_time_payments.on_behalf_of(42).get_all(limit=50)

# 3.0.0
from datetime import datetime, timedelta, timezone

for payment in client.payments.iterate(
    user_uuid="0192f1c2-7b3a-7c4d-9e5f-6a7b8c9d0e1f",  # organization key: one member's rows
    created_after=datetime.now(timezone.utc) - timedelta(days=30),
    limit=50,
):
    print(payment.uuid, payment.amount, payment.metadata.fee_percent)
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
from typing import Optional

from qbitflow import PaymentCompletedEvent, WebhookSignatureError, webhooks


def receive(raw_body: bytes, signature_header: Optional[str], secret: str) -> int:
    try:
        event = webhooks.construct_event(raw_body, signature_header, secret)
    except WebhookSignatureError:
        return 400
    if isinstance(event, PaymentCompletedEvent):
        print("fulfil", event.data.reference)
    return 200
```

### Handle an error

```python
# 2.x
# except NotFoundException: ...
# except ValidationError as e: print(e)  # field errors empty

# 3.0.0
from qbitflow import ApiError, NotFoundError, ValidationError

try:
    client.customers.create(name="Ada", email="ada@example.com")
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
