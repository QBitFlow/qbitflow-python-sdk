
"""
Customer-related data models.

This module contains data models for customer management operations.
"""

from datetime import datetime
from typing import Optional
from pydantic import Field, EmailStr

from .base_model import BaseModel


class Customer(BaseModel):
    """
    Represents a customer in the QBitFlow system.
    
    Customers are individuals or entities that make payments through your platform.
    Each customer has a unique UUID and contact information.
    
    Attributes:
        uuid: Unique identifier for the customer.
        name: Customer's first name.
        last_name: Customer's last name.
        email: Customer's email address.
        phone_number: Optional phone number.
        address: Optional physical address.
        reference: Optional external reference ID for your records.
        created_at: Timestamp when the customer was created.
    
    Example:
        >>> customer = client.customers.get("customer-uuid")
        >>> print(f"{customer.name} {customer.last_name}")
        >>> print(f"Email: {customer.email}")
    """
    
    uuid: str = Field(..., description="Unique identifier for the customer")
    name: str = Field(..., description="Customer's first name")
    last_name: str = Field(..., description="Customer's last name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
    reference: Optional[str] = Field(default=None, description="External reference ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateCustomerDto(BaseModel):
    """
    Data transfer object for creating a new customer.
    
    Use this model to provide customer information when creating a new customer.
    
    Attributes:
        name: Customer's first name (required).
        last_name: Customer's last name (required).
        email: Customer's email address (required).
        phone_number: Optional phone number.
        address: Optional physical address.
        reference: Optional external reference ID for your records.
    
    Example:
        >>> new_customer = CreateCustomerDto(
        ...     name="John",
        ...     last_name="Doe",
        ...     email="john@example.com",
        ...     phone_number="+1234567890",
        ...     reference="CRM-12345"
        ... )
        >>> customer = client.customers.create(new_customer)
    """
    
    name: str = Field(..., min_length=1, description="Customer's first name")
    last_name: str = Field(..., min_length=1, description="Customer's last name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
    reference: Optional[str] = Field(default=None, description="External reference ID")


class UpdateCustomerDto(BaseModel):
    """
    Data transfer object for updating an existing customer.
    
    All fields are optional - only provide the fields you want to update.
    
    Attributes:
        name: New first name.
        last_name: New last name.
        email: New email address.
        phone_number: New phone number.
        address: New physical address.
    
    Example:
        >>> update_data = UpdateCustomerDto(
        ...     email="newemail@example.com",
        ...     phone_number="+9876543210"
        ... )
        >>> customer = client.customers.update("customer-uuid", update_data)
    """
    
    name: Optional[str] = Field(..., min_length=1, description="Customer's first name")
    last_name: Optional[str] = Field(..., min_length=1, description="Customer's last name")
    email: Optional[EmailStr] = Field(..., description="Customer's email address")
    phone_number: Optional[str] = Field(default=None, description="Customer's phone number")
    address: Optional[str] = Field(default=None, description="Customer's physical address")
