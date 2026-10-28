# Compliance and data handling

This document describes what the QBitFlow Python SDK does with data, so you can account for it in
your own privacy, security and compliance assessments. It describes the SDK only: QBitFlow's
processing of the data it receives is covered by QBitFlow's own terms and privacy policy
(<https://qbitflow.app>).

## What the SDK is

A client library that runs inside your application. It turns your method calls into HTTPS
requests to the QBitFlow API, decodes the answers into typed models, and verifies the webhooks
QBitFlow sends you. It is non-custodial like QBitFlow itself: it never holds funds, private keys
or wallet seeds, and it signs no blockchain transaction.

## What it sends, and where

- **Only to the base URL you configure** (by default `https://api.qbitflow.app/v2`), and only the
  requests your code makes.
- **Your API key**, in the `X-API-Key` header of every request.
- **The data you pass to a method**, as its query string or JSON body: for example a customer's
  name, email, phone number and address (`customers.create`), checkout references, product
  details, amounts and your `metadata`. The SDK adds no data of its own beyond the protocol
  headers: `User-Agent: qbitflow-python/<version>`, an `Idempotency-Key` on the creates, and the
  `On-Behalf-Of` and `X-Request-Id` headers when you set them.
- `webhooks.verify_remote` sends the webhook body and its signature header to the API for
  checking; the local `webhooks.verify` sends nothing.

Treat `metadata` as visible to anyone with access to your QBitFlow account and your webhook
endpoints: never put secrets or personal data in it.

## What it stores

Nothing. The SDK keeps no cache, no files and no database: the data it receives is returned to
your code as models in memory, and it is your application that decides what to keep.

## Telemetry and logging

- **No telemetry**: the SDK collects no usage data and contacts no service other than the base
  URL you configure.
- **No logging**: it writes no logs and prints nothing. `WebhookRouter(on_error=...)` lets you log
  rejected webhook deliveries yourself, if you choose to.

## Secrets

- The API key never appears in `repr(client)` or in error messages, and an invalid key is refused
  without being quoted.
- A webhook endpoint's secret (returned once, by `webhooks.endpoints.create`) is excluded from the
  model's `repr`, and a `WebhookRouter` never shows the secret it holds.
- Keep both in a secret store or environment variables (`QBITFLOW_API_KEY`,
  `QBITFLOW_WEBHOOK_SECRET`), never in source code. [SECURITY.md](SECURITY.md) lists the SDK's
  security properties and how to report a vulnerability.

## Cryptography

The SDK implements no cryptographic primitive of its own. TLS is provided by `httpx` (certificate
verification on, as httpx's default, for the client the SDK creates), and webhook signatures use
the Python standard library's `hmac` and `hashlib` (HMAC-SHA256, constant-time comparison).

## Dependencies

Two runtime dependencies, both open source:

| Package | Version | Use |
|---|---|---|
| [`httpx`](https://pypi.org/project/httpx/) | `>=0.24, <1` | HTTP and TLS |
| [`pydantic`](https://pypi.org/project/pydantic/) | `>=2.5, <3` | decoding the API's answers into typed models |

The optional extras (`flask`, `django`, `fastapi`, `starlette`) only install a web framework for
the webhook router's adapters; the SDK never imports one unless you call its adapter.

## License

The SDK is licensed under the Mozilla Public License 2.0 ([LICENSE](LICENSE)).
