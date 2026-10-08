"""Error classes, is_retryable, and idempotency keys across processes.

QBITFLOW_API_KEY=sk_… python examples/errors_and_retries.py
"""

from typing import Any, Callable, Optional

from _common import new_client

import qbitflow


def describe(what: str, error: Optional[Exception]) -> None:
    print(f"{what}: ", end="")
    if error is None:
        print("ok")
    elif isinstance(error, qbitflow.ValidationError):
        print(f"invalid input (status {error.status})")  # None: refused before sending
        for f in error.field_errors:
            print(f"  {f.field}: {f.message}")
    elif isinstance(error, qbitflow.NotFoundError):
        print(f"not found (request {error.request_id})")
    elif isinstance(error, qbitflow.ConflictError):
        print(f"conflict {error.code}, details {error.details}")  # e.g. unique_violation
    elif isinstance(error, qbitflow.IdempotencyError):
        print("idempotency key reused with another request: use a new key")
    elif isinstance(error, qbitflow.RateLimitError):
        print(f"rate limited: retry after {error.retry_after} s")
    elif isinstance(error, qbitflow.AuthenticationError):
        print("bad API key")
    elif isinstance(error, qbitflow.PermissionDeniedError):
        print("not allowed:", error.code)  # forbidden, policy_disabled, plan_required
    elif isinstance(error, (qbitflow.NetworkError, qbitflow.ServerError)):
        print(f"transient (retryable: {qbitflow.is_retryable(error)}): {error}")
    elif isinstance(error, qbitflow.ApiError):
        print(f"API error {error.status} {error.code}")
    else:
        print(error)


def attempt(what: str, call: Callable[[], Any]) -> Any:
    try:
        result = call()
    except qbitflow.ApiError as exc:
        describe(what, exc)
        return None
    describe(what, None)
    return result


def handle_errors(client: qbitflow.QBitFlow) -> None:
    # docs:start errors-handling
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
    # docs:end errors-handling


def create_once() -> qbitflow.CheckoutSession:
    # docs:start retries-idempotency
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
    # docs:end retries-idempotency
    client.close()
    return session


def main() -> None:
    with new_client() as client:
        # Refused before sending: field errors by wire name.
        attempt("invalid params", lambda: client.products.create(name="x", price=-1))
        # A 404 from the API.
        attempt(
            "unknown session",
            lambda: client.checkout_sessions.get_status("pay@019eca82-5680-7b00-8000-00000000dead"),
        )
        handle_errors(client)

        # The same Idempotency-Key returns the first result (kept 24 hours).
        first = attempt("create", create_once)
        again = attempt("create again", create_once)
        if first is not None and again is not None:
            print(f"same checkout both times: {first.uuid == again.uuid} ({first.uuid})")
        # The same key with another body: 422 idempotency_key_reused.
        attempt(
            "same key, other body",
            lambda: client.checkout_sessions.create_payment(
                product_name="T-shirt",
                price=9.99,
                reference="order-1042",
                options=qbitflow.RequestOptions(idempotency_key="checkout-order-1042"),
            ),
        )
        if first is not None:
            # Frees order-1042 for the next run (a 409 once it is already expired).
            attempt("expire", lambda: client.checkout_sessions.expire(first.uuid))


if __name__ == "__main__":
    main()
