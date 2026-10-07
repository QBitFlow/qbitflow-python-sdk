"""
Offline tests for how error responses are turned into exceptions (unit level).

The payloads below are the API's actual error envelopes, captured from the server::

    400 -> {"errors":[{"field":"ProductName","message":"ProductName is too short"},
                      {"field":"Price","message":"Price is too short"}]}
    401 -> {"error":"invalid or missing authentication token"}
    404 -> {"error":"resource not found"}

Note there is no top-level ``message`` key on an error response; ``message`` is the
success envelope, so it is only honoured as a last-resort fallback.

These tests call ``_handle_http_status`` / ``_extract_error`` directly. The end-to-end
behaviour through a real request — where the 2.5.0 regression lived — is covered by
``tests/test_transport.py``.

Run with:
    pytest tests/test_error_parsing.py -v
"""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    FieldError,
    ForbiddenException,
    InvalidRequestError,
    NotFoundException,
    QBitFlowError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from qbitflow.requests.base_request import BaseRequest

VALIDATION_BODY = {
    "errors": [
        {"field": "ProductName", "message": "ProductName is too short"},
        {"field": "Price", "message": "Price is too short"},
    ]
}


@pytest.fixture
def request_handler():
    handler = BaseRequest(api_key="sk_dummy_offline_tests")
    yield handler
    handler.close()


def response_with(status_code: int, **kwargs) -> httpx.Response:
    """Build a real httpx.Response so the parsing runs against the genuine type."""
    return httpx.Response(status_code, request=httpx.Request("GET", "http://localhost/x"), **kwargs)


# ── Extraction ───────────────────────────────────────────────────────────────


def test_every_field_failure_is_reported(request_handler):
    """Surfacing only errors[0] leaves the caller to discover the rest one round-trip
    at a time."""
    message, fields = request_handler._extract_error(response_with(400, json=VALIDATION_BODY))

    assert "ProductName is too short" in message
    assert "Price is too short" in message
    assert len(fields) == 2


def test_field_names_are_exposed_structurally(request_handler):
    _, fields = request_handler._extract_error(response_with(400, json=VALIDATION_BODY))

    assert fields == [
        FieldError(field="ProductName", message="ProductName is too short"),
        FieldError(field="Price", message="Price is too short"),
    ]


def test_message_is_prefixed_with_the_field_name(request_handler):
    body = {"errors": [{"field": "Price", "message": "Price is too short"}]}

    message, _ = request_handler._extract_error(response_with(400, json=body))

    assert message == "Price: Price is too short"


def test_bare_string_entry_without_a_field(request_handler):
    body = {"errors": ["name is required"]}

    message, fields = request_handler._extract_error(response_with(400, json=body))

    assert message == "name is required"
    assert fields == [FieldError(field="", message="name is required")]


def test_error_key_wins_over_a_synthesised_message(request_handler):
    body = {"error": "First", "message": "Second"}

    message, _ = request_handler._extract_error(response_with(400, json=body))

    assert message == "First"


def test_message_is_honoured_only_as_a_fallback(request_handler):
    body = {"message": "Bad request"}

    message, fields = request_handler._extract_error(response_with(400, json=body))

    assert message == "Bad request"
    assert fields == []


def test_non_json_body_text_is_kept(request_handler):
    """A proxy's HTML page is more useful than a generic label."""
    message, fields = request_handler._extract_error(response_with(500, text="<html>oops</html>"))

    assert message == "<html>oops</html>"
    assert fields == []


def test_empty_body_falls_back_to_the_http_status_text(request_handler):
    message, fields = request_handler._extract_error(response_with(502, text=""))

    assert message == "Bad Gateway"
    assert fields == []


def test_unrecognised_shape_falls_back_to_the_status_text(request_handler):
    message, fields = request_handler._extract_error(response_with(400, json={"detail": "nope"}))

    assert message == "Bad Request"
    assert fields == []


def test_fields_are_parsed_for_any_status(request_handler):
    """The ``errors[]`` list is honoured whatever the status, not only on 400/422."""
    for status in (401, 403, 404, 409, 429, 500):
        _, fields = request_handler._extract_error(response_with(status, json=VALIDATION_BODY))
        assert len(fields) == 2, status


# ── Status mapping carries the fields through ────────────────────────────────


@pytest.mark.parametrize(
    ("status_code", "expected_type"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, ForbiddenException),
        (404, NotFoundException),
        (409, ConflictError),
        (429, RateLimitError),
        (500, ServerError),
    ],
)
def test_fields_survive_the_status_mapping(request_handler, status_code, expected_type):
    """
    `fields` lives on the base error, so it is readable whichever subclass is raised.
    That matters because a validation-shaped body is not tied to one status.
    """
    with pytest.raises(expected_type) as exc_info:
        request_handler._handle_http_status(response_with(status_code, json=VALIDATION_BODY))

    assert len(exc_info.value.fields) == 2
    assert exc_info.value.fields[0].field == "ProductName"
    assert exc_info.value.status_code == status_code


@pytest.mark.parametrize(
    ("status_code", "expected_type"),
    [
        # A validation failure raises the *same* type as client-side validation, so one
        # `except ValidationError` covers a field rejected locally and the same field
        # rejected by the API.
        (400, ValidationError),
        (422, ValidationError),
        (401, AuthenticationError),
        # A permissions failure is not a malformed request; it used to be reported as one.
        (403, ForbiddenException),
        (404, NotFoundException),
        # A conflict has its own type; calling it "validation failed" would be misleading.
        (409, ConflictError),
        (429, RateLimitError),
        # 4xx with no more specific meaning.
        (405, InvalidRequestError),
        (425, InvalidRequestError),
        # Server-side failures, and redirects (misconfigured base URL).
        (500, ServerError),
        (503, ServerError),
        (301, ServerError),
        (307, ServerError),
    ],
)
def test_status_codes_map_to_their_own_type(request_handler, status_code, expected_type):
    with pytest.raises(expected_type) as exc_info:
        request_handler._handle_http_status(
            response_with(status_code, json={"error": "something went wrong"})
        )

    assert type(exc_info.value) is expected_type
    assert exc_info.value.status_code == status_code


def test_server_error_is_still_an_api_error(request_handler):
    with pytest.raises(APIError):
        request_handler._handle_http_status(response_with(500, json={"error": "boom"}))


def test_forbidden_is_not_reported_as_a_malformed_request(request_handler):
    """
    A 403 means the API key was accepted but its role is too low — most often an
    admin-level call (including on_behalf_of) made with a user-level key. Reporting that
    as InvalidRequestError sent users looking for a bug in their payload.
    """
    with pytest.raises(ForbiddenException) as exc_info:
        request_handler._handle_http_status(response_with(403, json={"error": "forbidden"}))

    assert exc_info.value.status_code == 403
    assert not isinstance(exc_info.value, InvalidRequestError)


def test_rate_limit_parses_retry_after_seconds(request_handler):
    with pytest.raises(RateLimitError) as exc_info:
        request_handler._handle_http_status(
            response_with(429, json={"error": "rl"}, headers={"Retry-After": "12"})
        )

    assert exc_info.value.retry_after == 12
    assert exc_info.value.response == {"retry_after": 12}


def test_rate_limit_parses_an_http_date_retry_after(request_handler):
    """An HTTP-date ``Retry-After`` becomes the seconds from now (floored at 0)."""
    future = datetime.now(timezone.utc) + timedelta(seconds=90)
    header = format_datetime(future, usegmt=True)

    with pytest.raises(RateLimitError) as exc_info:
        request_handler._handle_http_status(
            response_with(429, json={"error": "rl"}, headers={"Retry-After": header})
        )

    assert 80 <= exc_info.value.retry_after <= 90


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", 0),
        (" 7 ", 7),
        ("Wed, 21 Oct 2026 07:28:00 GMT", 120),
        ("Wed, 21 Oct 2026 07:20:00 GMT", 0),  # in the past → 0
        ("Wednesday, 21-Oct-26 07:28:00 GMT", 120),  # RFC 850 form
        ("soon", None),
        ("-5", None),
        ("", None),
        (None, None),
    ],
)
def test_retry_after_forms(value, expected):
    now = datetime(2026, 10, 21, 7, 26, 0, tzinfo=timezone.utc)
    assert BaseRequest._parse_retry_after(value, now=now) == expected


def test_fields_default_to_empty_for_a_single_message_error(request_handler):
    body = {"error": "resource not found"}

    with pytest.raises(NotFoundException) as exc_info:
        request_handler._handle_http_status(response_with(404, json=body))

    assert exc_info.value.fields == []
    assert exc_info.value.message == "resource not found"


def test_a_success_status_raises_nothing(request_handler):
    assert request_handler._handle_http_status(response_with(200, json={"ok": True})) is None


# ── FieldError itself ────────────────────────────────────────────────────────


def test_field_error_renders_with_and_without_a_field():
    assert str(FieldError(field="Price", message="too short")) == "Price: too short"
    assert str(FieldError(field="", message="too short")) == "too short"


def test_fields_are_available_on_the_base_error_type():
    error = QBitFlowError("boom", fields=[FieldError(field="Price", message="too short")])

    assert error.fields[0].field == "Price"
    # Defaults to an empty list rather than None, so callers can always iterate.
    assert QBitFlowError("boom").fields == []


def test_every_exception_type_exposes_status_code_and_fields():
    for cls in (
        APIError,
        ServerError,
        AuthenticationError,
        ValidationError,
        ForbiddenException,
        NotFoundException,
        ConflictError,
        RateLimitError,
        InvalidRequestError,
    ):
        err = cls("x", status_code=418, fields=[FieldError("f", "m")])
        assert err.status_code == 418 and err.fields[0].field == "f"
        assert str(err) == "[418] x"
