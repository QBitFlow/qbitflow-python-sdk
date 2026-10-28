# Contributing

Thank you for helping improve the QBitFlow Python SDK. Bug reports and pull requests are welcome
on [GitHub](https://github.com/QBitFlow/qbitflow-python-sdk). For a security issue, do **not**
open an issue: follow [SECURITY.md](SECURITY.md).

## Setting up

Python 3.10 or later:

```bash
git clone https://github.com/QBitFlow/qbitflow-python-sdk.git
cd qbitflow-python-sdk
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## The gates

Every pull request must pass these, the same checks CI runs on Python 3.10 to 3.14
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Run them from the repository root with
every `QBITFLOW_*` environment variable unset, so the suite stays offline:

```bash
mypy qbitflow/
flake8 qbitflow/ tests/ examples/
black --check qbitflow/ tests/ examples/
isort --check-only qbitflow/ tests/ examples/
python -m py_compile examples/*.py
pytest -q -p no:cacheprovider
```

`pytest` runs the whole offline suite against stub HTTP transports: the models, the services'
requests, validation, retries, errors, webhooks, and the conformance vectors in
`tests/fixtures/vectors/` (cases every QBitFlow SDK reproduces). Nothing in it needs a network or
an API key.

Two groups of tests skip themselves on an outside contributor's machine, and that is expected:

- **`tests/test_integration.py`**, the live checks. They run only with an API key **and** an
  explicit base URL (`QBITFLOW_API_KEY`, `QBITFLOW_BASE_URL`; a key without a base URL fails, so
  they are never aimed at production by accident), and write only with `QBITFLOW_LIVE_WRITES=1`
  on a test-mode key. Use your own test-mode key if you want to run them; the maintainers run them
  before every release.
- **`tests/test_snippets.py`**, the website snippet check (below). It needs the maintainers'
  documentation tooling, which is not part of this repository.

## Code style

- Formatting is black and isort (line length 100); lint is flake8; typing is mypy, and the
  package ships `py.typed`: every public function is annotated.
- Every public class, function and method has a docstring saying what it does, what it sends
  (the HTTP route), what it returns and what it raises.
- Arguments are keyword-only (except path ids); the wire's camelCase names are mapped to
  snake_case with explicit per-field aliases.
- Money stays a decimal string end to end: never a float.
- A change of behaviour comes with a test, and with a `CHANGELOG.md` entry under `Unreleased`.

## Website snippets

The code on [qbitflow.app/docs](https://qbitflow.app/docs) and the Python code blocks of
`README.md` that show an SDK capability are not hand-written: they are **named regions** of the
programs in `examples/`, which run and pass the gates above.

```python
def create_checkout(client: qbitflow.QBitFlow) -> qbitflow.CreatedCheckoutSession:
    # docs:start checkout-create-payment
    session = client.checkout_sessions.create_payment(...)
    # docs:end checkout-create-payment
    return session
```

- **Markers** are exactly `# docs:start <id>` and `# docs:end <id>` on their own lines (any
  indentation: the region is dedented when extracted). One region per id; regions never nest or
  overlap, and the id on `docs:end` matches its `docs:start`.
- **Ids** are shared by every QBitFlow SDK and are a public contract with the website: never
  rename or remove one.
- **A region reads on its own.** It uses a ready client named `client` (only `client-init` and
  `client-on-behalf-of` build theirs), refers to the SDK as `qbitflow.…` (`import qbitflow`), and
  takes the ids it needs but doesn't create from variables defined just outside it
  (`payment_uuid`, `subscription_uuid`, `session_uuid`, `member_uuid`). Keys come from
  `QBITFLOW_API_KEY` and `QBITFLOW_WEBHOOK_SECRET`, never from the code.
- **README blocks** are `<!-- docs:snippet <id> -->` / `<!-- /docs:snippet -->` pairs whose code
  is copied from the region: **never edit them by hand**. If you change a region, say so in your
  pull request and a maintainer regenerates the README blocks.
- `examples/snippets.manifest.json` maps every id to the file holding its region.
