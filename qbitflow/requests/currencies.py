"""
Currency request handlers.

These endpoints are public (no authentication required) and are used to resolve
the currency IDs returned in a session's ``available_currencies``. Payments, subscriptions and
billing records carry their full ``currency`` object.
"""

from typing import List

from qbitflow.dto.transaction.currency import Currency

from .base_request import BaseRequest


class CurrencyRequests(BaseRequest):
    """Handler for supported-currency lookups."""

    BASE_ROUTE = "/utils"

    def get_all_available(self, test: bool = False) -> List[Currency]:
        """
        Return all supported currencies, native currencies and tokens alike.

        Args:
            test: When ``True``, include test-network currencies.

        Returns:
            The list of supported currencies.

        Example:
            >>> currencies = client.currencies.get_all_available()
            >>> for currency in currencies:
            ...     print(f"{currency.id}: {currency.name} ({currency.symbol})")
        """
        params = {"test": str(test).lower()}
        return self._request_list(
            Currency, f"{self.BASE_ROUTE}/all-available-currencies", params=params
        )

    def get_all_main(self, test: bool = False) -> List[Currency]:
        """
        Return only the main (native / blockchain) currencies, excluding tokens.

        Args:
            test: When ``True``, include test-network currencies.

        Returns:
            The list of main currencies.

        Example:
            >>> currencies = client.currencies.get_all_main()
            >>> for currency in currencies:
            ...     print(f"{currency.id}: {currency.name} ({currency.symbol})")
        """
        params = {"test": str(test).lower()}
        return self._request_list(Currency, f"{self.BASE_ROUTE}/all-main-currencies", params=params)
