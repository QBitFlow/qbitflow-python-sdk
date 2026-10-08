# Contributing

## Gates

From the SDK root, with the dev extras installed (`pip install -e ".[dev]"`):

```bash
mypy qbitflow/
flake8 qbitflow/ tests/ examples/
black --check qbitflow/ tests/ examples/
isort --check-only qbitflow/ tests/ examples/
python -m py_compile examples/*.py
pytest -q -p no:cacheprovider
```

Run them with every `QBITFLOW_*` variable unset: the suite stays offline. The live checks
(`tests/test_integration.py`) are described in the README's Testing section.

## Website snippets

The code on [qbitflow.app/docs](https://qbitflow.app/docs) and the Python code blocks of
`README.md` that show an SDK capability are not hand-written: they are **named regions** of the
programs in `examples/`, which run and pass the gates above.

```python
def create_checkout(client: qbitflow.QBitFlow) -> qbitflow.CheckoutSession:
    # docs:start checkout-create-payment
    session = client.checkout_sessions.create_payment(...)
    # docs:end checkout-create-payment
    return session
```

- **Markers** are exactly `# docs:start <id>` and `# docs:end <id>` on their own lines (any
  indentation: the region is dedented when extracted). One region per id; regions never nest or
  overlap, and the id on `docs:end` matches its `docs:start`.
- **Ids** come from the hub's `snippets/catalog.json`: the same ids in every QBitFlow SDK, each
  with what its snippet `shows` and the `routes` it calls.
- **A region reads on its own.** It uses a ready client named `client` (only `client-init` and
  `client-on-behalf-of` build theirs), refers to the SDK as `qbitflow.…` (`import qbitflow`), uses
  the catalog's shared values (T-shirt, Blue, size M, 4.99, `tshirt-blue-m`, `order-1042`,
  `order-1043`, `https://shop.example.com/…`, `qbitflow.PLACEHOLDER_UUID`, `seller@example.com`,
  …), and takes the ids it needs but doesn't create from variables defined just outside it
  (`payment_uuid`, `subscription_uuid`, `session_uuid`, `member_uuid`). Keys come from
  `QBITFLOW_API_KEY` and `QBITFLOW_WEBHOOK_SECRET`, never from the code. Setup (env lookups,
  `_common.new_client()`, `main()`) stays outside the regions.
- **The manifest** `examples/snippets.manifest.json` maps every catalog id to the file holding
  its region, or lists it under `unsupported` with a one-line reason; `catalog` is the hub commit
  of the catalog this SDK follows.
- **README blocks** are `<!-- docs:snippet <id> -->` / `<!-- /docs:snippet -->` pairs. The
  script writes the code between them: never edit it by hand.

From a hub checkout (this SDK in `sdk/qbitflow-python-sdk`):

```bash
node ../../scripts/embed-snippets.mjs .           # rewrite the README's snippet blocks
node ../../scripts/embed-snippets.mjs --check .   # change nothing; exit 1 on any problem
```

`tests/test_snippets.py` runs the `--check` in `pytest`. It finds the hub at `QBITFLOW_HUB_DIR`,
or two directories up; a standalone clone (or a machine without `node`) skips it, and an invalid
`QBITFLOW_HUB_DIR` fails it.

### The rule

> **Website snippets.** The code on qbitflow.app/docs and in this README comes from `# docs:start <id>` … `# docs:end <id>` regions in `examples/`. Every change keeps them true:
> - **New public capability:** add a region, an id in the hub's `snippets/catalog.json` (the same id across all SDKs), and the manifest entry, plus the README block via `scripts/embed-snippets.mjs`.
> - **Changed capability:** update the region's code. Never hand-edit an embedded README block: re-run the script.
> - **Ids are a public contract with the website.** Never rename or remove one silently. To retire an id, keep it until the website no longer uses it, and note it in the CHANGELOG.
> - **Before committing:** the examples run, the manifest check passes, and `embed-snippets --check` passes.
> - **Unsupported ids:** an id the SDK can't support goes under `unsupported` with a reason. Never write placeholder code.
