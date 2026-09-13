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

    name: str = Field(..., min_length=1, description="Product name")
    description: str = Field(..., min_length=1, description="Product description")
    price: float = Field(..., ge=0, description="Price in USD")
    reference: Optional[str] = Field(default=None, description="External reference ID")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Validate that price is non-negative."""
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v


class UpdateProductDto(BaseModel):
    """
    Data transfer object for updating an existing product.

    Attributes:
        name: New product name (required).
        description: New product description (required).
        price: New price in USD (required, must be non-negative).

    Example:
        >>> update_data = UpdateProductDto(
        ...     name="Premium Plus Subscription",
        ...     description="Updated description",
        ...     price=39.99
        ... )
        >>> product = client.products.update(1, update_data)
    """

    name: str = Field(..., min_length=1, description="Product name")
    description: str = Field(..., min_length=1, description="Product description")
    price: float = Field(..., ge=0, description="Price in USD")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Validate that price is non-negative."""
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v
