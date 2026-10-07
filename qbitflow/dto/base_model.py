"""
Base models for all DTOs in the QBitFlow SDK.

Three bases live here:

* :class:`BaseModel` — the common configuration: automatic camelCase aliases (``customer_uuid``
  ↔ ``customerUUID``), population by field name or alias, and ``model_dump`` /
  ``model_dump_json`` that emit the API's camelCase keys by default.
* :class:`ResponseModel` — every model the API sends back. It decodes the way Go's
  ``encoding/json`` does on the server side:

  - a field that is **absent or null** where the Go type is not a pointer decodes to its zero
    value (``0``, ``""``, ``False``, ``[]``, a zero-valued nested object, or the Go zero time
    ``0001-01-01T00:00:00Z``) — never an error, never ``None``;
  - a field whose Go type is a pointer is ``Optional`` and decodes to ``None`` when absent;
  - a field that is present with the **wrong JSON type** (a string where a number is expected,
    an object where a string is expected, …) fails validation; the request layer reports that
    as :class:`~qbitflow.exceptions.ServerError` carrying the HTTP status. Harmless numeric
    widening is accepted (a JSON integer into a float field, an integral float into an int
    field);
  - unknown keys are ignored.

* :class:`RequestModel` — every request DTO. Its validation failures raise the SDK's
  :class:`~qbitflow.exceptions.ValidationError` (with per-field ``fields``), never pydantic's own
  exception, so ``except qbitflow.exceptions.ValidationError`` covers a value rejected locally
  and the same value rejected by the API.
"""

import types
from datetime import datetime, timezone
from typing import (
    Annotated,
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

import pydantic
from pydantic import BaseModel as PydanticBaseModel
from pydantic import BeforeValidator, ConfigDict, Strict, model_validator

from qbitflow.exceptions.exceptions import FieldError, ValidationError
from qbitflow.utils.helpers import snake_to_camel_case

#: Go's zero ``time.Time`` (``0001-01-01T00:00:00Z``): what a non-pointer timestamp decodes to
#: when the API has not set it. Compare against it to detect "never happened".
GO_ZERO_TIME = datetime(1, 1, 1, tzinfo=timezone.utc)


# ── Strictly-typed field types for responses ─────────────────────────────────


def _require_int(value: Any) -> Any:
    """Accept an integer (or an integral float); reject booleans, strings and the rest."""
    if isinstance(value, bool):
        raise ValueError("expected an integer, got a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"expected an integer, got {type(value).__name__}")


def _require_number(value: Any) -> Any:
    """Accept any JSON number; reject booleans, strings and the rest."""
    if isinstance(value, bool):
        raise ValueError("expected a number, got a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"expected a number, got {type(value).__name__}")


def _require_timestamp(value: Any) -> Any:
    """Accept an RFC 3339 string (or a ``datetime``); reject numbers and the rest."""
    if isinstance(value, (str, datetime)):
        return value
    raise ValueError(f"expected an RFC 3339 timestamp string, got {type(value).__name__}")


#: A JSON string (no coercion from numbers).
Str = Annotated[str, Strict()]
#: A JSON boolean (no coercion from strings or numbers).
Bool = Annotated[bool, Strict()]
#: A JSON integer; an integral float is accepted.
Int = Annotated[int, BeforeValidator(_require_int)]
#: A JSON number, as a float.
Float = Annotated[float, BeforeValidator(_require_number)]
#: An RFC 3339 timestamp string, as a timezone-aware ``datetime``.
Timestamp = Annotated[datetime, BeforeValidator(_require_timestamp)]


def _is_nullable(annotation: Any) -> bool:
    """Whether ``None`` is a legitimate value for a field of this annotation."""
    if annotation is None or annotation is type(None) or annotation is Any:
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        return _is_nullable(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        return any(_is_nullable(arg) for arg in get_args(annotation))
    return False


class BaseModel(PydanticBaseModel):
    """
    Base model with the common configuration for all DTOs.

    Features:
        - camelCase aliases generated from snake_case field names (``customer_uuid`` ↔
          ``customerUUID``)
        - fields may be populated by either name
        - ``model_dump()`` / ``model_dump_json()`` emit camelCase keys unless
          ``by_alias=False`` is passed
    """

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both camelCase and snake_case
        alias_generator=snake_to_camel_case,  # Generate camelCase aliases
    )

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """Serialize to a dictionary, with the API's camelCase keys by default."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs: Any) -> str:
        """Serialize to JSON, with the API's camelCase keys by default."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)


class ResponseModel(BaseModel):
    """
    Base for every model the API returns (see the module docstring for the decoding policy).

    Every non-``Optional`` field declares its zero value as default, so an absent key decodes to
    it; the ``mode="before"`` validator below drops explicit ``null`` values for those fields so
    the same default applies.
    """

    _qbf_non_nullable: ClassVar[Dict[type, FrozenSet[str]]] = {}

    @classmethod
    def _non_nullable_keys(cls) -> FrozenSet[str]:
        """Every key (field name and aliases) whose field does not accept ``None``."""
        cached = ResponseModel._qbf_non_nullable.get(cls)
        if cached is not None:
            return cached

        keys = set()
        for name, field in cls.model_fields.items():
            if _is_nullable(field.annotation):
                continue
            keys.add(name)
            if field.alias:
                keys.add(field.alias)
            choices = getattr(field.validation_alias, "choices", None)
            if choices:
                keys.update(choice for choice in choices if isinstance(choice, str))
            elif isinstance(field.validation_alias, str):
                keys.add(field.validation_alias)

        frozen = frozenset(keys)
        ResponseModel._qbf_non_nullable[cls] = frozen
        return frozen

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls_for_non_nullable_fields(cls, data: Any) -> Any:
        """A ``null`` for a non-pointer Go field means its zero value: let the default apply."""
        if not isinstance(data, dict):
            return data
        non_nullable = cls._non_nullable_keys()
        if not any(value is None and key in non_nullable for key, value in data.items()):
            return data
        return {
            key: value for key, value in data.items() if not (value is None and key in non_nullable)
        }


def validation_error_from_pydantic(
    exc: pydantic.ValidationError, fallback: str = "invalid parameters"
) -> ValidationError:
    """Convert a pydantic failure into the SDK's :class:`ValidationError`, one field each."""
    fields: List[FieldError] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "")).removeprefix("Value error, ")
        fields.append(FieldError(field=loc, message=message))

    return ValidationError("; ".join(str(field) for field in fields) or fallback, fields=fields)


_RequestT = TypeVar("_RequestT", bound="RequestModel")


class RequestModel(BaseModel):
    """
    Base for every request DTO.

    Validation runs on construction (and again when the DTO is handed to a request method, so
    a value assigned after construction is still checked). A rejected value raises the SDK's
    :class:`~qbitflow.exceptions.ValidationError` with one :class:`FieldError` per offending
    field — never ``pydantic.ValidationError``.
    """

    model_config = ConfigDict(revalidate_instances="always")

    def __init__(self, /, **data: Any) -> None:
        try:
            super().__init__(**data)
        except pydantic.ValidationError as exc:
            raise validation_error_from_pydantic(exc, f"invalid {type(self).__name__}") from exc

    @classmethod
    def model_validate(cls: Type[_RequestT], obj: Any, **kwargs: Any) -> _RequestT:
        """Validate ``obj`` (a mapping or an instance), raising the SDK's ValidationError."""
        try:
            return super().model_validate(obj, **kwargs)
        except pydantic.ValidationError as exc:
            raise validation_error_from_pydantic(exc, f"invalid {cls.__name__}") from exc

    @classmethod
    def model_validate_json(cls: Type[_RequestT], json_data: Any, **kwargs: Any) -> _RequestT:
        """Validate a JSON document, raising the SDK's ValidationError."""
        try:
            return super().model_validate_json(json_data, **kwargs)
        except pydantic.ValidationError as exc:
            raise validation_error_from_pydantic(exc, f"invalid {cls.__name__}") from exc

    def to_body(self) -> Dict[str, Any]:
        """
        The JSON body for this DTO: camelCase keys, unset (``None``) fields omitted and empty
        optional strings omitted (the API treats ``""`` as "not provided").
        """
        body = self.model_dump(exclude_none=True, by_alias=True)
        return {key: value for key, value in body.items() if value != ""}
