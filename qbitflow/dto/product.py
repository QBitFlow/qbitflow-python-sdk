"""
Product-related data models.

This module contains data models for product management operations.
"""

from typing import Any, Optional

from pydantic import Field, field_validator

from qbitflow.utils.helpers import validate_price, validate_product_text

from .base_model import GO_ZERO_TIME, Bool, Float, Int, RequestModel, ResponseModel, Str, Timestamp


def _check_text(field_name: str, value: Optional[str], max_length: int) -> Optional[str]:
    """Apply the API's ``producttext`` rule (2-``max_length`` chars, no markup) when provided."""
    if value is None:
        return value
    problem = validate_product_text(value, 2, max_length)
    if problem is not None:
        raise ValueError(f"{field_name} {problem}")
    return value


def _check_price(value: Any) -> Any:
    """A provided price must be a finite number strictly greater than 0."""
    if value is None:
        return value
    problem = validate_price(value)
    if problem is not None:
        raise ValueError(f"price {problem}")
    return value


class Product(ResponseModel):
    """
    Represents a product in the QBitFlow system.

    Products are items or services that customers can purchase through
    one-time payments or subscriptions.

    Attributes:
        id: Unique identifier for the product.
        name: Product name.
        description: Product description.
        price: Price in USD.
        reference: Your own reference for the product (auto-generated when not given).
        created_at: Timestamp when the product was created.
        is_active: Whether the product is currently active (hidden "ghost" products created
            by a session checkout are ``False`` and excluded from ``get_all``).
        test: Whether this is a test-mode product.
        organization_id: Organization that owns this product.
        user_id: User that owns this product, 0 for organization-level products.

    Example:
        >>> product = client.products.get(1)
        >>> print(f"{product.name}: ${product.price}")
        >>> print(f"Active: {product.is_active}")
    """

    id: Int = 0
    name: Str = ""
    description: Str = ""
    price: Float = 0.0
    reference: Str = ""
    created_at: Timestamp = GO_ZERO_TIME
    is_active: Bool = False
    test: Bool = False
    organization_id: Int = 0
    user_id: Int = 0


class CreateProductDto(RequestModel):
    """
    Data transfer object for creating a new product.

    Attributes:
        name: Product name (required; 2-100 characters, no markup characters).
        description: Product description (required; 2-500 characters, no markup characters).
        price: Price in USD (required, a finite number greater than 0).
        reference: Optional external reference ID for your records; auto-generated when
            omitted (or ``""``) and immutable afterwards.

    Raises:
        ValidationError: (the SDK's) if a value breaks the API's rules.

    Example:
        >>> new_product = CreateProductDto(
        ...     name="Premium Subscription",
        ...     description="Access to all premium features",
        ...     price=29.99,
        ...     reference="PROD-PREMIUM"
        ... )
        >>> product = client.products.create(new_product)
    """

    name: str = Field(..., description="Product name")
    description: str = Field(..., description="Product description")
    price: float = Field(..., description="Price in USD, must be greater than 0")
    reference: Optional[str] = Field(default=None, description="External reference ID")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _check_text("name", v, 100) or v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return _check_text("description", v, 500) or v

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: Any) -> Any:
        """Validate that price is finite and strictly positive (the API rejects 0)."""
        return _check_price(v)


class UpdateProductDto(RequestModel):
    """
    Data transfer object for updating an existing product.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields are excluded from the request entirely, so there is no
    side-effect reset. An empty ``UpdateProductDto()`` is a valid no-op. A provided field is
    validated as on create — an empty ``name`` or ``description`` is rejected.

    ``reference`` is deliberately absent: it is an immutable identifier and the API
    ignores it on update.

    Attributes:
        name: New product name, 2-100 characters, no markup characters.
        description: New product description, 2-500 characters, no markup characters.
        price: New price in USD, a finite number greater than 0.

    Example:
        >>> # change only the price; name and description are untouched
        >>> product = client.products.update(1, UpdateProductDto(price=39.99))
    """

    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, description="Price in USD, must be > 0")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return _check_text("name", v, 100)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        return _check_text("description", v, 500)

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: Any) -> Any:
        """Validate that a supplied price is finite and strictly positive."""
        return _check_price(v)
