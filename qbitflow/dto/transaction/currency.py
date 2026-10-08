"""
Currency-related data models.

This module contains data models for cryptocurrency information.
"""

from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class Currency(BaseModel):
    """
    Represents a cryptocurrency that can be used for payments.

    Currencies define the supported cryptocurrencies that customers can use
    to complete payments.

    Attributes:
        id: Unique identifier for the currency.
        name: Currency name (e.g., "Bitcoin", "Ethereum").
        symbol: Currency symbol (e.g., "BTC", "ETH").
        decimals: Number of decimal places for this currency.
        address: Smart contract address or blockchain identifier.
        main_currency_id: ID of the main currency if this is a variant.
        main_currency: Reference to the main currency object if applicable.
        test: Whether this is a test mode currency.

    Example:
        >>> session = client.one_time_payments.get_session("session-uuid")
        >>> for currency in session.available_currencies:
        ...     print(f"{currency.name} ({currency.symbol})")
    """

    id: int = Field(..., description="Unique identifier for the currency")
    name: str = Field(..., description="Currency name")
    symbol: str = Field(..., description="Currency symbol")
    decimals: int = Field(..., ge=0, description="Number of decimal places")
    address: str = Field(..., description="Smart contract address or blockchain identifier")
    main_currency_id: Optional[int] = Field(
        default=None, description="ID of main currency if variant"
    )
    main_currency: Optional["Currency"] = Field(default=None, description="Main currency reference")
    test: bool = Field(..., description="Whether this is a test mode currency")
