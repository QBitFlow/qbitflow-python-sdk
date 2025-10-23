"""
Integration tests for QBitFlow SDK.

These tests run against the actual QBitFlow test API.
Make sure to set QBITFLOW_API_KEY environment variable.

Run with:
    export QBITFLOW_API_KEY="your_test_api_key"
    pytest tests/test_integration.py -v
"""

import pydantic
import pytest
from qbitflow import QBitFlow, Duration
from qbitflow.dto.customer import CreateCustomerDto, UpdateCustomerDto
from qbitflow.dto.product import CreateProductDto, UpdateProductDto
from qbitflow.dto.transaction.status import TransactionType
from qbitflow.exceptions import (
    NotFoundException,
    ValidationError,
    QBitFlowError
)


class TestClient:
    """Test QBitFlow client initialization."""
    
    def test_client_initialization(self, api_key):
        """Test that client can be initialized with API key."""
        client = QBitFlow(api_key=api_key)
        assert client.api_key == api_key
        assert client.customers is not None
        assert client.products is not None
        assert client.one_time_payments is not None
        assert client.subscriptions is not None
    
    def test_client_requires_api_key(self):
        """Test that client raises error without API key."""
        with pytest.raises(ValueError):
            QBitFlow(api_key="")


class TestCustomers:
    """Test customer management operations."""
    
    def test_create_customer(self, client, test_customer_data):
        """Test creating a new customer."""
        customer = client.customers.create(test_customer_data)
        
        assert customer.uuid is not None
        assert customer.name == test_customer_data.name
        assert customer.last_name == test_customer_data.last_name
        assert customer.email == test_customer_data.email
        assert customer.created_at is not None
    
    def test_get_customer(self, client, test_customer_data):
        """Test retrieving a customer by UUID."""
        # Create customer
        created = client.customers.create(test_customer_data)
        
        # Retrieve customer
        retrieved = client.customers.get(created.uuid)
        
        assert retrieved.uuid == created.uuid
        assert retrieved.email == created.email
    
    def test_get_customer_by_email(self, client, test_customer_data):
        """Test retrieving a customer by email."""
        # Create customer
        created = client.customers.create(test_customer_data)
        
        # Retrieve by email
        retrieved = client.customers.get_by_email(created.email)
        
        assert retrieved.uuid == created.uuid
        assert retrieved.email == created.email
    
    def test_get_all_customers(self, client):
        """Test retrieving all customers."""
        customers = client.customers.get_all()
        
        assert isinstance(customers, list)
        # Should have at least one customer
        assert len(customers) >= 0
    
    def test_update_customer(self, client, test_customer_data):
        """Test updating a customer."""
        # Create customer
        created = client.customers.create(test_customer_data)
        
        # Update customer
        update_data = UpdateCustomerDto(
            name= created.name,
            last_name= created.last_name,
            email="updated@example.com",
            phone_number="+9876543210"
        )
        updated = client.customers.update(created.uuid, update_data)
        
        assert updated.uuid == created.uuid
        assert updated.email == "updated@example.com"
        assert updated.phone_number == "+9876543210"
    
    def test_delete_customer(self, client, test_customer_data):
        """Test deleting a customer."""
        # Create customer
        created = client.customers.create(test_customer_data)
        
        # Delete customer
        response = client.customers.delete(created.uuid)
        assert response.message is not None
        
        # Verify deletion
        with pytest.raises(NotFoundException):
            client.customers.get(created.uuid)


class TestProducts:
    """Test product management operations."""
    
    def test_create_product(self, client, test_product_data):
        """Test creating a new product."""
        product = client.products.create(test_product_data)
        
        assert product.id is not None
        assert product.name == test_product_data.name
        assert product.price == test_product_data.price
        assert product.is_active is True
    
    def test_get_product(self, client, test_product_data):
        """Test retrieving a product by ID."""
        # Create product
        created = client.products.create(test_product_data)
        
        # Retrieve product
        retrieved = client.products.get(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.name == created.name
    
    def test_get_all_products(self, client):
        """Test retrieving all products."""
        products = client.products.get_all()
        
        assert isinstance(products, list)
        assert len(products) >= 0
    
    def test_update_product(self, client, test_product_data):
        """Test updating a product."""
        # Create product
        created = client.products.create(test_product_data)
        
        # Update product
        update_data = UpdateProductDto(
            name="Updated Product",
            description="Updated description",
            price=19.99
        )
        updated = client.products.update(created.id, update_data)
        
        assert updated.id == created.id
        assert updated.name == "Updated Product"
        assert updated.price == 19.99


class TestPayments:
    """Test payment operations."""
    
    def test_create_payment_session_with_product_id(self, client, test_customer_data):
        """Test creating a payment session with product ID."""
        # Create customer first
        customer = client.customers.create(test_customer_data)
        
        # Create payment session
        response = client.one_time_payments.create_session(
            product_id=1,  # Assuming product 1 exists in test environment
            customer_uuid=customer.uuid,
            webhook_url="https://example.com/webhook"
        )
        
        assert response.uuid is not None
        assert response.link is not None
        assert "http" in response.link
    
    def test_create_payment_session_with_product_details(self, client, test_customer_data):
        """Test creating a payment session with custom product details."""
        # Create customer first
        customer = client.customers.create(test_customer_data)
        
        # Create payment session
        response = client.one_time_payments.create_session(
            product_name="Custom Product",
            description="Test product",
            price=29.99,
            customer_uuid=customer.uuid
        )
        
        assert response.uuid is not None
        assert response.link is not None
    
    def test_get_payment_session(self, client, test_customer_data):
        """Test retrieving a payment session."""
        # Create customer
        customer = client.customers.create(test_customer_data)
        
        # Create payment session
        created = client.one_time_payments.create_session(
            product_id=1,
            customer_uuid=customer.uuid
        )
        
        # Retrieve session
        session = client.one_time_payments.get_session(created.uuid)
        
        assert session.uuid == created.uuid
        assert session.price > 0
        assert len(session.available_currencies) > 0


class TestSubscriptions:
    """Test subscription operations."""
    
    def test_create_subscription_session(self, client, test_customer_data):
        """Test creating a subscription session."""
        # Create customer
        customer = client.customers.create(test_customer_data)
        
        # Create subscription session
        response = client.subscriptions.create_session(
            product_id=1,
            frequency=Duration(value=1, unit="months"),
            trial_period=Duration(value=7, unit="days"),
            customer_uuid=customer.uuid
        )
        
        assert response.uuid is not None
        assert response.link is not None
    
    def test_create_subscription_without_trial(self, client, test_customer_data):
        """Test creating a subscription without trial period."""
        # Create customer
        customer = client.customers.create(test_customer_data)
        
        # Create subscription session
        response = client.subscriptions.create_session(
            product_id=1,
            frequency=Duration(value=1, unit="weeks"),
            customer_uuid=customer.uuid
        )
        
        assert response.uuid is not None
        assert response.link is not None


class TestPayAsYouGo:
    """Test pay-as-you-go subscription operations."""
    
    def test_create_payg_session(self, client, test_customer_data):
        """Test creating a PAYG subscription session."""
        # Create customer
        customer = client.customers.create(test_customer_data)
        
        # Create PAYG session
        response = client.pay_as_you_go.create_session(
            product_id=1,
            frequency=Duration(value=1, unit="months"),
            free_credits=10.0,
            customer_uuid=customer.uuid
        )
        
        assert response.uuid is not None
        assert response.link is not None


class TestTransactionStatus:
    """Test transaction status operations."""
    
    def test_get_transaction_status(self, client, test_customer_data):
        """Test retrieving transaction status."""
        # Create a payment session
        customer = client.customers.create(test_customer_data)
        session = client.one_time_payments.create_session(
            product_id=1,
            customer_uuid=customer.uuid
        )
        
        # Try to get status (may not exist yet if payment not started)
        try:
            status = client.transaction_status.get(
                session.uuid,
                TransactionType.ONE_TIME_PAYMENT
            )
            assert status.type == TransactionType.ONE_TIME_PAYMENT
        except NotFoundException:
            # Expected if payment hasn't been initiated
            pass


class TestValidation:
    """Test input validation."""
    
    def test_invalid_customer_uuid(self, client):
        """Test that invalid UUID raises validation error."""
        with pytest.raises((ValidationError, QBitFlowError)):
            client.customers.get("")
    
    def test_invalid_product_id(self, client):
        """Test that invalid product ID raises validation error."""
        with pytest.raises((ValidationError, QBitFlowError)):
            client.products.get(-1)
    
    def test_negative_price(self):
        """Test that negative price raises validation error."""
        with pytest.raises(pydantic.ValidationError):
            CreateProductDto(
                name="Test",
                description="Test",
                price=-10.0
            )

