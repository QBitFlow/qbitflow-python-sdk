# QBitFlow Python SDK

> **Website snippets.** The code on qbitflow.app/docs and in this README comes from `# docs:start <id>` … `# docs:end <id>` regions in `examples/`. Every change keeps them true:
> - **New public capability:** add a region, an id in the hub's `snippets/catalog.json` (the same id across all SDKs), and the manifest entry, plus the README block via `scripts/embed-snippets.mjs`.
> - **Changed capability:** update the region's code. Never hand-edit an embedded README block: re-run the script.
> - **Ids are a public contract with the website.** Never rename or remove one silently. To retire an id, keep it until the website no longer uses it, and note it in the CHANGELOG.
> - **Before committing:** the examples run, the manifest check passes, and `embed-snippets --check` passes.
> - **Unsupported ids:** an id the SDK can't support goes under `unsupported` with a reason. Never write placeholder code.

Commands (from this directory; details in CONTRIBUTING.md):
- Gates: `mypy qbitflow/`, `flake8 qbitflow/ tests/ examples/`, `black --check qbitflow/ tests/ examples/`, `isort --check-only qbitflow/ tests/ examples/`, `pytest -q -p no:cacheprovider` (with `QBITFLOW_*` unset).
- Snippets: `node ../../scripts/embed-snippets.mjs .` rewrites the README blocks; `--check` verifies them (also run by `tests/test_snippets.py`).
