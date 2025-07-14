"""
Controllers package for CiCLONE application.

This package contains all controllers following the MVC pattern:
- ElectrodeController: Coordinates electrode operations between models and views
- ImageController: Manages image-related operations and view updates
- CrosshairController: Coordinates crosshair operations between models and views
- SubjectController: Manages subject operations and coordinates between subject model and services
- ProcessingController: Manages image processing operations and worker coordination
- TreeViewController: Manages tree view operations and file system model
- MainController: Central coordinator for all application operations and workflow management
"""

from .electrode_controller import ElectrodeController
from .image_controller import ImageController
from .crosshair_controller import CrosshairController
from .subject_controller import SubjectController
from .processing_controller import ProcessingController
from .tree_view_controller import TreeViewController
from .main_controller import MainController

__all__ = [
    'ElectrodeController', 
    'ImageController', 
    'CrosshairController', 
    'SubjectController', 
    'ProcessingController', 
    'TreeViewController',
    'MainController'
] 