"""
Currency request handlers.

These endpoints are public (no authentication required) and are used to resolve
the currency IDs returned in ``SessionCheckout.available_currencies`` and on
payment/subscription records.
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
            test: When ``True``, list test-network currencies instead of live ones.

        Returns:
            The list of supported currencies.

        Example:
            >>> currencies = client.currencies.get_all_available()
            >>> for currency in currencies:
            ...     print(f"{currency.id}: {currency.name} ({currency.symbol})")
        """
        params = {"test": str(test).lower()}
        res = self._make_request(
            f"{self.BASE_ROUTE}/all-available-currencies", "GET", params=params
        )  # noqa: E501
        return [Currency(**item) for item in res]

    def get_all_main(self, test: bool = False) -> List[Currency]:
        """
        Return only the main (native / blockchain) currencies, excluding tokens.

        Args:
            test: When ``True``, list test-network currencies instead of live ones.

        Returns:
            The list of main currencies.

        Example:
            >>> currencies = client.currencies.get_all_main()
            >>> for currency in currencies:
            ...     print(f"{currency.id}: {currency.name} ({currency.symbol})")
        """
        params = {"test": str(test).lower()}
        res = self._make_request(f"{self.BASE_ROUTE}/all-main-currencies", "GET", params=params)
        return [Currency(**item) for item in res]
