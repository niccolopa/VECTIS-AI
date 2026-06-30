"""Data connectors: pluggable sources of raw observations for a region.

``SampleConnector`` (the default) reads the bundled, reproducible California
dataset so VECTIS runs fully offline. Live connectors for NASA FIRMS, ERA5, and
Copernicus are provided as opt-in stubs implementing the same interface.
"""

from vectis.data.connectors.base import Connector, RawFrame
from vectis.data.connectors.sample import SampleConnector

__all__ = ["Connector", "RawFrame", "SampleConnector", "get_connector"]


def get_connector(name: str = "sample") -> Connector:
    """Resolve a connector by name. Defaults to the bundled sample connector."""
    if name == "sample":
        return SampleConnector()
    # Live connectors are imported lazily so their optional deps aren't required.
    from vectis.data.connectors import live

    return live.get_live_connector(name)
