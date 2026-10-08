"""A year of accounting events, as JSON models and as a CSV file (qbitflow-2026.csv).

QBITFLOW_API_KEY=sk_… python examples/accounting.py
"""

from _common import new_client

import qbitflow


def export_year(client: qbitflow.QBitFlow) -> None:
    # docs:start accounting-export
    # Any range: the SDK splits it into the API's 95-day windows and joins the parts.
    events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
    for event in events:
        print(event.type, event.payment_uuid, event.token_symbol, event.net_amount)

    csv_text = client.accounting.export_csv_range("2026-01-01", "2026-12-31")
    with open("qbitflow-2026.csv", "w", encoding="utf-8") as file:
        file.write(csv_text)
    # docs:end accounting-export


def main() -> None:
    with new_client() as client:
        export_year(client)


if __name__ == "__main__":
    main()
