"""
Customer request handlers.

This module provides methods for managing customers via the QBitFlow API.
"""

from typing import List


from .base_request import BaseRequest, SuccessResponse
from qbitflow.dto.customer import Customer, CreateCustomerDto, UpdateCustomerDto
from qbitflow.exceptions import ValidationError


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
            ValidationError: If the provided data is invalid.
            APIError: If the API returns an error.
        
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
        res = self._make_request(f"{self.BASE_ROUTE}/", "POST", data.model_dump())
        return Customer(**res)
    
    def get(self, customer_uuid: str) -> Customer:
        """
        Get a customer by UUID.
        
        Args:
            customer_uuid: The UUID of the customer to retrieve.
        
        Returns:
            The customer with the specified UUID.
        
        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the UUID format is invalid.
        
        Example:
            >>> customer = client.customers.get("01997c89-d0e9-7c9a-9886-fe7709919695")
            >>> print(f"{customer.name} {customer.last_name}")
        """
        if not customer_uuid:
            raise ValidationError("Customer UUID cannot be empty")
        
        endpoint = f"{self.BASE_ROUTE}/uuid/{customer_uuid}"
        res = self._make_request(endpoint, "GET")
        return Customer(**res)
    
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
        if not email or "@" not in email:
            raise ValidationError("Invalid email address")
        
        endpoint = f"{self.BASE_ROUTE}/email/{email}"
        res = self._make_request(endpoint, "GET")
        return Customer(**res)
    
    def get_all(self) -> List[Customer]:
        """
        Get all customers.
        
        Returns:
            List of all customers.
        
        Raises:
            APIError: If the API returns an error.
        
        Example:
            >>> customers = client.customers.get_all()
            >>> print(f"Total customers: {len(customers)}")
            >>> for customer in customers:
            ...     print(f"- {customer.name} ({customer.email})")
        """
        # Returns a CursorData object for pagination
        res = self._make_request(f"{self.BASE_ROUTE}/all", "GET")
        items = res.get("items", [])
        return [Customer(**item) for item in items]
    
    def update(self, customer_uuid: str, data: UpdateCustomerDto) -> Customer:
        """
        Update an existing customer.
        
        Args:
            customer_uuid: The UUID of the customer to update.
            data: Customer update data.
        
        Returns:
            The updated customer.
        
        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the provided data is invalid.
        
        Example:
            >>> update_data = UpdateCustomerDto(
            ...     email="newemail@example.com",
            ...     phone_number="+9876543210"
            ... )
            >>> customer = client.customers.update("customer-uuid", update_data)
            >>> print(f"Updated customer: {customer.email}")
        """
        if not customer_uuid:
            raise ValidationError("Customer UUID cannot be empty")
        
        json_data = data.model_dump(exclude_none=True)
        json_data["uuid"] = customer_uuid
        
        res = self._make_request(f"{self.BASE_ROUTE}/", "PUT", json_data)
        return Customer(**res)
    
    def delete(self, customer_uuid: str) -> SuccessResponse:
        """
        Delete a customer.
        
        Args:
            customer_uuid: The UUID of the customer to delete.
        
        Returns:
            Success response.
        
        Raises:
            NotFoundException: If the customer is not found.
            ValidationError: If the UUID format is invalid.
        
        Example:
            >>> response = client.customers.delete("customer-uuid")
            >>> print(response.message)
        """
        if not customer_uuid:
            raise ValidationError("Customer UUID cannot be empty")
        
        endpoint = f"{self.BASE_ROUTE}/uuid/{customer_uuid}"
        res = self._make_request(endpoint, "DELETE")
        return SuccessResponse(**res)
