"""Error mapping, payload, message format (Go errors_test.go)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, Optional, Type

import httpx
import pytest

from qbitflow import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    FieldError,
    GoneError,
    IdempotencyError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    QBitFlowError,
    RateLimitError,
    ServerError,
    ValidationError,
    WebhookSignatureError,
    WebhookSignatureReason,
)
from qbitflow._transport import Response, as_webhook_signature_error, error_from_response
from qbitflow.errors import field_error

from .conftest import make_client, reply

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def mapped(status: int, body: str, headers: Optional[Dict[str, str]] = None) -> ApiError:
    return error_from_response(Response(status, httpx.Headers(headers or {}), body.encode()), NOW)


@pytest.mark.parametrize(
    "status, code, cls",
    [
        (400, "validation_failed", ValidationError),
        (400, "bad_request", BadRequestError),
        (400, "foreign_key_violation", BadRequestError),
        (400, "invalid_signature", BadRequestError),
        (400, "", BadRequestError),
        (401, "unauthorized", AuthenticationError),
        (403, "forbidden", PermissionDeniedError),
        (403, "policy_disabled", PermissionDeniedError),
        (403, "plan_required", PermissionDeniedError),
        (404, "not_found", NotFoundError),
        (409, "unique_violation", ConflictError),
        (409, "tx_already_sent", ConflictError),
        (409, "merchant_not_ready", ConflictError),
        (409, "refund_already_exists", ConflictError),
        (409, "held_funds_pending", ConflictError),
        (409, "idempotency_key_in_use", ConflictError),
        (410, "merchant_closed", GoneError),
        (422, "idempotency_key_reused", IdempotencyError),
        (422, "something_else", ApiError),
        (413, "request_too_large", ApiError),
        (405, "", ApiError),
        (429, "rate_limit_exceeded", RateLimitError),
        (500, "internal", ServerError),
        (503, "network_unavailable", ServerError),
        (504, "timeout", ServerError),
        (301, "", ServerError),
        (304, "", ServerError),
    ],
)
def test_error_mapping(status: int, code: str, cls: Type[ApiError]) -> None:
    body = json.dumps({"error": "the message", "code": code, "requestId": "req-body"})
    err = mapped(status, body)
    assert type(err) is cls
    assert isinstance(err, ApiError) and isinstance(err, QBitFlowError)
    assert err.status == status and err.code == code
    assert err.message == "the message" and err.request_id == "req-body"
    assert err.details == {}


def test_details_and_field_errors() -> None:
    body = """{
        "error": "name must be at least 2 characters",
        "code": "validation_failed",
        "details": {"errors": [
            {"field": "name", "message": "name must be at least 2 characters"},
            {"field": "frequency.unit", "message": "frequency.unit is required"},
            "garbage",
            {"other": 1}
        ], "max": 5},
        "errors": [{"field": "TOPLEVEL", "message": "must be ignored"}],
        "requestId": "abc-123",
        "debug": "stack trace"
    }"""
    err = mapped(400, body, {"X-Request-Id": "from-header"})
    assert isinstance(err, ValidationError)
    assert err.field_errors == [
        FieldError("name", "name must be at least 2 characters"),
        FieldError("frequency.unit", "frequency.unit is required"),
    ]
    assert err.request_id == "abc-123"  # the body wins over the header
    assert err.details["max"] == 5
    assert str(err) == (
        "name must be at least 2 characters (status 400, code validation_failed, request abc-123); "
        "name: name must be at least 2 characters; frequency.unit: frequency.unit is required"
    )
    assert err.raw_body == body.encode()
    assert "stack trace" not in str(err)


@pytest.mark.parametrize(
    "body, header, status, message, request_id, code",
    [
        ("", "hdr-1", 404, "not found", "hdr-1", ""),
        ("<html>gateway</html>", None, 502, "bad gateway", "", ""),
        ("[1,2]", "hdr-2", 500, "internal server error", "hdr-2", ""),
        (
            '{"error": 5, "code": ["x"], "details": "str", "requestId": 7}',
            "hdr-3",
            403,
            "forbidden",
            "hdr-3",
            "",
        ),
        ('{"error":"boom","code":"error"}', None, 409, "boom", "", "error"),
        ('{"error":"x"}', "hdr-4", 401, "x", "hdr-4", ""),
        ("{}", None, 499, "http status 499", "", ""),
    ],
)
def test_error_fallbacks(
    body: str, header: Optional[str], status: int, message: str, request_id: str, code: str
) -> None:
    err = mapped(status, body, {"X-Request-Id": header} if header else None)
    assert (err.message, err.request_id, err.code) == (message, request_id, code)
    assert err.details == {} and err.field_errors == []


@pytest.mark.parametrize(
    "err, want",
    [
        (
            ApiError("not found", status=404, code="not_found", request_id="r1"),
            "not found (status 404, code not_found, request r1)",
        ),
        (ApiError("boom", status=500), "boom (status 500)"),
        (
            ValidationError(
                "validation failed", field_errors=[FieldError("apiKey", "apiKey is required")]
            ),
            "validation failed; apiKey: apiKey is required",
        ),
        (ApiError(), "qbitflow error"),
    ],
)
def test_message_format(err: ApiError, want: str) -> None:
    assert str(err) == want


def test_message_includes_cause() -> None:
    try:
        try:
            raise OSError("dial tcp: refused")
        except OSError as cause:
            raise NetworkError("request failed") from cause
    except NetworkError as err:
        assert str(err) == "request failed: dial tcp: refused"


def test_errors_through_the_client() -> None:
    client, _, _ = make_client(
        lambda _r, _n: reply(
            403,
            (
                '{"error":"members.products is off","code":"policy_disabled",'
                '"details":{"policy":"members.products"}}'
            ),
            {"X-Request-Id": "hdr-id"},
        )
    )
    with pytest.raises(PermissionDeniedError) as info:
        client.me()
    err = info.value
    assert err.details["policy"] == "members.products" and err.request_id == "hdr-id"
    assert err.code == "policy_disabled"


def test_client_side_errors() -> None:
    err = field_error("price", "must be a number above 0")
    assert err.status is None and err.code == "" and err.details == {}
    assert str(err) == "validation failed; price: price must be a number above 0"
    assert isinstance(err, QBitFlowError)


def test_as_webhook_signature_error() -> None:
    err = as_webhook_signature_error(
        mapped(400, '{"error":"x","code":"invalid_signature","requestId":"r"}')
    )
    assert isinstance(err, WebhookSignatureError)
    assert err.reason == WebhookSignatureReason.INVALID_SIGNATURE and err.status == 400
    assert err.request_id == "r"
    for other in (
        mapped(400, '{"code":"validation_failed"}'),
        mapped(400, '{"code":"bad_request"}'),
        mapped(404, "{}"),
    ):
        assert as_webhook_signature_error(other) is other


def test_rate_limit_fields_default_none() -> None:
    err = mapped(429, "{}")
    assert isinstance(err, RateLimitError)
    assert err.retry_after is None and err.limit is None and err.period_seconds is None
