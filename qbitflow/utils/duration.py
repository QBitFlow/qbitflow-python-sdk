"""
Duration utility for representing time periods.

This module provides a Duration class for specifying time periods in various units,
commonly used for subscription frequencies and trial periods.
"""

from typing import Any, Literal

from pydantic import field_validator

from qbitflow.dto.base_model import RequestModel
from qbitflow.utils.helpers import MAX_UINT32, validate_integer

TimeUnit = Literal["seconds", "minutes", "hours", "days", "weeks", "months", "years"]


class Duration(RequestModel):
    """
    Represents a duration of time with a value and unit.

    This class is used throughout the SDK to specify time periods, particularly for
    subscription frequencies and trial periods.

    Attributes:
        value: The numeric value of the duration, an integer from 0 to 4294967295. A
            subscription ``frequency`` must be at least 1; a ``trial_period`` may be 0.
        unit: The unit of time (seconds, minutes, hours, days, weeks, months or years).

    Raises:
        ValidationError: (the SDK's) if ``value`` is not an integer in range or ``unit`` is
            not one of the supported units.

    Examples:
        >>> # One month duration
        >>> duration = Duration(value=1, unit="months")
        >>>
        >>> # Two weeks trial period
        >>> trial = Duration(value=2, unit="weeks")
        >>>
        >>> # Daily subscription
        >>> daily = Duration(value=1, unit="days")
    """

    value: int
    unit: TimeUnit

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, v: Any) -> Any:
        """Accept only integers from 0 to 4294967295 (the API's ``uint32``)."""
        problem = validate_integer(v, 0, MAX_UINT32)
        if problem is not None:
            raise ValueError(f"Duration value {problem}")
        return v

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        unit_text = self.unit if self.value != 1 else self.unit.rstrip("s")
        return f"{self.value} {unit_text}"

    def __repr__(self) -> str:
        """Return a detailed string representation."""
        return f"Duration(value={self.value}, unit='{self.unit}')"
