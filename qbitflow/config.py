
"""
Configuration module for QBitFlow SDK.

This module contains configuration settings for the SDK including API base URLs
and other global settings.
"""

from typing import Optional
import os

# Default base URL for QBitFlow API
# Can be overridden by setting QBITFLOW_BASE_URL environment variable
BASE_URL: str = os.getenv("QBITFLOW_BASE_URL", "https://api.qbitflow.app/v1")

# API version
API_VERSION: str = "v1"

# Request timeout in seconds
DEFAULT_TIMEOUT: int = 30

# Maximum retry attempts for failed requests
MAX_RETRIES: int = 3


def set_base_url(url: str) -> None:
    """
    Set the base URL for API requests.
    
    This is useful for testing or when using a different API endpoint.
    
    Args:
        url: The base URL to use for all API requests.
        
    Example:
        >>> from qbitflow import config
        >>> config.set_base_url("http://localhost:3001")
    """
    global BASE_URL
    BASE_URL = url


def get_base_url() -> str:
    """
    Get the current base URL for API requests.
    
    Returns:
        The current base URL.
        
    Example:
        >>> from qbitflow import config
        >>> print(config.get_base_url())
        https://api.qbitflow.app
    """
    return BASE_URL
