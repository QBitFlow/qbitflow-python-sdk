"""
Integration tests for QBitFlow SDK.

These tests run against the live QBitFlow server named by ``QBITFLOW_BASE_URL`` with the key
in ``QBITFLOW_API_KEY`` (see ``tests/conftest.py`` for the skip/fail rules: key without base
URL fails, neither skips).

Run with:
    set -a; . ../.local.env; set +a
    pytest tests/test_integration.py -v
"""

import os
from datetime import date, timedelta
from typing import Optional

import pytest

from qbitflow import Duration, QBitFlow
from qbitflow.dto.customer import UpdateCustomerDto
from qbitflow.dto.product import CreateProductDto, Product, UpdateProductDto
from qbitflow.dto.transaction.status import TransactionStatusValue, TransactionType
from qbitflow.dto.user import CreateUserDto, UpdateUserDto, User, UserRole
from qbitflow.exceptions import NotFoundException, QBitFlowError, ValidationError
from qbitflow.exceptions.exceptions import InvalidRequestError

created_user: Optional[User] = None
created_product: Optional[Product] = None
created_customer_uuid: Optional[str] = None


class TestClient:
    """Test QBitFlow client initialization."""

    def test_client_initialization(self, api_key, base_url):
        """Test that client can be initialized with API key."""
        client = QBitFlow(api_key=api_key, base_url=base_url)
        try:
            assert client.api_key == api_key
            assert client.base_url == base_url.rstrip("/")
            assert client.customers is not None
            assert client.claims is not None
        finally:
            client.close()

    def test_client_level_on_behalf_of_zero_is_organization_level(self, client):
        """`on_behalf_of(0)` sends no header, so it reads the same org-level user."""
        assert client.on_behalf_of(0).users.get().id == client.users.get().id

    def test_client_requires_api_key(self):
        """Test that client raises error without API key."""
        with pytest.raises(ValueError):
            QBitFlow(api_key="")


class TestCustomers:
    """Test customer management operations."""

    def test_create_customer(self, client, test_customer_data):
        """Test creating a new customer."""
        customer = client.customers.create(test_customer_data)

        assert customer.uuid
        assert customer.name == test_customer_data.name
        assert customer.last_name == test_customer_data.last_name
        assert customer.email == test_customer_data.email
        assert customer.created_at.year > 2000
        assert customer.organization_id > 0
        assert customer.address == ""  # omitted by the API → zero value

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
        page = client.customers.get_all(limit=2)

        assert isinstance(page.items, list)
        assert len(page.items) <= 2

    def test_update_customer(self, client, test_customer_data):
        """Test updating a customer."""
        created = client.customers.create(test_customer_data)
        # Email is unique per (organization, user), so it must be randomised - a fixed
        # value collides with the previous run and fails with 400.
        new_email = f"updated+{os.urandom(4).hex()}@example.com"
        update_data = UpdateCustomerDto(
            name=created.name,
            last_name=created.last_name,
            email=new_email,
            phone_number="+9876543210",
        )
        updated = client.customers.update(created.uuid, update_data)
        assert updated.uuid == created.uuid
        assert updated.email == new_email
        assert updated.phone_number == "+9876543210"

    def test_update_customer_partial(self, client, test_customer_data):
        """A partial update changes only the supplied fields."""
        created = client.customers.create(test_customer_data)

        updated = client.customers.update(created.uuid, UpdateCustomerDto(name="OnlyName"))

        assert updated.name == "OnlyName"
        assert updated.last_name == created.last_name
        assert updated.email == created.email

    def test_update_customer_empty_is_noop(self, client, test_customer_data):
        """An empty update body is a valid no-op."""
        created = client.customers.create(test_customer_data)

        updated = client.customers.update(created.uuid, UpdateCustomerDto())

        assert updated.name == created.name
        assert updated.last_name == created.last_name
        assert updated.email == created.email

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
        assert user.id > 0
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
        assert created_user is not None, "Create user test must run first"

        updated_email = f"updated+{os.urandom(4).hex()}@example.com"
        update_data = UpdateUserDto(
            name="Updated", last_name="User", email=updated_email, organization_fee_bps=150
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
        assert product.id > 0
        assert product.reference == test_product_data.reference
        assert product.organization_id > 0
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
            reference=reference_code,
        )
        created = client.products.create(product_data)
        retrieved = client.products.get_by_reference(reference_code)
        assert retrieved.id == created.id
        assert retrieved.reference == reference_code

    def test_update_product(self, client, test_product_data):
        """Test updating a product."""
        created = client.products.create(test_product_data)
        update_data = UpdateProductDto(
            name="Updated Product", description="Updated description", price=19.99
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
    """Test read-only API key operations."""

    def test_get_all_api_keys(self, client):
        """Test retrieving all API keys."""
        api_keys = client.api_keys.get_all()
        assert isinstance(api_keys, list)
        assert len(api_keys) > 0

    def test_get_for_user(self, client):
        """Test retrieving API keys for a specific user."""
        assert created_user is not None, "Create user test must run first"

        api_keys = client.api_keys.get_for_user(created_user.id)
        assert isinstance(api_keys, list)
        for key in api_keys:
            assert key.user_id == created_user.id


class TestCurrencies:
    """Test supported-currency lookups."""

    def test_get_all_available(self, client):
        """Test retrieving all available currencies (native and tokens)."""
        from qbitflow.dto.transaction.currency import Currency

        currencies = client.currencies.get_all_available()
        assert isinstance(currencies, list)
        assert len(currencies) > 0
        for currency in currencies:
            assert isinstance(currency, Currency)
            assert currency.id > 0

    def test_get_all_main(self, client):
        """Test retrieving only the main (native) currencies."""
        from qbitflow.dto.transaction.currency import Currency

        currencies = client.currencies.get_all_main()
        assert isinstance(currencies, list)
        assert len(currencies) > 0
        for currency in currencies:
            assert isinstance(currency, Currency)
            # Main currencies do not reference another main currency.
            assert currency.main_currency_id is None


class TestPayments:
    """Test payment operations."""

    def test_create_payment_session_with_product_id(self, client):
        """Test creating a payment session with product ID."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.one_time_payments.create_session(
            product_id=created_product.id,
            customer_uuid=created_customer_uuid,
        )

        assert response.uuid is not None
        assert response.link is not None
        assert "http" in response.link

    def test_create_payment_session_with_product_details(self, client):
        """Test creating a payment session with inline product details."""
        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.one_time_payments.create_session(
            product_name="Custom Product",
            description="Test product",
            price=29.99,
            customer_uuid=created_customer_uuid,
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_get_payment_session(self, client):
        """Test retrieving a payment session."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        created = client.one_time_payments.create_session(
            product_id=created_product.id, customer_uuid=created_customer_uuid
        )

        session = client.one_time_payments.get_session(created.uuid)

        assert session.uuid == created.uuid
        assert session.price > 0
        assert len(session.available_currencies) > 0
        # The public route honours the API key, so the authenticated fields are present.
        assert session.organization_id > 0
        assert session.customer_uuid == created_customer_uuid

    def test_get_all_payments(self, client):
        """Test retrieving all payments with pagination."""
        page = client.one_time_payments.get_all(limit=2)

        assert isinstance(page.items, list)
        assert len(page.items) <= 2
        for payment in page.items:
            assert payment.currency.id == payment.currency_id
            assert payment.organization_id > 0

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

        # Pagination must return well-formed pages; the test account may legitimately have
        # no completed payments, so assert shape rather than presence of data.
        assert isinstance(all_payments, list)
        for item in all_payments:
            assert item.source in ("payment", "subscription_history")
            assert item.currency.id == item.currency_id


class TestSubscriptions:
    """Test subscription operations."""

    def test_create_subscription_session(self, client):
        """Test creating a subscription session with trial period."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="months"),
            trial_period=Duration(value=7, unit="days"),
            customer_uuid=created_customer_uuid,
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_create_subscription_without_trial(self, client):
        """Test creating a subscription without a trial period."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        response = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="weeks"),
            customer_uuid=created_customer_uuid,
        )

        assert response.uuid is not None
        assert response.link is not None

    def test_get_session(self, client):
        """Test retrieving a subscription session."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        created = client.subscriptions.create_session(
            product_id=created_product.id,
            frequency=Duration(value=1, unit="months"),
            customer_uuid=created_customer_uuid,
        )

        session = client.subscriptions.get_session(created.uuid)

        assert session.uuid == created.uuid
        assert session.price > 0
        assert session.frequency > 0
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

    @staticmethod
    def _last_month():
        today = date.today()
        return (today - timedelta(days=30)).isoformat(), today.isoformat()

    def test_export_json(self, client):
        """Test exporting accounting data as JSON."""
        from qbitflow.dto.accounting import AccountingEvent

        start, end = self._last_month()
        events = client.accounting.export(start, end, "json")
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, AccountingEvent)

    def test_export_csv(self, client):
        """Test exporting accounting data as CSV."""
        start, end = self._last_month()
        csv_data = client.accounting.export(start, end, "csv")
        assert isinstance(csv_data, str)
        assert len(csv_data) > 0


class TestClaim:
    """Test claim request and fund management."""

    def test_get_claim_funds(self, client):
        """Test retrieving pending claim fund entries."""
        from qbitflow.dto.claim import ClaimFund

        funds = client.claims.get_funds()
        assert isinstance(funds, list)
        for fund in funds:
            assert isinstance(fund, ClaimFund)

    def test_create_claim_request(self, client):
        """Test creating a claim request for a user."""
        assert created_user is not None, "Create user test must run first"

        result = client.claims.create_request(user_id=created_user.id)
        assert result.message is not None
        assert result.link is not None
        assert "http" in result.link

    def test_get_claim_request(self, client):
        """Test retrieving the claim request created above."""
        assert created_user is not None, "Create user test must run first"

        result = client.claims.get_request_by_user(user_id=created_user.id)
        assert result.message is not None
        assert result.link is not None
        assert "http" in result.link


class TestTransactionStatus:
    """Test transaction status operations."""

    def test_get_transaction_status(self, client):
        """Test retrieving transaction status."""
        assert created_product is not None, "Create product test must run first"

        assert created_customer_uuid is not None, "Create customer test must run first"

        session = client.one_time_payments.create_session(
            product_id=created_product.id, customer_uuid=created_customer_uuid
        )

        try:
            status = client.transaction_status.get(session.uuid, TransactionType.ONE_TIME_PAYMENT)
            assert isinstance(status.status, (TransactionStatusValue, str))
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
        """A negative price raises the SDK's ValidationError before any request."""
        with pytest.raises(ValidationError, match="price"):
            CreateProductDto(name="Test", description="Test", price=-10.0)

    def test_payment_session_requires_product_info(self, client):
        """Test that create_session raises when neither product_id nor details are given."""
        with pytest.raises(ValidationError):
            client.one_time_payments.create_session()

    def test_subscription_session_requires_some_product(self):
        """A subscription session needs a stored product (product_id / product_reference)
        or a complete inline one (product_name + description + price); check() enforces
        this before any request."""
        from qbitflow import Duration
        from qbitflow.dto.transaction.session import CreateSubscriptionSessionDto

        with pytest.raises(ValidationError, match="product_id"):
            CreateSubscriptionSessionDto(
                frequency=Duration(value=1, unit="months")
                # product selection intentionally omitted
            )
