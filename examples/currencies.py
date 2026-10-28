"""The currencies customers can pay with.

QBITFLOW_API_KEY=sk_… python examples/currencies.py
"""

from _common import new_client

import qbitflow


def list_currencies(client: qbitflow.QBitFlow) -> None:
    # docs:start currencies-list
    # A public route limited to 60 requests a minute: cache the list at start-up. One bounded
    # list: the live currencies; test=True the test networks'; main=True the native coins only.
    currencies = client.currencies.list()
    for currency in currencies:
        print(currency.id, currency.code, currency.name, currency.chain, currency.decimals)
    # docs:end currencies-list


def main() -> None:
    with new_client() as client:
        list_currencies(client)


if __name__ == "__main__":
    main()
