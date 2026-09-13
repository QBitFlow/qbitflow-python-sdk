"""
Product request handlers.

This module provides methods for managing products via the QBitFlow API.
"""

from typing import List

from qbitflow.dto import product as dto
from qbitflow.exceptions import ValidationError

from .base_request import BaseRequest, SuccessResponse


class ProductRequests(BaseRequest):
    """Handler for product-related API requests."""

    BASE_ROUTE = "/product"

    def create(self, data: dto.CreateProductDto) -> dto.Product:
        """Create a new product."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "POST", data.model_dump())
        return dto.Product(**res)

    def get(self, product_id: int) -> dto.Product:
        """Get a product by ID."""
        if product_id <= 0:
            raise ValidationError("Product ID must be positive")

        endpoint = f"{self.BASE_ROUTE}/id/{product_id}"
        res = self._make_request(endpoint, "GET")
        return dto.Product(**res)

    def get_all(self) -> List[dto.Product]:
        """Get all products."""
        res = self._make_request(f"{self.BASE_ROUTE}/", "GET")
        return [dto.Product(**product) for product in res]

    def get_by_reference(self, reference: str) -> dto.Product:
        """Get a product by reference code."""
        if not reference:
            raise ValidationError("Reference cannot be empty")

        endpoint = f"{self.BASE_ROUTE}/reference/{reference}"
        res = self._make_request(endpoint, "GET")
        return dto.Product(**res)

    def update(self, product_id: int, data: dto.UpdateProductDto) -> dto.Product:
        """Update an existing product."""
        if product_id <= 0:
            raise ValidationError("Product ID must be positive")

        endpoint = f"{self.BASE_ROUTE}/{product_id}"
        res = self._make_request(endpoint, "PUT", data.model_dump())
        return dto.Product(**res)

    def delete(self, product_id: int) -> SuccessResponse:
        """Delete a product."""
        if product_id <= 0:
            raise ValidationError("Product ID must be positive")

        endpoint = f"{self.BASE_ROUTE}/{product_id}"
        res = self._make_request(endpoint, "DELETE")
        return SuccessResponse(**res)
