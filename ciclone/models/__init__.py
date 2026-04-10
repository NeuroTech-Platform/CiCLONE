"""
Models package for CiCLONE application.

This package contains all data models following the MVC pattern:
- ElectrodeModel: Manages electrode data and business logic
- CoordinateModel: Handles electrode coordinate data
- ImageModel: Manages image data and operations
- CrosshairModel: Manages crosshair state and business logic
- SubjectModel: Manages subject data, validation, and state
- ApplicationModel: Manages centralized application state and configuration
- AtlasModel: Atlas data models for FreeSurfer-based electrode labeling
"""

from .electrode_model import ElectrodeModel
from .coordinate_model import CoordinateModel
from .image_model import ImageModel
from .crosshair_model import CrosshairModel
from .subject_model import SubjectModel, SubjectData, SubjectValidationResult
from .application_model import ApplicationModel, WorkerState, UIState
from .subject_data_factory import SubjectDataFactory
from .atlas_model import AtlasType, AtlasLabel, AtlasData, UNKNOWN_LABEL

__all__ = [
    'ElectrodeModel', 'CoordinateModel', 'ImageModel', 'CrosshairModel',
    'SubjectModel', 'SubjectData', 'SubjectValidationResult',
    'ApplicationModel', 'WorkerState', 'UIState', 'SubjectDataFactory',
    'AtlasType', 'AtlasLabel', 'AtlasData', 'UNKNOWN_LABEL'
] 