"""Accounting export data models."""

from qbitflow.dto.base_model import GO_ZERO_TIME, Float, Int, ResponseModel, Str, Timestamp

#: Known values of :attr:`AccountingEvent.type`. The subscription-billing value is spelled
#: ``subscriptionHistory`` by the API's Go constant and ``subHistory`` in its prose; both are
#: listed so either is recognised. The field itself stays a plain string.
ACCOUNTING_EVENT_TYPES = (
    "payment",
    "subscriptionHistory",
    "subHistory",
    "refund",
    "organizationFee",
    "referralFee",
)


class AccountingEvent(ResponseModel):
    """
    Represents a single accounting event (payment, subscription cycle, refund or fee).

    Decimal values (gross_amount, fees, net_amount, etc.) are returned as strings
    to preserve full precision.

    Example:
        >>> events = client.accounting.export("2025-01-01", "2025-01-31", "json")
        >>> for event in events:
        ...     print(f"{event.payment_id} | {event.type} | ${event.gross_amount_usd}")
    """

    payment_id: Str = ""
    payment_reference: Str = ""
    #: ``payment``, ``subscriptionHistory``/``subHistory``, ``refund``, ``organizationFee`` or
    #: ``referralFee`` (see :data:`ACCOUNTING_EVENT_TYPES`); an unknown value is kept as is.
    type: Str = ""
    tx_time_utc: Timestamp = GO_ZERO_TIME
    receipt_url: Str = ""
    related_payment_id: Str = ""
    related_payment_reference: Str = ""
    product_id: Int = 0
    product_reference: Str = ""
    product_name: Str = ""
    product_description: Str = ""
    customer_uuid: Str = ""
    customer_reference: Str = ""
    chain: Str = ""
    block_number_or_slot: Str = ""
    tx_hash: Str = ""
    from_address: Str = ""
    to_address: Str = ""
    token_symbol: Str = ""
    currency_decimals: Int = 0
    token_contract_or_mint: Str = ""
    explorer_url: Str = ""
    gross_amount: Str = ""
    gross_amount_usd: Float = 0.0
    platform_fee_percent: Float = 0.0
    platform_fee_usd: Float = 0.0
    platform_fee: Str = ""
    organization_fee_percent: Float = 0.0
    organization_fee_usd: Float = 0.0
    organization_fee: Str = ""
    network_fees_usd: Float = 0.0
    network_fees: Str = ""
    net_amount_usd: Float = 0.0
    net_amount: Str = ""
