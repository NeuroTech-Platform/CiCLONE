"""
Electrode detection services for automatic localization.

This module provides both classical computer vision and ML-based
methods for detecting electrodes in CT and MRI images.

Main entry point is the DetectionService class which automatically
selects the appropriate detector based on image modality.

Example:
    from ciclone.services.detection import DetectionService
    
    service = DetectionService()
    electrodes = service.detect(volume_data, modality="CT")
    
    for electrode in electrodes:
        print(f"Found {electrode.suggested_name}: {electrode.num_contacts} contacts")
"""

from ciclone.services.detection.base_detector import BaseElectrodeDetector
from ciclone.services.detection.detected_electrode import DetectedElectrode
from ciclone.services.detection.ct_detector import CTElectrodeDetector
from ciclone.services.detection.detection_service import (
    DetectionService,
    create_detection_service,
)

# Optional SAM detector (requires torch and segment-anything)
try:
    from ciclone.services.detection.sam_detector import (
        SAMElectrodeDetector,
        is_sam_available,
        get_available_sam_models,
    )
    _SAM_EXPORTS = ["SAMElectrodeDetector", "is_sam_available", "get_available_sam_models"]
except ImportError:
    _SAM_EXPORTS = []

# Model management utilities
from ciclone.services.detection.model_loader import (
    get_default_model_dir,
    get_model_path,
    download_model,
    get_model_info,
    list_downloaded_models,
)

__all__ = [
    # Core classes
    "BaseElectrodeDetector",
    "DetectedElectrode",
    "CTElectrodeDetector",
    "DetectionService",
    "create_detection_service",
    # Model management
    "get_default_model_dir",
    "get_model_path",
    "download_model",
    "get_model_info",
    "list_downloaded_models",
] + _SAM_EXPORTS
