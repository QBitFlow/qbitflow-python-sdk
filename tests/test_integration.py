"""
Integration tests for QBitFlow SDK.

These tests run against the actual QBitFlow test API.
Make sure to set QBITFLOW_API_KEY environment variable.

Run with:
    export QBITFLOW_API_KEY="your_test_api_key"
    pytest tests/test_integration.py -v
"""

import os
from typing import Optional
import pydantic
import pytest
from qbitflow import QBitFlow, Duration
from qbitflow.dto.api_key import CreateApiKeyDto
from qbitflow.dto.customer import UpdateCustomerDto
from qbitflow.dto.product import CreateProductDto, Product, UpdateProductDto
from qbitflow.dto.transaction.status import TransactionType
from qbitflow.dto.user import CreateUserDto, UpdateUserDto, User, UserRole
from qbitflow.exceptions import (
    NotFoundException,
    ValidationError,
    QBitFlowError
)
from qbitflow.exceptions.exceptions import InvalidRequestError

created_user: Optional[User] = None
created_product: Optional[Product] = None
created_customer_uuid: Optional[str] = None


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
        assert client.refunds is not None
        assert client.accounting is not None
        assert client.claim is not None

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

        global created_customer_uuid
        created_customer_uuid = customer.uuid

    def test_get_customer(self, client, test_customer_data):
        """Test retrieving a customer by UUID."""
        created = client.customers.create(test_customer_data)
        retrieved = client.customers.get(created.uuid)
        assert retrieved.uuid == created.uuid
        assert retrieved.email == created.email

    def test_get_customer_by_email(self, client, test_customer_data):
        """Test retrieving a customer by email."""
        created = client.customers.create(test_customer_data)
        retrieved = client.customers.get_by_email(created.email)
        assert retrieved.uuid == created.uuid
        assert retrieved.email == created.email

    def test_get_all_customers(self, client):
        """Test retrieving all customers."""
        cursor = None
        all_customers = []
        page = client.customers.get_all(limit=2)

        assert isinstance(page.items, list)
        assert len(page.items) <= 2
    

        # while True:
        #     page = client.customers.get_all(limit=2, cursor=cursor)
        #     assert isinstance(page.items, list)
        #     all_customers.extend(page.items)
        #     cursor = page.next_cursor
        #     if not cursor:
        #         break

    def test_update_customer(self, client, test_customer_data):
        """Test updating a customer."""
        created = client.customers.create(test_customer_data)
        update_data = UpdateCustomerDto(
            name=created.name,
            last_name=created.last_name,
            email="updated@example.com",
            phone_number="+9876543210"
        )
        updated = client.customers.update(created.uuid, update_data)
        assert updated.uuid == created.uuid
        assert updated.email == "updated@example.com"
        assert updated.phone_number == "+9876543210"

    def test_delete_customer(self, client, test_customer_data):
        """Test deleting a customer."""
        created = client.customers.create(test_customer_data)
        response = client.customers.delete(created.uuid)
        assert response.message is not None
        with pytest.raises(NotFoundException):
            client.customers.get(created.uuid)


class TestUsers:
    """Test user management operations."""

    def test_create_user(self, client, test_user_data):
        """Test creating a new user."""
        user = client.users.create(test_user_data)
        assert user.id is not None
        assert user.name == test_user_data.name
        assert user.email == test_user_data.email
        assert user.created_at is not None

        global created_user
        created_user = user

    def test_get_user(self, client):
        """Test retrieving the current user (based on API key)."""
        retrieved = client.users.get()
        assert retrieved.id is not None

    def test_get_user_by_id(self, client):
        """Test retrieving a user by ID."""
        global created_user
        assert created_user is not None, "Create user test must run first"
        retrieved = client.users.get_by_id(created_user.id)
        assert retrieved.id == created_user.id
        assert retrieved.email == created_user.email

    def test_get_all_users(self, client):
        """Test retrieving all users."""
        users = client.users.get_all()
        assert isinstance(users, list)
        assert len(users) >= 1

    def test_update_user(self, client):
        """Test updating a user."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        updated_email = f"updated+{os.urandom(4).hex()}@example.com"
        update_data = UpdateUserDto(
            name="Updated",
            last_name="User",
            email=updated_email,
            organization_fee_bps=150
        )
        updated = client.users.update(created_user.id, update_data)
        assert updated.id == created_user.id
        assert updated.email == updated_email
        assert updated.name == "Updated"
        assert updated.organization_fee_bps == 150

    def test_delete_user(self, client):
        """Test deleting a user."""
        temp_user_data = CreateUserDto(
            email=f"tempuser+{os.urandom(4).hex()}@example.com",
            name="Temp",
            last_name="User",
            role=UserRole.USER,
        )
        temp_user = client.users.create(temp_user_data)
        assert temp_user.id is not None

        response = client.users.delete(temp_user.id)
        assert response.message is not None

        with pytest.raises(NotFoundException):
            client.users.get_by_id(temp_user.id)


class TestProducts:
    """Test product management operations."""

    def test_create_product(self, client, test_product_data):
        """Test creating a new product."""
        product = client.products.create(test_product_data)
        assert product.id is not None
        assert product.name == test_product_data.name
        assert product.price == test_product_data.price
        assert product.is_active is True

        global created_product
        created_product = product

    def test_get_product(self, client):
        """Test retrieving a product by ID."""
        assert created_product is not None, "Create product test must run first"
        retrieved = client.products.get(created_product.id)
        assert retrieved.id == created_product.id
        assert retrieved.name == created_product.name

    def test_get_all_products(self, client):
        """Test retrieving all products."""
        products = client.products.get_all()
        assert isinstance(products, list)
        assert len(products) > 0

    def test_get_by_reference(self, client, test_product_data):
        """Test retrieving a product by reference code."""
        reference_code = f"REF-{os.urandom(4).hex()}"
        product_data = CreateProductDto(
            name=test_product_data.name,
            description=test_product_data.description,
            price=test_product_data.price,
            reference=reference_code
        )
        created = client.products.create(product_data)
        retrieved = client.products.get_by_reference(reference_code)
        assert retrieved.id == created.id
        assert retrieved.reference == reference_code

    def test_update_product(self, client, test_product_data):
        """Test updating a product."""
        created = client.products.create(test_product_data)
        update_data = UpdateProductDto(
            name="Updated Product",
            description="Updated description",
            price=19.99
        )
        updated = client.products.update(created.id, update_data)
        assert updated.id == created.id
        assert updated.name == "Updated Product"
        assert updated.price == 19.99

    def test_delete_product(self, client, test_product_data):
        """Test deleting a product."""
        created = client.products.create(test_product_data)
        response = client.products.delete(created.id)
        assert response.message is not None
        with pytest.raises(NotFoundException):
            client.products.get(created.id)


class TestApiKeys:
    """Test API key management operations."""

    def test_create_api_key(self, client):
        """Test creating a new API key."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        api_key = client.api_keys.create(
            CreateApiKeyDto(
                name="Test API Key",
                user_id=created_user.id,
                test=True
            )
        )
        data = api_key.data
        assert data.name == "Test API Key"
        assert api_key.key is not None

    def test_get_all_api_keys(self, client):
        """Test retrieving all API keys."""
        api_keys = client.api_keys.get_all()
        assert isinstance(api_keys, list)
        assert len(api_keys) > 0

    def test_get_for_user(self, client):
        """Test retrieving API keys for a specific user."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        api_keys = client.api_keys.get_for_user(created_user.id)
        assert isinstance(api_keys, list)
        for key in api_keys:
            assert key.user_id == created_user.id

    def test_delete_api_key(self, client):
        """Test deleting an API key."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        api_key = client.api_keys.create(
            CreateApiKeyDto(
                name="Temp API Key",
                user_id=created_user.id,
                test=True
            )
        )

        response = client.api_keys.delete(api_key.data.id)
        assert response.message is not None

        user_keys = client.api_keys.get_for_user(created_user.id)
        key_ids = [key.id for key in user_keys]
        assert api_key.data.id not in key_ids


class TestPayments:
    """Test payment operations."""

    def test_create_payment_session_with_product_id(self, client):
        """Test creating a payment session with product ID."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.one_time_payments.create_session(
            product_id=created_product.id,
            customer_uuid=created_customer_uuid,
            webhook_url="https://example.com/webhook"
        )

        assert response.uuid is not None
        assert response.link is not None
        assert "http" in response.link

    def test_create_payment_session_with_product_details(self, client):
        """Test creating a payment session with inline product details."""
        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.one_time_payments.create_session(
            product_name="Custom Product",
            description="Test product",
            price=29.99,
            customer_uuid=created_customer_uuid
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_get_payment_session(self, client):
        """Test retrieving a payment session."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        created = client.one_time_payments.create_session(
            product_id=created_product.id,
            customer_uuid=created_customer_uuid
        )

        session = client.one_time_payments.get_session(created.uuid)

        assert session.uuid == created.uuid
        assert session.price > 0
        assert len(session.available_currencies) > 0

    def test_get_all_payments(self, client):
        """Test retrieving all payments with pagination."""
        cursor = None
        all_payments = []
        page = client.one_time_payments.get_all(limit=2, cursor=cursor)

        assert isinstance(page.items, list)
        assert len(page.items) <= 2
        assert len(page.items) >= 0


        # while True:
        #     page = client.one_time_payments.get_all(limit=2, cursor=cursor)
        #     all_payments.extend(page.items)
        #     cursor = page.next_cursor
        #     if not cursor:
        #         break

        # assert len(all_payments) >= 5

    def test_get_all_combined_payments(self, client):
        """Test retrieving combined payments (one-time + subscription) with pagination."""
        cursor = None
        all_payments = []
        while True:
            page = client.one_time_payments.get_all_combined(limit=50, cursor=cursor)
            all_payments.extend(page.items)
            cursor = page.next_cursor
            if not cursor:
                break

        assert len(all_payments) >= 5


class TestSubscriptions:
    """Test subscription operations."""

    def test_create_subscription_session(self, client):
        """Test creating a subscription session with trial period."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="months"),
            trial_period=Duration(value=7, unit="days"),
            customer_uuid=created_customer_uuid
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_create_subscription_without_trial(self, client):
        """Test creating a subscription without a trial period."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="weeks"),
            customer_uuid=created_customer_uuid
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_get_session(self, client):
        """Test retrieving a subscription session."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        created = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="months"),
            customer_uuid=created_customer_uuid
        )

        session = client.subscriptions.get_session(created.uuid)

        assert session.uuid == created.uuid
        assert session.price > 0
        assert len(session.available_currencies) > 0


class TestRefunds:
    """Test refund retrieval operations."""

    def test_get_all_refunds(self, client):
        """Test retrieving all active refunds."""
        refunds = client.refunds.get_all()
        assert isinstance(refunds, list)

    def test_get_all_inactive_refunds(self, client):
        """Test retrieving inactive (processed) refunds with pagination."""
        page = client.refunds.get_all_inactive(limit=10)
        assert isinstance(page.items, list)


class TestAccounting:
    """Test accounting data export."""

    def test_export_json(self, client):
        """Test exporting accounting data as JSON."""
        from qbitflow.dto.accounting import AccountingEvent

        events = client.accounting.export("2024-11-01", "2024-12-31", "json")
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, AccountingEvent)

    def test_export_csv(self, client):
        """Test exporting accounting data as CSV."""
        csv_data = client.accounting.export("2024-11-01", "2024-12-31", "csv")
        assert isinstance(csv_data, str)
        assert len(csv_data) > 0


class TestClaim:
    """Test claim request and fund management."""

    def test_get_claim_funds(self, client):
        """Test retrieving pending claim fund entries."""
        from qbitflow.dto.claim import ClaimFund

        funds = client.claim.get_funds()
        assert isinstance(funds, list)
        for fund in funds:
            assert isinstance(fund, ClaimFund)

    def test_create_claim_request(self, client):
        """Test creating a claim request for a user."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        result = client.claim.create_request(user_id=created_user.id)
        assert result.message is not None
        assert result.link is not None
        assert "http" in result.link

    def test_get_claim_request(self, client):
        """Test retrieving a claim request via the public endpoint."""
        global created_user
        assert created_user is not None, "Create user test must run first"

        result = client.claim.get_request(user_id=created_user.id)
        assert result.message is not None
        assert result.link is not None
        assert "http" in result.link


class TestTransactionStatus:
    """Test transaction status operations."""

    def test_get_transaction_status(self, client):
        """Test retrieving transaction status."""
        global created_product
        assert created_product is not None, "Create product test must run first"

        global created_customer_uuid
        assert created_customer_uuid is not None, "Create customer test must run first"

        session = client.one_time_payments.create_session(
            product_id=created_product.id,
            customer_uuid=created_customer_uuid
        )

        try:
            status = client.transaction_status.get(
                session.uuid,
                TransactionType.ONE_TIME_PAYMENT
            )
            assert status.type == TransactionType.ONE_TIME_PAYMENT
        except NotFoundException:
            pass  # Expected if payment hasn't been initiated yet
        except InvalidRequestError as e:
            if e.status_code != 425:
                raise

class TestValidation:
    """Test input validation."""

    def test_invalid_customer_uuid(self, client):
        """Test that empty UUID raises validation error."""
        with pytest.raises((ValidationError, QBitFlowError)):
            client.customers.get("")

    def test_invalid_product_id(self, client):
        """Test that invalid product ID raises validation error."""
        with pytest.raises((ValidationError, QBitFlowError)):
            client.products.get(-1)

    def test_negative_price(self):
        """Test that negative price raises a pydantic validation error."""
        with pytest.raises(pydantic.ValidationError):
            CreateProductDto(
                name="Test",
                description="Test",
                price=-10.0
            )

    def test_payment_session_requires_product_info(self, client):
        """Test that create_session raises when neither product_id nor details are given."""
        with pytest.raises((ValueError, ValidationError)):
            client.one_time_payments.create_session()

    def test_subscription_session_requires_product_id(self):
        """Test that CreateSubscriptionSessionDto requires product_id."""
        from qbitflow.dto.transaction.session import CreateSubscriptionSessionDto
        from qbitflow import Duration
        with pytest.raises(pydantic.ValidationError):
            CreateSubscriptionSessionDto(
                frequency=Duration(value=1, unit="months")
                # product_id intentionally omitted
            )
