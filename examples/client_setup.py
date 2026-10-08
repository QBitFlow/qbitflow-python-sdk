"""Create a client and check its key with me(), then build one from the environment.

QBITFLOW_API_KEY=sk_… python examples/client_setup.py

client_init talks to the default API URL; from_env also reads QBITFLOW_BASE_URL (and
QBITFLOW_ON_BEHALF_OF), so with QBITFLOW_BASE_URL set only the second part runs.
"""

import os

import qbitflow


def client_init() -> qbitflow.QBitFlow:
    # docs:start client-init
    # One client per API key, shared by the whole program. ValidationError: not an sk_… key.
    client = qbitflow.QBitFlow(os.environ["QBITFLOW_API_KEY"])

    # The recommended start-up check: what is this key, and which mode is it in?
    me = client.me()  # AuthenticationError for an unknown or revoked key
    if me.space is not None:
        print(f"{me.space.organization_name}, role {me.role}, test mode {me.space.test}")
    # docs:end client-init
    return client


def config_from_env() -> qbitflow.QBitFlow:
    # docs:start config-from-env
    # QBITFLOW_API_KEY (required), QBITFLOW_BASE_URL and QBITFLOW_ON_BEHALF_OF when set.
    client = qbitflow.QBitFlow.from_env(timeout=10)  # explicit options override the environment
    # docs:end config-from-env
    return client


def main() -> None:
    if not os.environ.get("QBITFLOW_API_KEY"):
        raise SystemExit("set QBITFLOW_API_KEY")
    if not os.environ.get("QBITFLOW_BASE_URL"):
        client_init().close()
    with config_from_env() as client:
        print("from the environment:", client.me().role)


if __name__ == "__main__":
    main()
