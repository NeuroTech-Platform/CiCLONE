"""
Abstract base class for electrode detectors.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np

from ciclone.services.detection.detected_electrode import DetectedElectrode


class BaseElectrodeDetector(ABC):
    """
    Abstract base class for electrode detection algorithms.
    
    Subclasses implement specific detection methods (classical CV, SAM, etc.)
    while sharing common interface and utilities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the detector with optional configuration.
        
        Args:
            config: Dictionary of configuration parameters
        """
        self.config = config or {}
    
    @abstractmethod
    def detect(self, volume_data: np.ndarray, **kwargs) -> List[DetectedElectrode]:
        """
        Detect electrodes in the given volume data.
        
        Args:
            volume_data: 3D numpy array of image intensities
            **kwargs: Additional detection parameters
            
        Returns:
            List of DetectedElectrode objects
        """
        pass
    
    @abstractmethod
    def get_detector_name(self) -> str:
        """Return the name of this detector implementation."""
        pass
    
    @abstractmethod
    def get_supported_modalities(self) -> List[str]:
        """Return list of supported image modalities (e.g., ['CT', 'MRI'])."""
        pass
    
    def validate_volume(self, volume_data: np.ndarray) -> bool:
        """
        Validate that the volume data is suitable for detection.
        
        Args:
            volume_data: 3D numpy array to validate
            
        Returns:
            True if valid, False otherwise
        """
        if volume_data is None:
            return False
        if not isinstance(volume_data, np.ndarray):
            return False
        if volume_data.ndim != 3:
            return False
        if volume_data.size == 0:
            return False
        return True
    
    def preprocess_volume(self, volume_data: np.ndarray) -> np.ndarray:
        """
        Preprocess volume data before detection.
        
        Default implementation returns data as-is. Override for custom preprocessing.
        
        Args:
            volume_data: Raw 3D volume data
            
        Returns:
            Preprocessed volume data
        """
        return volume_data
