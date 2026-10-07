"""
Configuration module for QBitFlow SDK.

Module-level defaults: the API base URL, the request timeout and the retry budget.

Base URL precedence, highest first:

1. ``QBitFlow(api_key, base_url=...)`` — per client.
2. :func:`set_base_url` — process-wide, followed by every client created without ``base_url``
   (even clients created before the call).
3. The ``QBITFLOW_BASE_URL`` environment variable, **read once when the SDK is imported**.
4. ``https://api.qbitflow.app/v1``.
"""

import os

from qbitflow.exceptions.exceptions import ValidationError

# Default base URL for QBitFlow API.
# Initialised from the QBITFLOW_BASE_URL environment variable at import time.
BASE_URL: str = os.getenv("QBITFLOW_BASE_URL", "https://api.qbitflow.app/v1")

# API version
API_VERSION: str = "v1"

# Request timeout in seconds
DEFAULT_TIMEOUT: int = 30

# Maximum retry attempts for idempotent (GET) requests that hit a network error or a 5xx.
# POST/PUT/DELETE are never retried. Exponential backoff: 1s, 2s, 4s.
MAX_RETRIES: int = 3


def set_base_url(url: str) -> None:
    """
    Set the process-wide base URL for API requests.

    Clients created without an explicit ``base_url`` follow this value, even after they were
    constructed. Prefer ``QBitFlow(api_key, base_url=...)`` when several clients with
    different targets coexist.

    Args:
        url: The base URL to use for all API requests (a trailing slash is stripped).

    Raises:
        ValidationError: If ``url`` is not a string or is blank.

    Example:
        >>> from qbitflow import config
        >>> config.set_base_url("https://staging.example.com/v1")
    """
    global BASE_URL
    if not isinstance(url, str) or not url.strip().rstrip("/"):
        raise ValidationError("base_url cannot be empty")
    BASE_URL = url.strip().rstrip("/")


def get_base_url() -> str:
    """
    Get the current base URL for API requests.

    Returns:
        The current base URL.

    Example:
        >>> from qbitflow import config
        >>> print(config.get_base_url())
        https://api.qbitflow.app/v1
    """
    return BASE_URL
