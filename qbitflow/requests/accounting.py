"""Accounting export request handlers."""

from typing import List, Literal, Union, overload

from qbitflow.dto.accounting import AccountingEvent
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest
from qbitflow.utils.helpers import validate_export_request


class AccountingRequests(BaseRequest):
    """
    Handler for accounting data export.

    Example:
        >>> events = client.accounting.export("2025-01-01", "2025-01-31", "json")
        >>> for event in events:
        ...     print(f"{event.payment_id}: ${event.gross_amount_usd}")
    """

    BASE_ROUTE = "/accounting"

    @overload
    def export(
        self, from_date: str, to_date: str, format: Literal["json"]
    ) -> List[AccountingEvent]: ...

    @overload
    def export(self, from_date: str, to_date: str, format: Literal["csv"]) -> str: ...

    def export(
        self,
        from_date: str,
        to_date: str,
        format: Literal["json", "csv"],
    ) -> Union[List[AccountingEvent], str]:
        """
        Export accounting data for a date range.

        Dates must be real ``YYYY-MM-DD`` calendar dates and ``from_date`` must not be after
        ``to_date`` — checked locally before any round-trip. How long a window the export may
        span is decided by the API.

        Args:
            from_date: Start date (inclusive), e.g. "2025-01-01".
            to_date: End date (inclusive), e.g. "2025-01-31".
            format: Response format — "json" returns a list of AccountingEvent
                objects; "csv" returns the raw CSV string (header row included).

        Returns:
            List[AccountingEvent] for format="json", raw CSV string for format="csv".

        Raises:
            ValidationError: If a date is malformed, the range is inverted, the format is
                unknown, or the API rejects the window (400).

        Example:
            >>> # JSON export
            >>> events = client.accounting.export("2025-01-01", "2025-01-31", "json")
            >>> print(f"Total events: {len(events)}")
            >>>
            >>> # CSV export
            >>> csv_data = client.accounting.export("2025-01-01", "2025-01-31", "csv")
            >>> with open("accounting.csv", "w") as f:
            ...     f.write(csv_data)
        """
        problem = validate_export_request(from_date, to_date, format)
        if problem is not None:
            raise ValidationError(problem)

        params = {"from": from_date, "to": to_date, "format": format}
        endpoint = f"{self.BASE_ROUTE}/export"

        if format == "csv":
            return self._make_raw_request(endpoint, "GET", params=params)

        return self._request_list(AccountingEvent, endpoint, params=params)
