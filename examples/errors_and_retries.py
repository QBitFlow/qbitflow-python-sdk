"""Error classes, is_retryable, and idempotency keys across processes.

QBITFLOW_API_KEY=sk_… python examples/errors_and_retries.py
"""

import os
import sys
import time
from typing import Any, Callable, Optional

from qbitflow import (
    ApiError,
    AuthenticationError,
    ConflictError,
    IdempotencyError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    QBitFlow,
    RateLimitError,
    RequestOptions,
    ServerError,
    ValidationError,
    is_retryable,
)


def describe(what: str, error: Optional[Exception]) -> None:
    print(f"{what}: ", end="")
    if error is None:
        print("ok")
    elif isinstance(error, ValidationError):
        print(f"invalid input (status {error.status})")  # None: refused before sending
        for f in error.field_errors:
            print(f"  {f.field}: {f.message}")
    elif isinstance(error, NotFoundError):
        print(f"not found (request {error.request_id})")
    elif isinstance(error, ConflictError):
        print(f"conflict {error.code}, details {error.details}")  # e.g. unique_violation
    elif isinstance(error, IdempotencyError):
        print("idempotency key reused with another request: use a new key")
    elif isinstance(error, RateLimitError):
        print(f"rate limited: retry after {error.retry_after} s")
    elif isinstance(error, AuthenticationError):
        print("bad API key")
    elif isinstance(error, PermissionDeniedError):
        print("not allowed:", error.code)  # forbidden, policy_disabled, plan_required
    elif isinstance(error, (NetworkError, ServerError)):
        print(f"transient (retryable: {is_retryable(error)}): {error}")
    elif isinstance(error, ApiError):
        print(f"API error {error.status} {error.code}")
    else:
        print(error)


def attempt(what: str, call: Callable[[], Any]) -> Any:
    try:
        result = call()
    except ApiError as exc:
        describe(what, exc)
        return None
    describe(what, None)
    return result


def main() -> None:
    key = os.environ.get("QBITFLOW_API_KEY", "")
    if not key:
        sys.exit("set QBITFLOW_API_KEY")
    try:
        client = QBitFlow(
            key, base_url=os.environ.get("QBITFLOW_BASE_URL") or None, max_retries=3, timeout=15
        )
    except ValidationError as exc:
        sys.exit(str(exc))  # a bad key format or option

    with client:
        # Refused before sending: field errors by wire name.
        attempt("invalid params", lambda: client.products.create(name="x", price=-1))
        # A 404 from the API.
        attempt(
            "unknown session",
            lambda: client.checkout_sessions.get_status("pay@019eca82-5680-7b00-8000-00000000dead"),
        )

        # The same Idempotency-Key returns the first result: safe to retry across processes.
        idempotency_key = "signup-" + time.strftime("%Y%m%d-%H%M%S")
        email = f"ada+{idempotency_key}@example.com"
        options = RequestOptions(idempotency_key=idempotency_key, request_id="signup-42")
        try:
            first = client.customers.create(name="Ada", email=email, options=options)
        except ApiError as exc:
            describe("create", exc)
            return
        again = client.customers.create(name="Ada", email=email, options=options)
        print(f"same customer both times: {first.uuid == again.uuid} ({first.uuid})")

        # The same key with another body: 422 idempotency_key_reused.
        attempt(
            "same key, other body",
            lambda: client.customers.create(name="Grace", email=email, options=options),
        )
        # Without a key, a second customer with the same email.
        attempt("second create", lambda: client.customers.create(name="Ada", email=email))

        client.customers.delete(first.uuid)  # clean up


if __name__ == "__main__":
    main()
