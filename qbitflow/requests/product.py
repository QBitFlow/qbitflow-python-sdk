"""
Product request handlers.

This module provides methods for managing products via the QBitFlow API.
"""

from typing import List

from qbitflow.dto import product as dto

from .base_request import BaseRequest, SuccessResponse


class ProductRequests(BaseRequest):
    """
    Handler for product-related API requests.

    Examples:
        >>> product = client.products.create(
        ...     CreateProductDto(name="Premium", description="All features", price=29.99)
        ... )
        >>> client.products.update(product.id, UpdateProductDto(price=39.99))
    """

    BASE_ROUTE = "/product"

    def create(self, data: dto.CreateProductDto) -> dto.Product:
        """
        Create a new product.

        Args:
            data: Product creation data.

        Returns:
            The created product.

        Raises:
            ValidationError: If the API rejects the data (400), e.g. a duplicate reference.
        """
        return self._request_model(
            dto.Product, f"{self.BASE_ROUTE}/", "POST", self._body(dto.CreateProductDto, data)
        )

    def get(self, product_id: int) -> dto.Product:
        """
        Get a product by ID (active or hidden).

        Args:
            product_id: Numeric product ID.

        Raises:
            ValidationError: If ``product_id`` is not a positive integer.
            NotFoundException: If the product does not exist or is not yours.
        """
        self._require_positive_id(product_id, "product_id")

        return self._request_model(dto.Product, f"{self.BASE_ROUTE}/id/{product_id}")

    def get_all(self) -> List[dto.Product]:
        """
        Get all active products in the caller's scope.

        Hidden ("ghost") products created by session checkouts are excluded; fetch them by
        id or reference instead.
        """
        return self._request_list(dto.Product, f"{self.BASE_ROUTE}/")

    def get_by_reference(self, reference: str) -> dto.Product:
        """
        Get a product by reference code.

        Args:
            reference: Your own product reference.

        Raises:
            ValidationError: If ``reference`` is empty.
            NotFoundException: If no product with that reference is yours. The API currently
                cannot route a reference containing ``/`` (it is escaped correctly, but the
                lookup answers 404).
        """
        self._require_identifier(reference, "reference")

        endpoint = f"{self.BASE_ROUTE}/reference/{self._escape_path(reference)}"
        return self._request_model(dto.Product, endpoint)

    def update(self, product_id: int, data: dto.UpdateProductDto) -> dto.Product:
        """
        Update an existing product (partial update).

        Args:
            product_id: Numeric product ID.
            data: Fields to change; unset fields are left unchanged.

        Raises:
            ValidationError: If ``product_id`` is not a positive integer or the API rejects
                the data.
            NotFoundException: If the product does not exist or is not yours.
        """
        self._require_positive_id(product_id, "product_id")

        endpoint = f"{self.BASE_ROUTE}/{product_id}"
        # Partial update: unset fields must be omitted, not sent as null.
        body = self._body(dto.UpdateProductDto, data)
        return self._request_model(dto.Product, endpoint, "PUT", body)

    def delete(self, product_id: int) -> SuccessResponse:
        """
        Delete a product (soft delete).

        Args:
            product_id: Numeric product ID.

        Raises:
            ValidationError: If ``product_id`` is not a positive integer.
            NotFoundException: If the product does not exist or is not yours.
        """
        self._require_positive_id(product_id, "product_id")

        return self._request_model(SuccessResponse, f"{self.BASE_ROUTE}/{product_id}", "DELETE")
