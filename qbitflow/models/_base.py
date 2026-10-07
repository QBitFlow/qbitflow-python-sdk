"""
The base of every model, and the field types that implement the decoding policy.

Decoding policy (the same in every QBitFlow SDK):

* **Lenient on absence.** An absent or ``null`` value where the field is not ``Optional``
  decodes to its zero value (``""``, ``0``, ``False``, ``[]``, an empty nested model,
  :data:`ZERO_TIME`), never to an error. ``Optional`` fields decode to ``None``.
* **Strict on type.** A value of the wrong JSON type (a string for a number, a number for a
  string, an object for a list, a number for a timestamp…) fails; the client reports it as a
  :class:`~qbitflow.ServerError`. Numeric widening is allowed: an integer into a float field,
  an integral float (``2.0``) into an integer field.
* Decimal strings (amounts in a token's smallest unit) stay strings, never parsed.
* Timestamps are RFC 3339 strings with any offset, decoded to timezone-aware ``datetime``.
* Unknown keys are ignored; unknown enum values are kept as the raw ``str``.

Field names are snake_case; each has an explicit ``alias`` with the API's camelCase wire name.
``model_dump(by_alias=True)`` writes the wire names back.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any, Dict, Type, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

__all__ = ["Model", "ZERO_TIME", "Str", "Bool", "Int", "UInt", "Float", "Time", "open_enum"]

#: What a non-``Optional`` timestamp decodes to when the API leaves it out
#: (``0001-01-01T00:00:00Z``, Go's zero time). Compare against it to detect "never set".
ZERO_TIME = datetime(1, 1, 1, tzinfo=timezone.utc)


def _check_str(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise ValueError(f"expected a string, got {_json_type(value)}")


def _check_bool(value: Any) -> Any:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise ValueError(f"expected a boolean, got {_json_type(value)}")


def _check_int(value: Any) -> Any:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError("expected an integer, got a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"expected an integer, got {_json_type(value)}")


def _check_uint(value: Any) -> Any:
    number = _check_int(value)
    if number < 0:
        raise ValueError("expected a non-negative integer")
    return number


def _check_float(value: Any) -> Any:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        raise ValueError("expected a number, got a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"expected a number, got {_json_type(value)}")


_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?"
    r"(?:([Zz])|([+-])(\d{2}):(\d{2}))"
)


def parse_time(value: str) -> datetime:
    """Parse an RFC 3339 timestamp (any offset, any fraction length) into an aware datetime.

    Raises:
        ValueError: when ``value`` is not an RFC 3339 timestamp.
    """
    match = _RFC3339.fullmatch(value)
    if match is None:
        raise ValueError(f"expected an RFC 3339 timestamp, got {value!r}")
    year, month, day, hour, minute, second, fraction, zulu, sign, off_h, off_m = match.groups()
    if zulu:
        tz = timezone.utc
    else:
        offset = timedelta(hours=int(off_h), minutes=int(off_m))
        if offset >= timedelta(hours=24):
            raise ValueError(f"invalid offset in {value!r}")
        tz = timezone(-offset if sign == "-" else offset)
    micro = int((fraction or "0")[:6].ljust(6, "0"))
    return datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second), micro, tzinfo=tz
    )


def _check_time(value: Any) -> Any:
    if value is None:
        return ZERO_TIME
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("expected a timezone-aware datetime")
        return value
    if isinstance(value, str):
        return parse_time(value)
    raise ValueError(f"expected an RFC 3339 timestamp string, got {_json_type(value)}")


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, (list, tuple)):
        return "an array"
    if isinstance(value, dict):
        return "an object"
    return type(value).__name__


#: A JSON string (never coerced from a number).
Str = Annotated[str, BeforeValidator(_check_str)]
#: A JSON boolean (never coerced from a string or a number).
Bool = Annotated[bool, BeforeValidator(_check_bool)]
#: A JSON integer; an integral float (``2.0``) is accepted.
Int = Annotated[int, BeforeValidator(_check_int)]
#: A non-negative JSON integer (ids, counts).
UInt = Annotated[int, BeforeValidator(_check_uint)]
#: A JSON number, as a float.
Float = Annotated[float, BeforeValidator(_check_float)]
#: An RFC 3339 timestamp, as a timezone-aware ``datetime`` (any offset).
Time = Annotated[datetime, BeforeValidator(_check_time)]

_E = TypeVar("_E", bound=Enum)


def open_enum(enum: Type[_E]) -> BeforeValidator:
    """The validator of an open enum field (``Annotated[Union[E, str], open_enum(E)]``): a known
    value becomes the member, an unknown string is kept raw, anything else fails."""

    def validate(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, enum):
            return value
        if not isinstance(value, str):
            raise ValueError(f"expected a string, got {_json_type(value)}")
        try:
            return enum(value)
        except ValueError:
            return value

    return BeforeValidator(validate)


class Model(BaseModel):
    """Base of every model: explicit camelCase aliases, populated by name or alias, unknown keys
    ignored, ``null`` values decoded as the field's default."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        """A ``null`` means "absent": the field's default (zero value or ``None``) applies."""
        if isinstance(data, dict) and any(value is None for value in data.values()):
            return {key: value for key, value in data.items() if value is not None}
        return data

    def to_dict(self) -> Dict[str, Any]:
        """The model as the API writes it: camelCase keys, JSON-compatible values, ``None``
        fields left out."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
