"""The examples' shared client factory: QBITFLOW_API_KEY (and optionally QBITFLOW_BASE_URL)."""

import os
import sys

from qbitflow import QBitFlow


def new_client() -> QBitFlow:
    key = os.environ.get("QBITFLOW_API_KEY", "")
    if not key:
        sys.exit("set QBITFLOW_API_KEY")
    return QBitFlow(key, base_url=os.environ.get("QBITFLOW_BASE_URL") or None)
