"""
Offline tests for how error responses are turned into exceptions.

The payloads below are the API's actual error envelopes, captured from the server::

    400 -> {"errors":[{"field":"ProductName","message":"ProductName is too short"},
                      {"field":"Price","message":"Price is too short"}]}
    401 -> {"error":"invalid or missing authentication token"}
    404 -> {"error":"resource not found"}

Note there is no top-level ``message`` key on an error response; ``message`` is the
success envelope, so it is only honoured as a last-resort fallback.

Run with:
    pytest tests/test_error_parsing.py -v
"""

import httpx
import pytest

from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    FieldError,
    ForbiddenException,
    InvalidRequestError,
    NotFoundException,
    QBitFlowError,
    RateLimitError,
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
    return BaseRequest(api_key="sk_dummy_offline_tests")


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


def test_non_json_body_falls_back_to_a_generic_message(request_handler):
    message, fields = request_handler._extract_error(response_with(500, text="<html>oops</html>"))

    assert "500" in message
    assert fields == []


def test_unrecognised_shape_falls_back_to_a_generic_message(request_handler):
    message, fields = request_handler._extract_error(response_with(400, json={"detail": "nope"}))

    assert "400" in message
    assert fields == []


# ── Status mapping carries the fields through ────────────────────────────────


@pytest.mark.parametrize(
    ("status_code", "expected_type"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (404, NotFoundException),
        (429, RateLimitError),
        (500, APIError),
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
        (429, RateLimitError),
        # 4xx with no more specific meaning. Deliberately not ValidationError: calling a
        # 409 Conflict "validation failed" would be misleading.
        (409, InvalidRequestError),
        (405, InvalidRequestError),
        (425, InvalidRequestError),
        (500, APIError),
        (503, APIError),
    ],
)
def test_status_codes_map_to_their_own_type(request_handler, status_code, expected_type):
    with pytest.raises(expected_type):
        request_handler._handle_http_status(
            response_with(status_code, json={"error": "something went wrong"})
        )


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
