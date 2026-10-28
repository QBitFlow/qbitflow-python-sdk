"""Compatibility shims across the supported Python versions (3.10+)."""

import sys
from enum import Enum

if sys.version_info >= (3, 11):  # pragma: no cover - depends on the interpreter
    from enum import StrEnum
else:  # pragma: no cover - depends on the interpreter

    class StrEnum(str, Enum):
        """``enum.StrEnum`` for Python 3.10: members are strings, ``str(member)`` is the value."""

        def __str__(self) -> str:
            return str(self.value)


__all__ = ["StrEnum"]
