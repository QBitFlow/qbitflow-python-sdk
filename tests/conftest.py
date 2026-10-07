"""
Pytest configuration and fixtures for QBitFlow SDK tests.

The offline suites need nothing. The live integration suite (``tests/test_integration.py``)
runs against the server named by ``QBITFLOW_BASE_URL`` — typically loaded from the workspace's
``.local.env`` — and never falls back to localhost or production:

* neither ``QBITFLOW_API_KEY`` nor ``QBITFLOW_BASE_URL`` set → the live tests are skipped;
* ``QBITFLOW_API_KEY`` set but ``QBITFLOW_BASE_URL`` missing → the live tests fail with a clear
  message;
* both set → the live tests run against that base URL::

    set -a; . ../.local.env; set +a
    pytest tests/test_integration.py -v
"""

import os

import pytest

from qbitflow import QBitFlow
from qbitflow.dto.user import UserRole


@pytest.fixture(scope="session")
def base_url():
    """The live server's base URL (``QBITFLOW_BASE_URL``); see the module docstring."""
    key = os.getenv("QBITFLOW_API_KEY", "").strip()
    url = os.getenv("QBITFLOW_BASE_URL", "").strip()
    if not key and not url:
        pytest.skip("live suite: QBITFLOW_API_KEY and QBITFLOW_BASE_URL are not set")
    if key and not url:
        pytest.fail(
            "QBITFLOW_API_KEY is set but QBITFLOW_BASE_URL is not: the live suite never "
            "defaults to localhost or production. Export QBITFLOW_BASE_URL (e.g. from "
            ".local.env) or unset QBITFLOW_API_KEY to skip the live tests."
        )
    if not key:
        pytest.skip("live suite: QBITFLOW_API_KEY is not set")
    return url


@pytest.fixture(scope="session")
def api_key(base_url):
    """The live API key (``QBITFLOW_API_KEY``); requires ``QBITFLOW_BASE_URL`` too."""
    return os.environ["QBITFLOW_API_KEY"].strip()


@pytest.fixture(scope="session")
def client(api_key, base_url):
    """A client bound to the live server named by QBITFLOW_BASE_URL."""
    client = QBitFlow(api_key=api_key, base_url=base_url)
    yield client
    client.close()


@pytest.fixture
def test_customer_data():
    """Sample customer data for testing."""
    from qbitflow.dto.customer import CreateCustomerDto

    return CreateCustomerDto(
        name="Test",
        last_name="Customer",
        email=f"test+{os.urandom(4).hex()}@example.com",
        phone_number="+1234567890",
        # A customer reference is unique per (organization, user), so it must be
        # randomised like the email - a fixed value collides on every rerun (400).
        reference=f"TEST-{os.urandom(4).hex()}",
        address=None,
    )


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    from qbitflow.dto.user import CreateUserDto

    return CreateUserDto(
        email=f"user+{os.urandom(4).hex()}@example.com",
        name="Test User",
        last_name="SDK",
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
        reference=f"TEST-PROD-{os.urandom(4).hex()}",
    )
