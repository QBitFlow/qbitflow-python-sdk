"""
Currency-related data models.

This module contains data models for cryptocurrency information.
"""

from typing import Optional

from qbitflow.dto.base_model import Bool, Int, ResponseModel, Str


class Currency(ResponseModel):
    """
    Represents a cryptocurrency that can be used for payments.

    Currencies define the supported cryptocurrencies that customers can use
    to complete payments. Payments, combined payments, subscriptions and billing records all
    carry their ``currency`` object.

    Attributes:
        id: Unique identifier for the currency.
        name: Currency name (e.g., "Bitcoin", "Ethereum").
        symbol: Currency symbol (e.g., "BTC", "ETH").
        decimals: Number of decimal places for this currency.
        address: Contract address (or mint) for tokens; empty for main (native) currencies.
        main_currency_id: ID of the main currency if this is a token; ``None`` for a main
            currency.
        main_currency: The main currency object for a token; ``None`` for a main currency.
        test: Whether this is a test mode currency.

    Example:
        >>> by_id = {c.id: c for c in client.currencies.get_all_available()}
        >>> session = client.one_time_payments.get_session("pay@...")
        >>> for currency_id in session.available_currencies:
        ...     currency = by_id[currency_id]
        ...     print(f"{currency.name} ({currency.symbol})")
    """

    id: Int = 0
    name: Str = ""
    symbol: Str = ""
    decimals: Int = 0
    address: Str = ""
    main_currency_id: Optional[Int] = None
    main_currency: Optional["Currency"] = None
    test: Bool = False
