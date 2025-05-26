"""
Controllers package for CiCLONE application.

This package contains all controllers following the MVC pattern:
- ElectrodeController: Coordinates electrode operations between models and views
- ImageController: Manages image-related operations and view updates
"""

from .electrode_controller import ElectrodeController
from .image_controller import ImageController

__all__ = ['ElectrodeController', 'ImageController'] 