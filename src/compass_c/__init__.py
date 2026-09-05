"""COMPASS-C: computational decision support with bounded local state."""

from .calculations import calculate
from .core import VERSION, CompassError, Notebook

__all__ = ["VERSION", "CompassError", "Notebook", "calculate"]
