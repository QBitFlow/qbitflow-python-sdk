"""Local webhook verification (Go webhook_test.go): the shared vector, tolerance, header parsing,
raw bodies, construct_event."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional, Union

import pytest

from qbitflow import (
    QBitFlow,
    ValidationError,
    WebhookSignatureError,
    WebhookSignatureReason,
    WebhookTestEvent,
    webhooks,
)

BODY = (
    '{"createdAt":"2026-10-01T12:00:00Z","data":{},"id":"evt_3f1c'
    '2d4e-5a6b-5c7d-8e9f-0a1b2c3d4e5f","test":false,"type":"webho'
    'ok.test","version":"v2"}'
)
T = 1790856000
NEW = "4a158046f55556e922bdec376a917c3ac338ba575b495f825427541a60bd2f4d"  # whsec_new_secret
OLD = "1cc78a6297ad96dd282d9d0399def50ed42a4e651885ac79f8528194227bc4f5"  # whsec_old_secret
HEADER = f"t={T},v1={NEW},v1={OLD}"

R = WebhookSignatureReason


def sign(secret: str, t: Union[int, str], body: Union[bytes, str]) -> str:
    data = body.encode() if isinstance(body, str) else body
    return hmac.new(secret.encode(), f"{t}.".encode() + data, hashlib.sha256).hexdigest()


def reason(
    body: Union[bytes, str], header: Optional[str], secret: str, offset: float = 0, **kw: float
) -> Optional[str]:
    try:
        webhooks.verify(body, header, secret, now=T + offset, **kw)
    except WebhookSignatureError as exc:
        assert exc.status is None
        return str(exc.reason)
    return None


def test_vector() -> None:
    assert sign("whsec_new_secret", T, BODY) == NEW
    assert sign("whsec_old_secret", T, BODY) == OLD
    for secret in ("whsec_new_secret", "whsec_old_secret"):
        assert reason(BODY, HEADER, secret, 60) is None
    for secret in ("whsec_other", "new_secret", "whsec_new_secret "):
        assert reason(BODY, HEADER, secret, 60) == R.NO_MATCHING_SIGNATURE
    for secret in ("whsec_new_secret", "whsec_old_secret", "whsec_other"):
        assert reason(BODY, HEADER, secret, 360) == R.TIMESTAMP_OUTSIDE_TOLERANCE


@pytest.mark.parametrize(
    "offset, tolerance, ok",
    [
        (0, None, True),
        (300, None, True),
        (301, None, False),
        (-300, None, True),  # t in the future: either direction
        (-301, None, False),
        (60, 10, False),
        (10, 10, True),
        (299, 0, True),  # 0 or less keeps 300 s
        (301, -1, False),
        (3000, 3600, True),
    ],
)
def test_tolerance(offset: int, tolerance: Optional[int], ok: bool) -> None:
    kw = {} if tolerance is None else {"tolerance": tolerance}
    got = reason(BODY, f"t={T},v1={NEW}", "whsec_new_secret", offset, **kw)
    assert got == (None if ok else R.TIMESTAMP_OUTSIDE_TOLERANCE)


def test_far_future_timestamp() -> None:
    assert (
        reason(BODY, f"t=9223372036854775807,v1={NEW}", "whsec_new_secret")
        == R.TIMESTAMP_OUTSIDE_TOLERANCE
    )


def test_clocks() -> None:
    header = f"t={T},v1={NEW}"
    webhooks.verify(
        BODY, header, "whsec_new_secret", now=datetime.fromtimestamp(T + 5, timezone.utc)
    )
    webhooks.verify(BODY, header, "whsec_new_secret", now=lambda: T + 5)
    with pytest.raises(ValidationError):
        webhooks.verify(BODY, header, "whsec_new_secret", now="later")


TS = str(T)


@pytest.mark.parametrize(
    "name, header, want",
    [
        ("rotation", HEADER, None),
        ("new only", f"t={TS},v1={NEW}", None),
        ("v1 first", f"v1={NEW},t={TS}", None),
        ("spaces around parts", f"  t = {TS} ,  v1 = {NEW}  ", None),
        ("bad v1 then good", f"t={TS},v1=deadbeef,v1={NEW}", None),
        ("good v1 then bad", f"t={TS},v1={NEW},v1=deadbeef", None),
        ("unknown scheme ignored", f"t={TS},v0={NEW},v1={NEW},v2=x", None),
        ("parts without =", f"t={TS},junk,v1={NEW},", None),
        ("empty", "", R.MISSING_HEADER),
        ("blank", "   ", R.MISSING_HEADER),
        ("none", None, R.MISSING_HEADER),
        ("garbage", "garbage", R.MALFORMED_HEADER),
        ("no t", f"v1={NEW}", R.MALFORMED_HEADER),
        ("no v1", f"t={TS}", R.MALFORMED_HEADER),
        ("only unknown scheme", f"t={TS},v0={NEW}", R.MALFORMED_HEADER),
        ("sha256 legacy scheme", f"sha256={NEW}", R.MALFORMED_HEADER),
        ("t not a number", f"t=abc,v1={NEW}", R.MALFORMED_HEADER),
        ("t negative", f"t=-{TS},v1={NEW}", R.MALFORMED_HEADER),
        ("t with sign", f"t=+{TS},v1={NEW}", R.MALFORMED_HEADER),
        ("t decimal", f"t={TS}.0,v1={NEW}", R.MALFORMED_HEADER),
        ("t empty", f"t=,v1={NEW}", R.MALFORMED_HEADER),
        ("t non-ASCII digits", f"t=１７９０８５６０００,v1={NEW}", R.MALFORMED_HEADER),
        ("t overflow", f"t=99999999999999999999,v1={NEW}", R.MALFORMED_HEADER),
        ("duplicate t", f"t={TS},t={TS},v1={NEW}", R.MALFORMED_HEADER),
        ("uppercase hex", f"t={TS},v1={NEW.upper()}", R.NO_MATCHING_SIGNATURE),
        ("truncated hex", f"t={TS},v1={NEW[:63]}", R.NO_MATCHING_SIGNATURE),
        ("value with =", f"t={TS},v1={NEW}=", R.NO_MATCHING_SIGNATURE),
        ("empty v1", f"t={TS},v1=", R.NO_MATCHING_SIGNATURE),
        ("non-ASCII v1", f"t={TS},v1=é", R.NO_MATCHING_SIGNATURE),
        ("other t", f"t=1790856001,v1={NEW}", R.NO_MATCHING_SIGNATURE),
        ("leading zeros signed as received", f"t=0{TS},v1={NEW}", R.NO_MATCHING_SIGNATURE),
    ],
)
def test_header_parsing(name: str, header: Optional[str], want: Optional[str]) -> None:
    assert reason(BODY, header, "whsec_new_secret", 30) == want


def test_leading_zeros_are_part_of_the_signed_text() -> None:
    header = f"t=0{TS},v1={sign('whsec_new_secret', '0' + TS, BODY)}"
    assert reason(BODY, header, "whsec_new_secret") is None


def test_raw_body() -> None:
    header = f"t={T},v1={NEW}"
    for body in (
        BODY.replace('"test":false', '"test":true'),
        BODY.replace(',"id"', ', "id"'),
        BODY + "\n",
    ):
        assert reason(body, header, "whsec_new_secret") == R.NO_MATCHING_SIGNATURE
    for raw in ('{"name":"Zoë – 李小龙 ☃"}'.encode(), bytes([0xFF, 0xFE, ord("{"), ord("}")]), b""):
        assert (
            reason(raw, f"t={T},v1={sign('whsec_new_secret', T, raw)}", "whsec_new_secret") is None
        )
        assert (
            reason(
                bytearray(raw), f"t={T},v1={sign('whsec_new_secret', T, raw)}", "whsec_new_secret"
            )
            is None
        )
    # A str body is its UTF-8 bytes.
    text = '{"name":"Zoë"}'
    assert reason(text, f"t={T},v1={sign('whsec_new_secret', T, text)}", "whsec_new_secret") is None
    # The key is the whole secret, whsec_ prefix included.
    assert (
        reason(BODY, f"t={T},v1={sign('new_secret', T, BODY)}", "whsec_new_secret")
        == R.NO_MATCHING_SIGNATURE
    )
    # An empty secret is a configuration error, checked first.
    with pytest.raises(ValidationError):
        webhooks.verify(BODY, "", "", now=T)
    with pytest.raises(ValidationError):
        webhooks.verify(42, header, "whsec_x", now=T)


def test_construct_event() -> None:
    event = webhooks.construct_event(BODY, HEADER, "whsec_new_secret", now=T + 60)
    assert isinstance(event, WebhookTestEvent)
    assert (
        event.id == "evt_3f1c2d4e-5a6b-5c7d-8e9f-0a1b2c3d4e5f"
        and event.version == "v2"
        and not event.test
    )
    assert (
        event.created_at == datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        and event.user_uuid is None
    )
    with pytest.raises(WebhookSignatureError) as info:
        webhooks.construct_event(BODY, HEADER, "whsec_other", now=T + 60)
    assert info.value.reason == R.NO_MATCHING_SIGNATURE

    # The client's webhooks service delegates to the same functions.
    client = QBitFlow("sk_x")
    client.webhooks.verify(BODY, HEADER, "whsec_old_secret", now=T + 60)
    assert (
        client.webhooks.construct_event(BODY.encode(), HEADER, "whsec_old_secret", now=T + 60).type
        == "webhook.test"
    )
    assert client.webhooks.parse_event(BODY).type == "webhook.test"

    # A v1 body signed correctly is still refused: the endpoint must move to v2.
    v1 = '{"uuid":"pay@x","txType":"payment","status":{"status":"completed"}}'
    with pytest.raises(ValidationError) as verr:
        webhooks.construct_event(
            v1, f"t={T},v1={sign('whsec_new_secret', T, v1)}", "whsec_new_secret", now=T
        )
    assert verr.value.field_errors[0].field == "version"


def test_headers_constants() -> None:
    assert webhooks.SIGNATURE_HEADER == "QBitFlow-Signature"
    assert webhooks.EVENT_ID_HEADER == "QBitFlow-Event-Id"
    assert webhooks.EVENT_TYPE_HEADER == "QBitFlow-Event-Type"
    assert webhooks.MAX_BODY_BYTES == 1 << 20
