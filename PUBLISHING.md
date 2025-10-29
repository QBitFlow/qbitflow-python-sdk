# Publishing to PyPI

This guide provides step-by-step instructions for publishing the QBitFlow Python SDK to PyPI.

## Prerequisites

Before publishing, ensure you have:

1. A PyPI account (create one at https://pypi.org/account/register/)
2. A TestPyPI account (create one at https://test.pypi.org/account/register/)
3. API tokens from both PyPI and TestPyPI
4. Required tools installed:
    ```bash
    pip install build twine
    ```

## Step 1: Prepare for Release

### 1.1 Update Version Number

Edit `qbitflow/__init__.py` and update the version:

```python
__version__ = "1.0.0"  # Update this
```

### 1.2 Update CHANGELOG.md

Document all changes in `CHANGELOG.md`:

```markdown
## [1.0.0] - 2025-01-15

### Added

-   Initial release
-   One-time payment support
-   Recurring subscriptions
-   Pay-as-you-go subscriptions
-   Customer management
-   Product management
-   Comprehensive documentation

### Changed

-   N/A (initial release)

### Fixed

-   N/A (initial release)
```

### 1.3 Run Tests

Ensure all tests pass:

```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=qbitflow --cov-report=html

# Check code style
flake8 qbitflow tests

# Format code
black qbitflow tests

# Type checking
mypy qbitflow
```

### 1.4 Verify Package Structure

Check that all files are in place:

```bash
tree -L 2 -I '__pycache__|*.pyc|.git'
```

Expected structure:

```
qbitflow-python-sdk/
├── qbitflow/           # Main package
├── tests/              # Tests
├── examples/           # Examples
├── README.md           # Documentation
├── LICENSE             # MIT License
├── setup.py            # Setup configuration
├── pyproject.toml      # Build configuration
├── MANIFEST.in         # Package manifest
├── CHANGELOG.md        # Version history
└── PUBLISHING.md       # This file
```

## Step 2: Build the Package

### 2.1 Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf build/ dist/ *.egg-info/
```

### 2.2 Build Distribution Files

```bash
# Build source distribution and wheel
python -m build
```

This creates two files in `dist/`:

-   `qbitflow-1.0.0.tar.gz` (source distribution)
-   `qbitflow-1.0.0-py3-none-any.whl` (wheel)

### 2.3 Verify Build

```bash
# List distribution files
ls -lh dist/

# Check wheel contents
unzip -l dist/qbitflow-1.0.0-py3-none-any.whl

# Verify package metadata
tar -tzf dist/qbitflow-1.0.0.tar.gz
```

## Step 3: Test on TestPyPI

Before publishing to the real PyPI, test on TestPyPI first.

### 3.1 Configure TestPyPI Credentials

Create or edit `~/.pypirc`:

```ini
[testpypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Your TestPyPI token
```

### 3.2 Upload to TestPyPI

```bash
# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*
```

### 3.3 Test Installation from TestPyPI

```bash
# Create a test environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ qbitflow

# Test the package
python -c "from qbitflow import QBitFlow; print('Import successful')"

# Run a simple test
python examples/main.py

# Deactivate and remove test environment
deactivate
rm -rf test_env/
```

### 3.4 Verify on TestPyPI

Visit your package page:

-   https://test.pypi.org/project/qbitflow/

Check:

-   Version number is correct
-   Description renders properly
-   Links work
-   Classifiers are correct

## Step 4: Publish to PyPI

Once testing is successful, publish to the real PyPI.

### 4.1 Configure PyPI Credentials

Edit `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Your PyPI token
```

### 4.2 Upload to PyPI

```bash
# Upload to PyPI (this is permanent!)
python -m twine upload dist/*
```

You'll see output like:

```
Uploading distributions to https://upload.pypi.org/legacy/
Uploading qbitflow-1.0.0-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Uploading qbitflow-1.0.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View at:
https://pypi.org/project/qbitflow/1.0.0/
```

### 4.3 Verify on PyPI

Visit your package page:

-   https://pypi.org/project/qbitflow/

### 4.4 Test Installation

```bash
# Create a test environment
python -m venv prod_test_env
source prod_test_env/bin/activate

# Install from PyPI
pip install qbitflow

# Test the package
python -c "from qbitflow import QBitFlow; print('Installation successful!')"

# Deactivate
deactivate
rm -rf prod_test_env/
```

## Step 5: Post-Release

### 5.1 Create Git Tag

```bash
# Commit all changes
git add .
git commit -m "Release version 1.0.0"

# Create and push tag
git tag -a v1.0.0 -m "Version 1.0.0"
git push origin main
git push origin v1.0.0
```

### 5.2 Create GitHub Release

1. Go to https://github.com/qbitflow/qbitflow-python-sdk/releases
2. Click "Create a new release"
3. Select tag: v1.0.0
4. Title: "QBitFlow Python SDK v1.0.0"
5. Description: Copy from CHANGELOG.md
6. Attach: Distribution files from `dist/`
7. Click "Publish release"

### 5.3 Update Documentation

-   Update documentation site with new version
-   Announce release on:
    -   Blog
    -   Twitter
    -   Discord/Slack community
    -   Email newsletter

## Step 6: Troubleshooting

### Issue: "File already exists"

If you get this error when uploading:

```
HTTPError: 400 Bad Request from https://upload.pypi.org/legacy/
File already exists.
```

Solution: You cannot reupload the same version. You must:

1. Increment the version number
2. Rebuild the package
3. Upload again

### Issue: "Invalid distribution file"

If twine reports an invalid distribution:

```bash
# Check the package
twine check dist/*

# If issues found, rebuild
rm -rf dist/
python -m build
```

### Issue: "Authentication failed"

If upload fails with authentication error:

1. Verify your API token is correct in `~/.pypirc`
2. Ensure token has upload permissions
3. Check token hasn't expired

### Issue: "Metadata is missing required fields"

Ensure these are set in `setup.py`:

-   `name`
-   `version`
-   `author`
-   `author_email`
-   `description`
-   `long_description`
-   `url`

## Automated Publishing with GitHub Actions

For automated releases, create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
    release:
        types: [published]

jobs:
    publish:
        runs-on: ubuntu-latest
        steps:
            - uses: actions/checkout@v3

            - name: Set up Python
              uses: actions/setup-python@v4
              with:
                  python-version: "3.9"

            - name: Install dependencies
              run: |
                  python -m pip install --upgrade pip
                  pip install build twine

            - name: Build package
              run: python -m build

            - name: Publish to PyPI
              env:
                  TWINE_USERNAME: __token__
                  TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
              run: twine upload dist/*
```

Then add `PYPI_API_TOKEN` to your GitHub repository secrets.

## Best Practices

1. **Always test on TestPyPI first**
2. **Use semantic versioning** (MAJOR.MINOR.PATCH)
3. **Keep CHANGELOG.md updated**
4. **Run all tests before publishing**
5. **Tag releases in Git**
6. **Create GitHub releases with notes**
7. **Use API tokens, not passwords**
8. **Never upload the same version twice**
9. **Keep credentials secure** (use environment variables)
10. **Monitor package downloads and issues**

## Useful Commands

```bash
# Check package description will render on PyPI
python -m readme_renderer README.md -o /tmp/README.html

# Validate package before upload
twine check dist/*

# View package info
python setup.py --version
python setup.py --name
python setup.py --author
python setup.py --classifiers

# List package contents
tar -tzf dist/qbitflow-*.tar.gz | head -20

# Remove a package from PyPI (limited window)
# Contact PyPI support at https://pypi.org/help/
```

## Resources

-   PyPI: https://pypi.org
-   TestPyPI: https://test.pypi.org
-   Python Packaging Guide: https://packaging.python.org
-   Twine Documentation: https://twine.readthedocs.io
-   Setuptools Documentation: https://setuptools.pypa.io

## Support

If you encounter issues during publishing:

-   Check the [Python Packaging Guide](https://packaging.python.org)
-   Ask on the [Python Packaging Discourse](https://discuss.python.org/c/packaging)
-   Contact QBitFlow support: support@qbitflow.app
