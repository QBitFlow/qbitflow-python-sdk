
"""
Duration utility for representing time periods.

This module provides a Duration class for specifying time periods in various units,
commonly used for subscription frequencies and trial periods.
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


TimeUnit = Literal["seconds", "minutes", "hours", "days", "weeks", "months"]


class Duration(BaseModel):
    """
    Represents a duration of time with a value and unit.
    
    This class is used throughout the SDK to specify time periods,
    particularly for subscription frequencies and trial periods.
    
    Attributes:
        value: The numeric value of the duration (must be positive).
        unit: The unit of time (seconds, minutes, hours, days, weeks, or months).
    
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
    
    value: int = Field(
        ...,
        gt=0,
        description="The numeric value of the duration (must be positive)"
    )
    unit: TimeUnit = Field(
        ...,
        description="The unit of time"
    )
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: int) -> int:
        """
        Validate that the duration value is positive.
        
        Args:
            v: The value to validate.
            
        Returns:
            The validated value.
            
        Raises:
            ValueError: If the value is not positive.
        """
        if v <= 0:
            raise ValueError("Duration value must be positive")
        return v
    
    def __str__(self) -> str:
        """Return a human-readable string representation."""
        unit_text = self.unit if self.value != 1 else self.unit.rstrip('s')
        return f"{self.value} {unit_text}"
    
    def __repr__(self) -> str:
        """Return a detailed string representation."""
        return f"Duration(value={self.value}, unit='{self.unit}')"
