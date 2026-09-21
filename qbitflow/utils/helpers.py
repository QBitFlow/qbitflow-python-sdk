"""
Helper functions for the QBitFlow SDK.

This module contains utility functions for string manipulation and data conversion.
"""

import re
from typing import Any, Dict, List, Optional, Union


def camel_to_snake_case(camel_str: str) -> str:
    """
    Convert a camel case string to snake case.

    Args:
        camel_str: String in camelCase format.

    Returns:
        String in snake_case format.

    Examples:
        >>> camel_to_snake_case("customerUUID")
        'customer_uuid'
        >>> camel_to_snake_case("productName")
        'product_name'
    """
    # Insert an underscore before any uppercase letter that follows a lowercase letter
    snake_str = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", camel_str)
    # Insert an underscore before any uppercase letter that follows a lowercase or uppercase letter
    snake_str = re.sub("([a-z0-9])([A-Z])", r"\1_\2", snake_str)
    return snake_str.lower()


def snake_to_camel_case(snake_str: str) -> str:
    """
    Convert a snake case string to camel case.

    Args:
        snake_str: String in snake_case format.

    Returns:
        String in camelCase format.

    Examples:
        >>> snake_to_camel_case("customer_uuid")
        'customerUUID'
        >>> snake_to_camel_case("product_name")
        'productName'
    """
    components = snake_str.split("_")
    # Capitalize the first letter of each component except the first one
    result = components[0] + "".join(x.title() for x in components[1:])

    # Special handling: convert 'Uuid' at the end to 'UUID'
    result = re.sub(r"Uuid$", "UUID", result)
    return result


def convert_dict_keys_to_snake_case(data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Recursively convert all dictionary keys from camel case to snake case.

    This function traverses nested dictionaries and lists, converting all
    dictionary keys to snake_case format.

    Args:
        data: Dictionary, list, or other data structure to convert.

    Returns:
        Data structure with all dictionary keys converted to snake case.

    Examples:
        >>> data = {"customerUUID": "123", "productName": "Test"}
        >>> convert_dict_keys_to_snake_case(data)
        {'customer_uuid': '123', 'product_name': 'Test'}
    """
    if isinstance(data, dict):
        return {
            camel_to_snake_case(key): convert_dict_keys_to_snake_case(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [convert_dict_keys_to_snake_case(item) for item in data]
    else:
        return data


def validate_uuid(uuid: str) -> bool:
    """
    Validate that a string is a valid UUID.

    Args:
        uuid: String to validate.

    Returns:
        True if the string is a valid UUID, False otherwise.

    Examples:
        >>> validate_uuid("01997c89-d0e9-7c9a-9886-fe7709919695")
        True
        >>> validate_uuid("invalid-uuid")
        False
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid))


def validate_url(url: str) -> bool:
    """
    Validate that a string is a valid URL.

    Args:
        url: String to validate.

    Returns:
        True if the string is a valid URL, False otherwise.

    Examples:
        >>> validate_url("https://example.com/webhook")
        True
        >>> validate_url("not a url")
        False
    """
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(url_pattern.match(url))


#: Characters the API's ``producttext`` rule rejects (common XSS / injection payloads).
PRODUCT_TEXT_DISALLOWED = '<>{}[]`\\|;"~^'


def validate_product_text(value: str, min_length: int, max_length: int) -> Optional[str]:
    """
    Mirror the API's ``producttext`` binding rule.

    Accepts letters (including accented and non-Latin), digits, spaces and ordinary
    punctuation; rejects angle brackets and other markup characters. Text that merely looks
    script-like (for example the literal ``javascript:alert(1)``) is allowed - the server
    renders these fields as escaped text.

    Args:
        value: The text to check.
        min_length: Minimum length, in characters.
        max_length: Maximum length, in characters.

    Returns:
        ``None`` when the value is acceptable, otherwise a message describing the problem.

    Examples:
        >>> validate_product_text("Premium Plan", 2, 100) is None
        True
        >>> validate_product_text("<script>", 2, 100) is None
        False
    """
    if not value or not value.strip():
        return "must not be blank"

    if len(value) < min_length or len(value) > max_length:
        return f"must be between {min_length} and {max_length} characters"

    for char in value:
        if char in PRODUCT_TEXT_DISALLOWED:
            return f"must not contain the character {char!r}"
        # Reject control characters, but allow the common whitespace ones.
        if ord(char) < 32 and char not in "\n\r\t":
            return "must not contain control characters"

    return None
