"""
SAM-based electrode detector for MRI images and difficult CT cases.

Uses MedSAM or MobileSAM for segmentation when classical CV methods
are insufficient (e.g., MRI where electrodes don't appear as bright
as in CT).

This module is optional - it gracefully handles missing dependencies.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import warnings

from ciclone.services.detection.base_detector import BaseElectrodeDetector
from ciclone.services.detection.detected_electrode import DetectedElectrode
from ciclone.services.detection.electrode_clustering import (
    cluster_contacts,
    fit_electrode_axis,
    filter_linear_clusters,
    suggest_electrode_name,
)

# Check for optional dependencies
SAM_AVAILABLE = False
TORCH_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    from segment_anything import sam_model_registry, SamPredictor
    SAM_AVAILABLE = True
except ImportError:
    pass


class SAMElectrodeDetector(BaseElectrodeDetector):
    """
    SAM-based detector for electrode localization in MRI and difficult CT images.
    
    This detector uses Segment Anything Model (SAM) variants optimized for
    medical imaging. It's particularly useful for:
    - MRI images where electrodes create susceptibility artifacts
    - CT images with low contrast or unusual scanning protocols
    - Refining detections from the classical CV detector
    
    Supported models:
    - MedSAM: Fine-tuned SAM for medical images (~300MB)
    - MobileSAM: Lightweight SAM variant for fast inference (~40MB)
    - SAM ViT-B: Original SAM base model (~375MB)
    
    Note: This detector requires torch and segment-anything packages.
    If not available, it will raise an error on initialization.
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "model_type": "vit_b",       # SAM model variant
        "checkpoint_path": None,      # Path to model checkpoint
        "device": "auto",             # 'cuda', 'cpu', or 'auto'
        "min_contacts_per_electrode": 3,
        "clustering_eps": 15.0,
        "linearity_threshold": 0.75,
        "points_per_slice": 10,       # Auto-generated points per slice
        "iou_threshold": 0.5,         # Minimum IoU for valid mask
        "slice_step": 5,              # Process every Nth slice for speed
    }
    
    # Model registry for different SAM variants
    MODEL_INFO = {
        "vit_b": {
            "name": "SAM ViT-B",
            "size_mb": 375,
            "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
        },
        "vit_l": {
            "name": "SAM ViT-L", 
            "size_mb": 1200,
            "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth"
        },
        "vit_h": {
            "name": "SAM ViT-H",
            "size_mb": 2400,
            "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
        },
        "medsam": {
            "name": "MedSAM",
            "size_mb": 300,
            "url": None  # User must provide checkpoint
        },
        "mobilesam": {
            "name": "MobileSAM",
            "size_mb": 40,
            "url": None  # User must provide checkpoint
        }
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SAM detector.
        
        Args:
            config: Configuration parameters including model_type and checkpoint_path
            
        Raises:
            ImportError: If torch or segment-anything not installed
            FileNotFoundError: If checkpoint file not found
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for SAM detector. "
                "Install with: pip install torch"
            )
        
        if not SAM_AVAILABLE:
            raise ImportError(
                "segment-anything is required for SAM detector. "
                "Install with: pip install segment-anything"
            )
        
        merged_config = self.DEFAULT_CONFIG.copy()
        if config:
            merged_config.update(config)
        super().__init__(merged_config)
        
        self._model = None
        self._predictor = None
        self._device = None
    
    def get_detector_name(self) -> str:
        model_type = self.config.get("model_type", "vit_b")
        model_info = self.MODEL_INFO.get(model_type, {})
        return f"SAM Detector ({model_info.get('name', model_type)})"
    
    def get_supported_modalities(self) -> List[str]:
        return ["CT", "MRI"]
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if the SAM model is loaded."""
        return self._model is not None and self._predictor is not None
    
    def load_model(self, checkpoint_path: Optional[str] = None) -> bool:
        """
        Load the SAM model.
        
        Args:
            checkpoint_path: Path to model checkpoint file
            
        Returns:
            True if model loaded successfully
        """
        checkpoint = checkpoint_path or self.config.get("checkpoint_path")
        
        if checkpoint is None:
            raise ValueError(
                "Model checkpoint path must be provided. "
                "Download from: https://github.com/facebookresearch/segment-anything"
            )
        
        # Determine device
        device_config = self.config.get("device", "auto")
        if device_config == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device_config
        
        model_type = self.config.get("model_type", "vit_b")
        
        try:
            # Load SAM model
            self._model = sam_model_registry[model_type](checkpoint=checkpoint)
            self._model.to(device=self._device)
            self._model.eval()
            
            # Create predictor
            self._predictor = SamPredictor(self._model)
            
            return True
            
        except Exception as e:
            warnings.warn(f"Failed to load SAM model: {e}")
            self._model = None
            self._predictor = None
            return False
    
    def detect(self, volume_data: np.ndarray, **kwargs) -> List[DetectedElectrode]:
        """
        Detect electrodes in volume data using SAM.
        
        Args:
            volume_data: 3D numpy array of image intensities
            **kwargs: Additional detection parameters
            
        Returns:
            List of DetectedElectrode objects
        """
        if not self.validate_volume(volume_data):
            return []
        
        if not self.is_model_loaded:
            checkpoint = kwargs.get("checkpoint_path") or self.config.get("checkpoint_path")
            if not self.load_model(checkpoint):
                warnings.warn("SAM model not loaded. Cannot perform detection.")
                return []
        
        params = self.config.copy()
        params.update(kwargs)
        
        # Collect all detected points across slices
        all_centroids = []
        
        slice_step = params.get("slice_step", 5)
        
        # Process axial slices
        for z in range(0, volume_data.shape[2], slice_step):
            slice_2d = volume_data[:, :, z]
            slice_centroids = self._detect_in_slice(slice_2d, params)
            
            # Add z coordinate
            for centroid in slice_centroids:
                all_centroids.append((centroid[0], centroid[1], z))
        
        if len(all_centroids) < params["min_contacts_per_electrode"]:
            return []
        
        centroids = np.array(all_centroids)
        
        # Cluster and build electrodes (same as CT detector)
        labels = cluster_contacts(
            centroids,
            min_cluster_size=params["min_contacts_per_electrode"],
            eps=params["clustering_eps"]
        )
        
        labels = filter_linear_clusters(
            centroids,
            labels,
            params["linearity_threshold"]
        )
        
        electrodes = self._build_electrodes_from_clusters(
            centroids,
            labels,
            volume_data.shape
        )
        
        return electrodes
    
    def _detect_in_slice(
        self, 
        slice_2d: np.ndarray,
        params: Dict[str, Any]
    ) -> List[Tuple[float, float]]:
        """
        Detect electrode contacts in a 2D slice using SAM.
        
        Returns list of (x, y) centroids in the slice.
        """
        # Normalize slice for SAM input
        slice_normalized = self._normalize_for_sam(slice_2d)
        
        # Convert to RGB (SAM expects 3-channel input)
        slice_rgb = np.stack([slice_normalized] * 3, axis=-1)
        slice_rgb = (slice_rgb * 255).astype(np.uint8)
        
        # Set image in predictor
        self._predictor.set_image(slice_rgb)
        
        # Generate automatic point prompts based on intensity
        points = self._generate_point_prompts(slice_2d, params)
        
        if len(points) == 0:
            return []
        
        centroids = []
        
        # Get masks for each point prompt
        for point in points:
            try:
                masks, scores, _ = self._predictor.predict(
                    point_coords=np.array([[point[0], point[1]]]),
                    point_labels=np.array([1]),  # Foreground
                    multimask_output=True
                )
                
                # Use best mask
                best_idx = np.argmax(scores)
                mask = masks[best_idx]
                score = scores[best_idx]
                
                if score < params.get("iou_threshold", 0.5):
                    continue
                
                # Get centroid of mask
                if mask.sum() > 0:
                    y_coords, x_coords = np.where(mask)
                    centroid_x = np.mean(x_coords)
                    centroid_y = np.mean(y_coords)
                    centroids.append((centroid_x, centroid_y))
                    
            except Exception:
                continue
        
        # Remove duplicate centroids (same contact detected multiple times)
        centroids = self._deduplicate_centroids(centroids)
        
        return centroids
    
    def _normalize_for_sam(self, slice_2d: np.ndarray) -> np.ndarray:
        """Normalize slice data to 0-1 range for SAM."""
        slice_min = slice_2d.min()
        slice_max = slice_2d.max()
        
        if slice_max - slice_min > 0:
            return (slice_2d - slice_min) / (slice_max - slice_min)
        return np.zeros_like(slice_2d, dtype=float)
    
    def _generate_point_prompts(
        self,
        slice_2d: np.ndarray,
        params: Dict[str, Any]
    ) -> List[Tuple[int, int]]:
        """
        Generate point prompts for SAM based on image intensity.
        
        For MRI, looks for dark spots (susceptibility artifacts).
        Uses adaptive thresholding to find potential electrode locations.
        """
        points_per_slice = params.get("points_per_slice", 10)
        
        # For MRI: electrodes appear as dark voids
        # For CT: electrodes appear bright
        # Use both strategies and combine
        
        points = []
        
        # Strategy 1: High intensity points (CT-like)
        threshold_high = np.percentile(slice_2d[slice_2d > 0], 95)
        high_mask = slice_2d > threshold_high
        
        if high_mask.sum() > 0:
            y_coords, x_coords = np.where(high_mask)
            # Sample points
            indices = np.random.choice(
                len(x_coords), 
                min(points_per_slice // 2, len(x_coords)),
                replace=False
            )
            for idx in indices:
                points.append((x_coords[idx], y_coords[idx]))
        
        # Strategy 2: Low intensity points (MRI susceptibility artifacts)
        threshold_low = np.percentile(slice_2d[slice_2d > 0], 5)
        low_mask = (slice_2d < threshold_low) & (slice_2d > 0)
        
        if low_mask.sum() > 0:
            y_coords, x_coords = np.where(low_mask)
            indices = np.random.choice(
                len(x_coords),
                min(points_per_slice // 2, len(x_coords)),
                replace=False
            )
            for idx in indices:
                points.append((x_coords[idx], y_coords[idx]))
        
        return points
    
    def _deduplicate_centroids(
        self,
        centroids: List[Tuple[float, float]],
        min_distance: float = 3.0
    ) -> List[Tuple[float, float]]:
        """Remove duplicate centroids that are too close together."""
        if len(centroids) <= 1:
            return centroids
        
        unique = [centroids[0]]
        
        for centroid in centroids[1:]:
            is_duplicate = False
            for existing in unique:
                dist = np.sqrt(
                    (centroid[0] - existing[0])**2 + 
                    (centroid[1] - existing[1])**2
                )
                if dist < min_distance:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(centroid)
        
        return unique
    
    def _build_electrodes_from_clusters(
        self,
        centroids: np.ndarray,
        labels: np.ndarray,
        volume_shape: Tuple[int, int, int]
    ) -> List[DetectedElectrode]:
        """Build DetectedElectrode objects from clustered centroids."""
        electrodes = []
        unique_labels = set(labels) - {-1}
        existing_names = []
        
        for cluster_label in sorted(unique_labels):
            mask = labels == cluster_label
            cluster_points = centroids[mask]
            
            if len(cluster_points) < self.config["min_contacts_per_electrode"]:
                continue
            
            tip, entry, ordered_contacts = fit_electrode_axis(
                cluster_points,
                return_ordered=True
            )
            
            name = suggest_electrode_name(tip, volume_shape, existing_names)
            existing_names.append(name)
            
            # Lower confidence for SAM detections (more uncertain than CT)
            confidence = min(0.9, 0.5 + len(ordered_contacts) * 0.03)
            
            electrode = DetectedElectrode(
                tip=tip,
                entry=entry,
                contacts=[tuple(c) for c in ordered_contacts],
                confidence=confidence,
                suggested_name=name,
                electrode_type=None  # SAM doesn't infer type well
            )
            
            electrodes.append(electrode)
        
        electrodes.sort(key=lambda e: e.confidence, reverse=True)
        return electrodes
    
    def detect_with_prompts(
        self,
        volume_data: np.ndarray,
        point_prompts: List[Tuple[int, int, int]],
        **kwargs
    ) -> List[DetectedElectrode]:
        """
        Detect electrodes using user-provided point prompts.
        
        This is useful for semi-automatic detection where the user
        provides approximate electrode locations.
        
        Args:
            volume_data: 3D image volume
            point_prompts: List of (x, y, z) points to use as prompts
            **kwargs: Additional parameters
            
        Returns:
            List of detected electrodes near the prompts
        """
        if not self.is_model_loaded:
            checkpoint = kwargs.get("checkpoint_path") or self.config.get("checkpoint_path")
            if not self.load_model(checkpoint):
                return []
        
        params = self.config.copy()
        params.update(kwargs)
        
        all_centroids = []
        
        for prompt in point_prompts:
            x, y, z = prompt
            
            # Get slice containing the prompt
            slice_2d = volume_data[:, :, z]
            
            # Normalize and prepare for SAM
            slice_normalized = self._normalize_for_sam(slice_2d)
            slice_rgb = np.stack([slice_normalized] * 3, axis=-1)
            slice_rgb = (slice_rgb * 255).astype(np.uint8)
            
            self._predictor.set_image(slice_rgb)
            
            try:
                masks, scores, _ = self._predictor.predict(
                    point_coords=np.array([[x, y]]),
                    point_labels=np.array([1]),
                    multimask_output=True
                )
                
                best_idx = np.argmax(scores)
                mask = masks[best_idx]
                
                if mask.sum() > 0:
                    y_coords, x_coords = np.where(mask)
                    centroid_x = np.mean(x_coords)
                    centroid_y = np.mean(y_coords)
                    all_centroids.append((centroid_x, centroid_y, z))
                    
            except Exception:
                continue
        
        if len(all_centroids) < 2:
            return []
        
        centroids = np.array(all_centroids)
        
        # For prompted detection, assume all points belong to same electrode
        tip, entry, ordered = fit_electrode_axis(centroids, return_ordered=True)
        
        electrode = DetectedElectrode(
            tip=tip,
            entry=entry,
            contacts=[tuple(c) for c in ordered],
            confidence=0.8,
            suggested_name="Prompted"
        )
        
        return [electrode]


def is_sam_available() -> bool:
    """Check if SAM dependencies are available."""
    return SAM_AVAILABLE and TORCH_AVAILABLE


def get_available_sam_models() -> List[str]:
    """Get list of available SAM model types."""
    if not is_sam_available():
        return []
    return list(SAMElectrodeDetector.MODEL_INFO.keys())
