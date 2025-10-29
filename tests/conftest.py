"""
Pytest configuration and fixtures for QBitFlow SDK tests.

Set the QBITFLOW_API_KEY environment variable to run integration tests:
    export QBITFLOW_API_KEY="your_test_api_key"
"""

import os
import pytest
from qbitflow import QBitFlow, config
from qbitflow.dto.user import UserRole


@pytest.fixture(scope="session")
def api_key():
    """Get API key from environment variable."""
    key = os.getenv("QBITFLOW_API_KEY")
    if not key:
        pytest.skip("QBITFLOW_API_KEY environment variable not set")
    return key


@pytest.fixture(scope="session")
def client(api_key):
    """Create QBitFlow client with test API key."""
    # Optionally set test base URL
    test_url = os.getenv("QBITFLOW_BASE_URL")
    if test_url:
        config.set_base_url(test_url)
    
    return QBitFlow(api_key=api_key)


@pytest.fixture
def test_customer_data():
    """Sample customer data for testing."""
    from qbitflow.dto.customer import CreateCustomerDto
    return CreateCustomerDto(
        name="Test",
        last_name="Customer",
        email=f"test+{os.urandom(4).hex()}@example.com",
        phone_number="+1234567890",
        reference="TEST-001",
        address=None
    )


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    from qbitflow.dto.user import CreateUserDto
    return CreateUserDto(
        email=f"user+{os.urandom(4).hex()}@example.com",
        name="Test User",
        last_name="SDK",
        password="SecureP@ssw0rd!",
        role=UserRole.USER,
    )

@pytest.fixture
def test_product_data():
    """Sample product data for testing."""
    from qbitflow.dto.product import CreateProductDto
    return CreateProductDto(
        name="Test Product",
        description="A test product for SDK testing",
        price=9.99,
        reference=f"TEST-PROD-{os.urandom(4).hex()}"
    )

