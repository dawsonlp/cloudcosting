"""Multi-cloud infrastructure cost estimation tool."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cloudcosting")
except PackageNotFoundError:
    __version__ = "dev"
