"""Setup configuration for QBitFlow Python SDK."""

from setuptools import setup, find_packages
import os

# Read long description from README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from package
version = {}
with open(os.path.join("qbitflow", "__init__.py"), "r") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)
            break

setup(
    name="qbitflow",
    version=version.get("__version__", "1.0.0"),
    author="QBitFlow",
    author_email="support@qbitflow.app",
    description="Official Python SDK for QBitFlow - Next Generation Crypto Payment Processing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/qbitflow/qbitflow-python-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/qbitflow/qbitflow-python-sdk/issues",
        "Documentation": "https://qbitflow.app/docs",
        "Source Code": "https://github.com/qbitflow/qbitflow-python-sdk",
        "Homepage": "https://qbitflow.app",
    },
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires=">=3.8",
    install_requires=[
        "httpx>=0.24.0,<1.0.0",
        "pydantic>=2.0.0,<3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "isort>=5.12.0",
        ],
        "server": [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.23.0",
        ],
    },
    keywords=[
        "qbitflow",
        "cryptocurrency",
        "crypto",
        "payment",
        "payment-processing",
        "bitcoin",
        "solana",
        "ethereum",
        "blockchain",
        "subscription",
        "recurring-billing",
        "api-client",
        "sdk",
    ],
    include_package_data=True,
    zip_safe=False,
)
