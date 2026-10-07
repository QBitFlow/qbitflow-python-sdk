"""
Single source of truth for the SDK version.

Kept in a dependency-free module so the request layer can stamp the ``User-Agent`` header
without importing the package root (which would be circular), and so the build backend can
read the version statically without importing the SDK's dependencies.
"""

__version__ = "2.5.0"
