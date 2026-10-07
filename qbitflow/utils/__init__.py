"""
Utility modules for QBitFlow SDK.

This package contains utility classes and functions used throughout the SDK.

``CursorData`` and ``Duration`` are models built on :mod:`qbitflow.dto.base_model`, which itself
uses :mod:`qbitflow.utils.helpers`; they are therefore imported lazily to keep the package free
of import cycles.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - static typing only
    from .cursor_data import CursorData
    from .duration import Duration

__all__ = ["Duration", "CursorData"]


def __getattr__(name: str) -> Any:
    if name == "CursorData":
        from .cursor_data import CursorData

        return CursorData
    if name == "Duration":
        from .duration import Duration

        return Duration
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
