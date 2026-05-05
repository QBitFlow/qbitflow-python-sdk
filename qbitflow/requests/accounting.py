"""Accounting export request handlers."""

import json
from typing import List, Literal, Union

from qbitflow.requests.base_request import BaseRequest
from qbitflow.dto.accounting import AccountingEvent
from qbitflow.exceptions import ValidationError


class AccountingRequests(BaseRequest):
    """
    Handler for accounting data export.

    Example:
        >>> events = client.accounting.export("2025-01-01", "2025-12-31", "json")
        >>> for event in events:
        ...     print(f"{event.payment_id}: ${event.gross_amount_usd}")
    """

    BASE_ROUTE = "/accounting"

    def export(
        self,
        from_date: str,
        to_date: str,
        format: Literal["json", "csv"],
    ) -> Union[List[AccountingEvent], str]:
        """
        Export accounting data for a date range.

        Dates must be in YYYY-MM-DD format.

        Args:
            from_date: Start date (inclusive), e.g. "2025-01-01".
            to_date: End date (inclusive), e.g. "2025-12-31".
            format: Response format — "json" returns a list of AccountingEvent
                objects; "csv" returns the raw CSV string.

        Returns:
            List[AccountingEvent] for format="json", raw CSV string for format="csv".

        Raises:
            ValidationError: If from_date or to_date are empty.

        Example:
            >>> # JSON export
            >>> events = client.accounting.export("2025-01-01", "2025-12-31", "json")
            >>> print(f"Total events: {len(events)}")
            >>>
            >>> # CSV export
            >>> csv_data = client.accounting.export("2025-01-01", "2025-12-31", "csv")
            >>> with open("accounting.csv", "w") as f:
            ...     f.write(csv_data)
        """
        if not from_date:
            raise ValidationError("from_date cannot be empty")
        if not to_date:
            raise ValidationError("to_date cannot be empty")

        params = {"from": from_date, "to": to_date, "format": format}

        if format == "csv":
            raw = self._make_raw_request(f"{self.BASE_ROUTE}/export", "GET", params=params)
            return raw

        raw = self._make_raw_request(f"{self.BASE_ROUTE}/export", "GET", params=params)
        data = json.loads(raw)
        return [AccountingEvent(**item) for item in data]
