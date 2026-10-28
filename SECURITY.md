# Security Policy

## Supported versions

Only the latest release of the current major version receives security fixes.

| Version | Supported |
|---|---|
| 3.x (latest release) | Yes |
| Earlier 3.x releases | No: upgrade to the latest 3.x |
| 2.x and older | No (they target the retired API v1) |

## Reporting a vulnerability

Please report suspected vulnerabilities privately by email to
**[security@qbitflow.app](mailto:security@qbitflow.app)**. Do **not** open a public GitHub issue,
pull request or discussion for a security problem.

Include as much of the following as you can:

- the SDK version (`qbitflow.__version__`), your Python version and operating system;
- a description of the issue and its impact;
- the steps, or a minimal script, to reproduce it;
- any proof of concept, logs or affected configuration.

Never include a live API key, a webhook secret or a customer's personal data in a report: redact
them, or use a test-mode key you then revoke.

We will acknowledge your report, keep you informed as we investigate, and credit you in the
advisory if you wish.

## Disclosure

Once a fix is released, the vulnerability is disclosed in a
[GitHub Security Advisory](https://github.com/QBitFlow/qbitflow-python-sdk/security/advisories)
for this repository and in the `Security` section of [CHANGELOG.md](CHANGELOG.md), with the
versions affected and the version that fixes it.

## The SDK's security properties

What the SDK itself does (your integration remains responsible for storing keys and secrets, and
for its own HTTP client when you pass one):

- **API key checks and redaction.** `QBitFlow(...)` refuses a key that is blank, does not start
  with `sk_`, or contains a character other than printable ASCII without spaces (a header could
  not carry it), before anything is sent; the error never quotes the key. The key is sent only in
  the `X-API-Key` header, and never appears in `repr(client)` or in an error's message.
- **Webhook secrets kept out of reprs.** The `secret` of `WebhookEndpointCreated` (returned only
  when an endpoint is created) is excluded from the model's `repr`, and `repr(WebhookRouter)`
  shows only the registered event types, never the secret.
- **Webhook signature verification.** `webhooks.verify`, `construct_event` and `WebhookRouter`
  compute the HMAC-SHA256 of `<timestamp>.<raw body>` with the endpoint's secret and compare it
  with **every** `v1` signature of the `QBitFlow-Signature` header in constant time
  (`hmac.compare_digest`). A timestamp more than 5 minutes (`tolerance`, in seconds) from the
  clock is refused, which bounds replays. The router's framework adapters read at most 1 MiB of
  body, and answer errors without echoing the secret or the exception.
- **Transport.** Requests go through `httpx`. A client the SDK creates verifies TLS certificates
  (httpx's default). Redirects are never followed, so the key is never forwarded to another host.
  The base URL must be an absolute `http` or `https` URL with a host and without credentials,
  query or fragment (the error never quotes it); keep the default `https://api.qbitflow.app/v2`
  in production.
- **Timeouts.** `timeout` (30 seconds by default) bounds each attempt as a whole, from sending the
  request to the last byte of the answer's body, so a server trickling its answer cannot hold a
  call past it. Retries are bounded (`max_retries`, 3 by default) and never wait more than 60
  seconds for a rate limit.
- **Validation before sending.** Inputs (references, URLs, amounts, metadata, ids, path segments)
  are checked client-side, and every path segment is percent-encoded (a `/` inside an id, and a
  `.` or `..` segment, included), so an input can never reach another route.
- **No telemetry, no logging.** The SDK sends nothing but the requests you make to the base URL
  you configure, writes no logs, prints nothing and stores nothing on disk.
