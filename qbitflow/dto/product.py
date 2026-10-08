"""
Product-related data models.

This module contains data models for product management operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from .base_model import BaseModel


class Product(BaseModel):
    """
    Represents a product in the QBitFlow system.

    Products are items or services that customers can purchase through
    one-time payments or subscriptions.

    Attributes:
        id: Unique identifier for the product.
        name: Product name.
        description: Product description.
        price: Price in USD.
        reference: Optional external reference ID for your records.
        created_at: Timestamp when the product was created.
        is_active: Whether the product is currently active.

    Example:
        >>> product = client.products.get(1)
        >>> print(f"{product.name}: ${product.price}")
        >>> print(f"Active: {product.is_active}")
    """

    id: int = Field(..., description="Unique identifier for the product")
    name: str = Field(..., description="Product name")
    description: str = Field(..., description="Product description")
    price: float = Field(..., ge=0, description="Price in USD")
    reference: Optional[str] = Field(default=None, description="External reference ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Whether the product is active")
    test: bool = Field(
        default=False,
        description="Whether this is a test-mode product (test and live are isolated)",
    )
    organization_id: int = Field(default=0, description="Organization that owns this product")
    user_id: int = Field(
        default=0, description="User that owns this product, 0 for organization-level products"
    )


class CreateProductDto(BaseModel):
    """
    Data transfer object for creating a new product.

    Attributes:
        name: Product name (required).
        description: Product description (required).
        price: Price in USD (required, must be non-negative).
        reference: Optional external reference ID for your records.

    Example:
        >>> new_product = CreateProductDto(
        ...     name="Premium Subscription",
        ...     description="Access to all premium features",
        ...     price=29.99,
        ...     reference="PROD-PREMIUM"
        ... )
        >>> product = client.products.create(new_product)
    """

    name: str = Field(..., min_length=2, max_length=100, description="Product name")
    description: str = Field(..., min_length=2, max_length=500, description="Product description")
    price: float = Field(..., gt=0, description="Price in USD, must be greater than 0")
    reference: Optional[str] = Field(default=None, description="External reference ID")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Validate that price is strictly positive (the API rejects 0 and negatives)."""
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return v


class UpdateProductDto(BaseModel):
    """
    Data transfer object for updating an existing product.

    Updates are **partial**: every field is optional and any field you leave unset keeps
    its stored value. Unset fields are excluded from the request entirely, so there is no
    side-effect reset. An empty ``UpdateProductDto()`` is a valid no-op.

    ``reference`` is deliberately absent: it is an immutable identifier and the API
    ignores it on update.

    Attributes:
        name: New product name, 2-100 characters.
        description: New product description, 2-500 characters.
        price: New price in USD, must be greater than 0.

    Example:
        >>> # change only the price; name and description are untouched
        >>> product = client.products.update(1, UpdateProductDto(price=39.99))
    """

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, min_length=2, max_length=500)
    price: Optional[float] = Field(default=None, gt=0, description="Price in USD, must be > 0")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[float]) -> Optional[float]:
        """Validate that a supplied price is strictly positive."""
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        return v
