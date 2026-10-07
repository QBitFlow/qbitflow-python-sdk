"""
Customer request handlers.

This module provides methods for managing customers via the QBitFlow API.
"""

from typing import Optional

from qbitflow.dto.customer import CreateCustomerDto, Customer, UpdateCustomerDto
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder

from .base_request import BaseRequest, SuccessResponse


class CustomerRequests(BaseRequest):
    """
    Handler for customer-related API requests.

    This class provides methods to create, retrieve, update, and delete customers.

    Examples:
        >>> # Create a new customer
        >>> customer_data = CreateCustomerDto(
        ...     name="John",
        ...     last_name="Doe",
        ...     email="john@example.com"
        ... )
        >>> customer = client.customers.create(customer_data)
        >>>
        >>> # Get customer by UUID
        >>> customer = client.customers.get("customer-uuid")
        >>>
        >>> # Get all customers
        >>> customers = client.customers.get_all()
    """

    BASE_ROUTE = "/customer"

    def create(self, data: CreateCustomerDto) -> Customer:
        """
        Create a new customer.

        Args:
            data: Customer creation data.

        Returns:
            The created customer.

        Raises:
            ValidationError: If a field breaks the API's rules (checked locally) or the API
                rejects the data (400), e.g. a duplicate email or reference.

        Example:
            >>> customer_data = CreateCustomerDto(
            ...     name="John",
            ...     last_name="Doe",
            ...     email="john@example.com",
            ...     phone_number="+1234567890"
            ... )
            >>> customer = client.customers.create(customer_data)
            >>> print(f"Created customer: {customer.uuid}")
        """
        return self._request_model(
            Customer, f"{self.BASE_ROUTE}/", "POST", self._body(CreateCustomerDto, data)
        )

    def get(self, customer_uuid: str) -> Customer:
        """
        Get a customer by UUID.

        Args:
            customer_uuid: The UUID of the customer to retrieve.

        Returns:
            The customer with the specified UUID.

        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the UUID is empty.

        Example:
            >>> customer = client.customers.get("01997c89-d0e9-7c9a-9886-fe7709919695")
            >>> print(f"{customer.name} {customer.last_name}")
        """
        self._require_identifier(customer_uuid, "customer_uuid")

        endpoint = f"{self.BASE_ROUTE}/uuid/{self._escape_path(customer_uuid)}"
        return self._request_model(Customer, endpoint)

    def get_by_reference(self, reference: str) -> Customer:
        """
        Get a customer by the reference you assigned when creating it.

        Lets you resolve a customer from your own identifier without storing
        QBitFlow's UUID.

        Args:
            reference: The customer reference.

        Returns:
            The customer with the specified reference.

        Raises:
            NotFoundException: If no customer with that reference is found.
            ValidationError: If the reference is empty.

        Example:
            >>> customer = client.customers.get_by_reference("CRM-12345")
            >>> print(f"Customer UUID: {customer.uuid}")
        """
        self._require_identifier(reference, "reference")

        endpoint = f"{self.BASE_ROUTE}/reference/{self._escape_path(reference)}"
        return self._request_model(Customer, endpoint)

    def get_by_email(self, email: str) -> Customer:
        """
        Get a customer by email address.

        Args:
            email: The email address of the customer to retrieve.

        Returns:
            The customer with the specified email.

        Raises:
            NotFoundException: If no customer with that email is found.
            ValidationError: If the email format is invalid.

        Example:
            >>> customer = client.customers.get_by_email("john@example.com")
            >>> print(f"Customer UUID: {customer.uuid}")
        """
        self._require_email(email)

        endpoint = f"{self.BASE_ROUTE}/email/{self._escape_path(email)}"
        return self._request_model(Customer, endpoint)

    def get_all(
        self, limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> CursorData[Customer, str]:
        """
        Get all customers (cursor-paginated).

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from a previous response.

        Returns:
            One page of customers.

        Raises:
            ValidationError: If ``limit`` is not a positive integer.

        Example:
            >>> customers = client.customers.get_all()
            >>> print(f"Total customers: {len(customers)}")
            >>> for customer in customers.items:
            ...     print(f"- {customer.name} ({customer.email})")
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)

        return self._request_model(
            CursorData[Customer, str], f"{self.BASE_ROUTE}/all", params=params
        )

    def update(self, customer_uuid: str, data: UpdateCustomerDto) -> Customer:
        """
        Update an existing customer (partial update).

        Args:
            customer_uuid: The UUID of the customer to update.
            data: Customer update data; unset fields are left unchanged.

        Returns:
            The updated customer.

        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the UUID is empty or the API rejects the data.

        Example:
            >>> update_data = UpdateCustomerDto(
            ...     email="newemail@example.com",
            ...     phone_number="+9876543210"
            ... )
            >>> customer = client.customers.update("customer-uuid", update_data)
            >>> print(f"Updated customer: {customer.email}")
        """
        self._require_identifier(customer_uuid, "customer_uuid")

        # Partial update: unset (and "") fields are omitted, not sent as null.
        json_data = self._body(UpdateCustomerDto, data)

        return self._request_model(
            Customer, f"{self.BASE_ROUTE}/{self._escape_path(customer_uuid)}", "PUT", json_data
        )

    def delete(self, customer_uuid: str) -> SuccessResponse:
        """
        Delete a customer (soft delete).

        Args:
            customer_uuid: The UUID of the customer to delete.

        Returns:
            Success response.

        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the UUID is empty.

        Example:
            >>> response = client.customers.delete("customer-uuid")
            >>> print(response.message)
        """
        self._require_identifier(customer_uuid, "customer_uuid")

        endpoint = f"{self.BASE_ROUTE}/uuid/{self._escape_path(customer_uuid)}"
        return self._request_model(SuccessResponse, endpoint, "DELETE")
