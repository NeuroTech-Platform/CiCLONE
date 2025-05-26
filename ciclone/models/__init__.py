"""
Models package for CiCLONE application.

This package contains all data models following the MVC pattern:
- ElectrodeModel: Manages electrode data and business logic
- CoordinateModel: Handles electrode coordinate data
- ImageModel: Manages image data and operations
"""

from .electrode_model import ElectrodeModel
from .coordinate_model import CoordinateModel
from .image_model import ImageModel

__all__ = ['ElectrodeModel', 'CoordinateModel', 'ImageModel'] 