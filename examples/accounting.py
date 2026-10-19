"""A year of accounting events, as JSON models and as a CSV file (qbitflow-2026.csv).

QBITFLOW_API_KEY=sk_… python examples/accounting.py
"""

from _common import new_client

import qbitflow


def export_year(client: qbitflow.QBitFlow) -> None:
    # docs:start accounting-export
    # The API exports at most 92 days at a time (both included): the *_range methods split any
    # range into windows, request them in order and join the results (the CSV header once).
    events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
    for event in events:
        print(event.type, event.tx_uuid, event.tx_time_utc.date(), event.gross_amount_usd)

    csv_text = client.accounting.export_csv_range("2026-01-01", "2026-12-31")
    with open("qbitflow-2026.csv", "w", encoding="utf-8") as file:
        file.write(csv_text)
    # docs:end accounting-export


def main() -> None:
    with new_client() as client:
        export_year(client)


if __name__ == "__main__":
    main()
