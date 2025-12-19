"""
Unified detection service that selects the appropriate detector.

Provides a high-level interface for electrode detection that automatically
chooses between classical CV and SAM-based methods based on image modality
and available dependencies.
"""

from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import warnings

from ciclone.services.detection.base_detector import BaseElectrodeDetector
from ciclone.services.detection.detected_electrode import DetectedElectrode
from ciclone.services.detection.ct_detector import CTElectrodeDetector


class DetectionService:
    """
    High-level service for electrode detection.
    
    Automatically selects the appropriate detection method based on:
    - Image modality (CT vs MRI)
    - Available dependencies (torch/SAM)
    - User preferences
    
    Usage:
        service = DetectionService()
        electrodes = service.detect(volume_data, modality="CT")
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the detection service.
        
        Args:
            config: Configuration options including:
                - ct_config: Config for CT detector
                - sam_config: Config for SAM detector
                - prefer_sam: Use SAM even when CT detector would work
        """
        self.config = config or {}
        
        # Initialize CT detector (always available)
        ct_config = self.config.get("ct_config", {})
        self._ct_detector = CTElectrodeDetector(ct_config)
        
        # SAM detector initialized lazily (optional dependency)
        self._sam_detector = None
        self._sam_available = None
    
    @property
    def sam_available(self) -> bool:
        """Check if SAM detector is available."""
        if self._sam_available is None:
            try:
                from ciclone.services.detection.sam_detector import is_sam_available
                self._sam_available = is_sam_available()
            except ImportError:
                self._sam_available = False
        return self._sam_available
    
    def _get_sam_detector(self) -> Optional[BaseElectrodeDetector]:
        """Get or initialize the SAM detector."""
        if self._sam_detector is None and self.sam_available:
            try:
                from ciclone.services.detection.sam_detector import SAMElectrodeDetector
                sam_config = self.config.get("sam_config", {})
                self._sam_detector = SAMElectrodeDetector(sam_config)
            except Exception as e:
                warnings.warn(f"Failed to initialize SAM detector: {e}")
        return self._sam_detector
    
    def detect(
        self,
        volume_data: np.ndarray,
        modality: str = "auto",
        method: str = "auto",
        **kwargs
    ) -> List[DetectedElectrode]:
        """
        Detect electrodes in volume data.
        
        Args:
            volume_data: 3D numpy array of image intensities
            modality: Image modality ('CT', 'MRI', or 'auto')
            method: Detection method ('ct', 'sam', or 'auto')
            **kwargs: Additional parameters passed to detector
            
        Returns:
            List of DetectedElectrode objects
        """
        # Determine modality if auto
        if modality == "auto":
            modality = self._detect_modality(volume_data)
        
        # Select detector
        detector = self._select_detector(modality, method)
        
        if detector is None:
            warnings.warn("No suitable detector available")
            return []
        
        # Run detection
        return detector.detect(volume_data, **kwargs)
    
    def _detect_modality(self, volume_data: np.ndarray) -> str:
        """
        Attempt to detect the image modality from data characteristics.
        
        CT images typically have:
        - Hounsfield units ranging from -1000 (air) to 3000+ (metal)
        - Bone appears at 400-1000 HU
        - Metal artifacts at 1600+ HU
        
        MRI images typically have:
        - Arbitrary intensity units
        - No specific intensity for metal
        - Lower overall intensity range
        """
        data_min = volume_data.min()
        data_max = volume_data.max()
        data_range = data_max - data_min
        
        # Check for CT characteristics
        # CT typically has values below 0 (air/water is -1000 to 0)
        has_negative = data_min < -100
        
        # CT metal artifacts are very bright (> 1500)
        has_metal_artifacts = data_max > 1500
        
        # CT has wider dynamic range
        wide_range = data_range > 2000
        
        if has_negative or has_metal_artifacts or wide_range:
            return "CT"
        
        # Default to MRI if CT characteristics not found
        return "MRI"
    
    def _select_detector(
        self,
        modality: str,
        method: str
    ) -> Optional[BaseElectrodeDetector]:
        """Select the appropriate detector based on modality and method."""
        prefer_sam = self.config.get("prefer_sam", False)
        
        if method == "ct":
            return self._ct_detector
        
        if method == "sam":
            detector = self._get_sam_detector()
            if detector is None:
                warnings.warn("SAM requested but not available, falling back to CT detector")
                return self._ct_detector
            return detector
        
        # Auto selection
        if modality == "CT" and not prefer_sam:
            return self._ct_detector
        
        if modality == "MRI":
            detector = self._get_sam_detector()
            if detector is not None:
                return detector
            warnings.warn("MRI detected but SAM not available, using CT detector")
            return self._ct_detector
        
        # Default to CT detector
        return self._ct_detector
    
    def detect_with_refinement(
        self,
        volume_data: np.ndarray,
        modality: str = "auto",
        **kwargs
    ) -> List[DetectedElectrode]:
        """
        Detect electrodes with an additional refinement pass.
        
        First runs coarse detection, then refines each electrode
        with a local search.
        
        Args:
            volume_data: 3D image volume
            modality: Image modality
            **kwargs: Additional parameters
            
        Returns:
            List of refined DetectedElectrode objects
        """
        # Initial detection
        initial_electrodes = self.detect(volume_data, modality, **kwargs)
        
        if not initial_electrodes:
            return []
        
        # Refine using CT detector's refinement method
        refined = self._ct_detector.refine_detection(
            volume_data,
            initial_electrodes,
            search_radius=kwargs.get("search_radius", 10)
        )
        
        return refined
    
    def detect_incremental(
        self,
        volume_data: np.ndarray,
        existing_electrodes: List[DetectedElectrode],
        modality: str = "auto",
        **kwargs
    ) -> List[DetectedElectrode]:
        """
        Detect additional electrodes while preserving existing ones.
        
        Useful for detecting electrodes that weren't found in initial pass.
        
        Args:
            volume_data: 3D image volume
            existing_electrodes: Already detected electrodes
            modality: Image modality
            **kwargs: Additional parameters
            
        Returns:
            Combined list of existing and newly detected electrodes
        """
        # Create mask excluding existing electrode regions
        exclusion_mask = np.ones(volume_data.shape, dtype=bool)
        
        for electrode in existing_electrodes:
            for contact in electrode.contacts:
                x, y, z = int(contact[0]), int(contact[1]), int(contact[2])
                radius = 10
                
                x_min = max(0, x - radius)
                x_max = min(volume_data.shape[0], x + radius)
                y_min = max(0, y - radius)
                y_max = min(volume_data.shape[1], y + radius)
                z_min = max(0, z - radius)
                z_max = min(volume_data.shape[2], z + radius)
                
                exclusion_mask[x_min:x_max, y_min:y_max, z_min:z_max] = False
        
        # Detect in remaining regions
        masked_volume = volume_data.copy()
        masked_volume[~exclusion_mask] = 0
        
        new_electrodes = self.detect(masked_volume, modality, **kwargs)
        
        # Combine results
        all_electrodes = list(existing_electrodes) + new_electrodes
        
        return all_electrodes
    
    def get_detector_info(self) -> Dict[str, Any]:
        """Get information about available detectors."""
        info = {
            "ct_detector": {
                "name": self._ct_detector.get_detector_name(),
                "available": True,
                "modalities": self._ct_detector.get_supported_modalities(),
            }
        }
        
        if self.sam_available:
            sam_detector = self._get_sam_detector()
            if sam_detector:
                info["sam_detector"] = {
                    "name": sam_detector.get_detector_name(),
                    "available": True,
                    "modalities": sam_detector.get_supported_modalities(),
                }
        else:
            info["sam_detector"] = {
                "name": "SAM Detector",
                "available": False,
                "reason": "torch and segment-anything not installed"
            }
        
        return info


def create_detection_service(
    prefer_sam: bool = False,
    ct_threshold: int = 1600,
    sam_model_type: str = "vit_b",
    sam_checkpoint: Optional[str] = None
) -> DetectionService:
    """
    Factory function to create a configured detection service.
    
    Args:
        prefer_sam: Use SAM even for CT images
        ct_threshold: Threshold for CT detector
        sam_model_type: SAM model variant
        sam_checkpoint: Path to SAM checkpoint
        
    Returns:
        Configured DetectionService instance
    """
    config = {
        "prefer_sam": prefer_sam,
        "ct_config": {
            "threshold": ct_threshold,
        },
        "sam_config": {
            "model_type": sam_model_type,
            "checkpoint_path": sam_checkpoint,
        }
    }
    
    return DetectionService(config)
