"""
Classical computer vision electrode detector for CT images.

Uses local maxima detection to find electrode contacts, then spacing-aware
chaining to group contacts into electrodes based on known electrode geometry.
This approach leverages the fact that SEEG electrode contacts are spaced at
regular intervals (typically 3.5mm, but varies by electrode type).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy import ndimage
from scipy.ndimage import label, center_of_mass, binary_dilation, binary_erosion
from scipy.ndimage import maximum_filter
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA

from ciclone.services.detection.base_detector import BaseElectrodeDetector
from ciclone.services.detection.detected_electrode import DetectedElectrode
from ciclone.services.detection.electrode_clustering import (
    cluster_contacts,
    fit_electrode_axis,
    filter_linear_clusters,
    estimate_inter_contact_distance,
    suggest_electrode_name,
)


class CTElectrodeDetector(BaseElectrodeDetector):
    """
    Classical CV detector for electrode localization in CT images.
    
    This detector leverages the fact that electrodes (metal) appear as very
    bright voxels in CT scans due to their high Hounsfield Units (~1600+ HU).
    
    Algorithm:
    1. Threshold volume to isolate high-intensity metal artifacts
    2. Apply morphological operations to clean up noise
    3. Label connected components (individual contacts or contact groups)
    4. Extract centroids of each component
    5. Cluster centroids using HDBSCAN/DBSCAN to group into electrodes
    6. Filter clusters for linearity (electrodes are approximately linear)
    7. Fit PCA axis to each cluster to determine tip/entry points
    """
    
    # Default configuration
    # Updated based on artifact analysis (Dec 2024):
    # - Increased min_contacts_per_electrode from 4 to 6 (41% of artifacts had <= 5 contacts)
    # - Increased linearity_threshold from 0.80 to 0.85 for initial filtering
    # - Added skull base filtering to remove bright bone artifacts at bottom of skull
    DEFAULT_CONFIG = {
        "threshold": 1400,           # Intensity threshold for local maxima
        "min_contact_size": 5,       # Minimum voxels for a valid contact
        "max_contact_size": 500,     # Maximum voxels (filter large artifacts)
        "min_contacts_per_electrode": 6,  # Minimum contacts to form electrode (was 4)
        "clustering_eps": 15.0,      # Max distance between contacts (voxels)
        "linearity_threshold": 0.85, # PCA linearity filter (was 0.80)
        "morphology_iterations": 1,  # Morphological cleanup iterations
        "use_adaptive_threshold": True,  # Adapt threshold based on histogram
        "preprocessed_ct": False,    # Set True for _CT_Electrodes type images
        "local_maxima_neighborhood": 5,  # Neighborhood size for local maxima
        "use_spacing_aware_detection": True,  # Use spacing-aware chaining
        # Standard electrode spacings in mm (Dixi electrode types)
        "electrode_spacings_mm": [3.5, 4.3, 4.6, 4.9, 6.5],
        "spacing_tolerance_mm": 1.5,  # Tolerance around expected spacing
        "voxel_size_mm": 0.55,       # Default voxel size (will be overridden if provided)
        # Skull base filtering - exclude detections near bottom of volume
        "skull_base_filter_enabled": True,  # Enable skull base artifact filtering
        "skull_base_margin_percent": 15,    # Exclude bottom X% of Z-axis (skull base)
        # Maximum contacts per electrode (prevent over-grouping)
        "max_contacts_per_electrode": 18,   # Max contacts known from electrode definitions
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize CT detector with configuration.
        
        Args:
            config: Override default configuration parameters
        """
        merged_config = self.DEFAULT_CONFIG.copy()
        if config:
            merged_config.update(config)
        super().__init__(merged_config)
    
    def get_detector_name(self) -> str:
        return "CT Classical CV Detector"
    
    def get_supported_modalities(self) -> List[str]:
        return ["CT"]
    
    def detect(self, volume_data: np.ndarray, **kwargs) -> List[DetectedElectrode]:
        """
        Detect electrodes in CT volume data.
        
        Uses a two-stage approach:
        1. Local maxima detection to find candidate contact positions
        2. Spacing-aware chaining to group contacts into electrodes
        
        Args:
            volume_data: 3D numpy array of CT intensities
            **kwargs: Override config parameters for this detection
                - voxel_size_mm: Voxel size in mm (important for spacing)
            
        Returns:
            List of DetectedElectrode objects
        """
        if not self.validate_volume(volume_data):
            return []
        
        # Merge kwargs with config
        params = self.config.copy()
        params.update(kwargs)
        
        # Use spacing-aware detection if enabled
        if params.get("use_spacing_aware_detection", True):
            return self._detect_spacing_aware(volume_data, params)
        else:
            return self._detect_classic(volume_data, params)
    
    def _detect_spacing_aware(
        self, 
        volume_data: np.ndarray, 
        params: Dict[str, Any]
    ) -> List[DetectedElectrode]:
        """
        Detect electrodes using local maxima and spacing-aware chaining.
        
        This approach leverages known electrode geometry (contact spacing)
        to chain contacts together into electrodes.
        """
        # Step 1: Determine threshold
        threshold = self._determine_threshold(volume_data, params)
        
        # Step 2: Find local maxima
        neighborhood = params.get("local_maxima_neighborhood", 5)
        local_max = maximum_filter(volume_data, size=neighborhood)
        local_maxima = (volume_data == local_max) & (volume_data > threshold)
        
        # Label and get centroids
        labeled_maxima, num_maxima = label(local_maxima)
        
        if num_maxima == 0:
            return []
        
        centroids = np.array(center_of_mass(
            local_maxima, labeled_maxima, range(1, num_maxima + 1)
        ))
        
        if len(centroids) < params["min_contacts_per_electrode"]:
            return []
        
        # Step 2.5: Filter out skull base artifacts
        # The skull base (bottom of volume) often has bright bone artifacts
        if params.get("skull_base_filter_enabled", True):
            margin_pct = params.get("skull_base_margin_percent", 15)
            z_dim = volume_data.shape[2]
            min_z = int(z_dim * margin_pct / 100)
            
            # Filter centroids below min_z
            valid_mask = centroids[:, 2] >= min_z
            centroids = centroids[valid_mask]
            
            if len(centroids) < params["min_contacts_per_electrode"]:
                return []
        
        # Step 3: Find chains using multiple spacing ranges
        voxel_size = params.get("voxel_size_mm", 0.55)
        tolerance = params.get("spacing_tolerance_mm", 1.5)
        
        # Build spacing ranges covering all electrode types
        # Standard: 3.5mm, Variants: 4.3, 4.6, 4.9mm, Wide: 6.5mm
        spacing_ranges = [
            (2.0, 5.0),   # Standard electrodes (3.5mm ± 1.5mm)
            (3.5, 6.0),   # Medium spacing variants
            (5.0, 8.0),   # Wide spacing variants (6.5mm)
        ]
        
        all_chains = []
        for min_mm, max_mm in spacing_ranges:
            chains = self._find_spacing_chains(
                centroids, 
                min_mm / voxel_size, 
                max_mm / voxel_size,
                params["min_contacts_per_electrode"],
                params["linearity_threshold"]
            )
            all_chains.extend(chains)
        
        # Remove duplicate chains (overlapping centers)
        unique_chains = []
        for chain in all_chains:
            is_dup = False
            for uc in unique_chains:
                if np.linalg.norm(chain['center'] - uc['center']) < 5:
                    # Keep the one with more contacts
                    if len(chain['points']) > len(uc['points']):
                        unique_chains.remove(uc)
                        unique_chains.append(chain)
                    is_dup = True
                    break
            if not is_dup:
                unique_chains.append(chain)
        
        # Step 4: Build electrode objects
        electrodes = []
        existing_names = []

        for chain in unique_chains:
            points = chain['points']

            # Fit axis and order contacts
            tip, entry, ordered_contacts = fit_electrode_axis(
                points, return_ordered=True
            )

            # Estimate spacing
            mean_dist, std_dist = estimate_inter_contact_distance(ordered_contacts)

            # Calculate confidence
            confidence = self._calculate_confidence(
                ordered_contacts, mean_dist, std_dist
            )

            # Suggest name and type
            name = suggest_electrode_name(tip, volume_data.shape, existing_names)
            existing_names.append(name)

            electrode_type = self._infer_electrode_type(
                len(ordered_contacts), mean_dist * voxel_size
            )

            electrode = DetectedElectrode(
                tip=tip,
                entry=entry,
                contacts=[tuple(c) for c in ordered_contacts],
                confidence=confidence,
                suggested_name=name,
                electrode_type=electrode_type
            )
            electrodes.append(electrode)
        
        # Sort by confidence
        electrodes.sort(key=lambda e: e.confidence, reverse=True)
        
        return electrodes
    
    def _find_spacing_chains(
        self,
        centroids: np.ndarray,
        min_spacing: float,
        max_spacing: float,
        min_length: int,
        linearity_threshold: float
    ) -> List[Dict]:
        """
        Find linear chains of points with specific spacing.
        
        Builds an adjacency graph where contacts are connected if they're
        at the expected electrode spacing, then finds connected components.
        """
        # Build adjacency matrix based on spacing
        distances = cdist(centroids, centroids)
        adjacency = (distances >= min_spacing) & (distances <= max_spacing)
        
        # Find connected components
        n = len(centroids)
        visited = np.zeros(n, dtype=bool)
        chains = []
        
        for start in range(n):
            if visited[start]:
                continue
            
            # BFS to find connected component
            component = []
            queue = [start]
            while queue:
                node = queue.pop(0)
                if visited[node]:
                    continue
                visited[node] = True
                component.append(node)
                
                for neighbor in np.where(adjacency[node])[0]:
                    if not visited[neighbor]:
                        queue.append(neighbor)
            
            # Check if component is valid (enough points and linear)
            if len(component) >= min_length:
                pts = centroids[component]
                pca = PCA(n_components=min(3, len(pts)))
                pca.fit(pts)
                linearity = pca.explained_variance_ratio_[0]
                
                if linearity >= linearity_threshold:
                    chains.append({
                        'indices': component,
                        'points': pts,
                        'center': pts.mean(axis=0),
                        'linearity': linearity
                    })
        
        return chains
    
    def _detect_classic(
        self, 
        volume_data: np.ndarray, 
        params: Dict[str, Any]
    ) -> List[DetectedElectrode]:
        """
        Classic detection using connected components and HDBSCAN clustering.
        
        Fallback method when spacing-aware detection is disabled.
        """
        # Step 1: Determine threshold
        threshold = self._determine_threshold(volume_data, params)
        
        # Step 2: Create binary mask of high-intensity voxels
        binary_mask = volume_data > threshold
        
        # Step 3: Morphological cleanup
        binary_mask = self._morphological_cleanup(
            binary_mask, 
            params["morphology_iterations"]
        )
        
        # Step 4: Label connected components
        labeled_array, num_features = label(binary_mask)
        
        if num_features == 0:
            return []
        
        # Step 5: Extract valid contact centroids
        centroids, component_sizes = self._extract_contact_centroids(
            binary_mask,
            labeled_array,
            num_features,
            params["min_contact_size"],
            params["max_contact_size"]
        )

        if len(centroids) < params["min_contacts_per_electrode"]:
            return []

        # Step 5.5: Filter out skull base artifacts
        if params.get("skull_base_filter_enabled", True):
            margin_pct = params.get("skull_base_margin_percent", 15)
            z_dim = volume_data.shape[2]
            min_z = int(z_dim * margin_pct / 100)
            
            # Filter centroids below min_z
            valid_mask = centroids[:, 2] >= min_z
            centroids = centroids[valid_mask]
            
            if len(centroids) < params["min_contacts_per_electrode"]:
                return []

        # Step 6: Cluster centroids into electrode groups
        labels = cluster_contacts(
            centroids,
            min_cluster_size=params["min_contacts_per_electrode"],
            eps=params["clustering_eps"]
        )
        
        # Step 7: Filter for linear clusters (electrodes are linear)
        labels = filter_linear_clusters(
            centroids, 
            labels, 
            params["linearity_threshold"]
        )
        
        # Step 8: Build electrode objects from clusters
        electrodes = self._build_electrodes_from_clusters(
            centroids, 
            labels, 
            volume_data.shape
        )
        
        return electrodes
    
    def _determine_threshold(
        self, 
        volume_data: np.ndarray, 
        params: Dict[str, Any]
    ) -> float:
        """
        Determine the intensity threshold for metal detection.
        
        If adaptive thresholding is enabled, analyzes the histogram to find
        a suitable threshold. Otherwise uses the configured fixed threshold.
        
        For pre-processed CT files (electrode-isolated), uses higher percentiles.
        """
        if not params.get("use_adaptive_threshold", True):
            return params["threshold"]
        
        base_threshold = params["threshold"]
        
        # Check if this looks like a pre-processed CT file
        # Pre-processed files typically have electrodes already isolated
        # and higher overall intensity in the metal regions
        is_preprocessed = params.get("preprocessed_ct", False)
        
        # Auto-detect pre-processing based on intensity distribution
        if not is_preprocessed:
            # Pre-processed files have most voxels near zero or negative
            # with only electrodes being bright
            positive_voxels = volume_data[volume_data > 0]
            if len(positive_voxels) > 0:
                percentile_99 = np.percentile(positive_voxels, 99)
                percentile_999 = np.percentile(positive_voxels, 99.9)
                
                # If 99.9th percentile is much higher than 99th, likely preprocessed
                # with isolated bright metal artifacts
                if percentile_999 > percentile_99 * 1.3:
                    is_preprocessed = True
        
        if is_preprocessed:
            # For pre-processed files, use higher threshold
            # Target the brightest voxels (metal contacts)
            positive_voxels = volume_data[volume_data > 0]
            if len(positive_voxels) > 0:
                # Use ~98th percentile for pre-processed data
                adaptive_threshold = np.percentile(positive_voxels, 97.5)
                return max(adaptive_threshold, base_threshold)
        
        # Standard CT processing
        # Get histogram of high-intensity region
        high_intensity_mask = volume_data > (base_threshold * 0.5)
        high_values = volume_data[high_intensity_mask]
        
        if len(high_values) == 0:
            return base_threshold
        
        # Find the threshold that captures metal while rejecting bone
        # Metal typically has much higher values than bone
        percentile_95 = np.percentile(volume_data[volume_data > 0], 95)
        
        # Use a threshold between 95th percentile and configured value
        # This helps adapt to different CT scanning protocols
        adaptive_threshold = max(percentile_95, base_threshold * 0.8)
        
        return min(adaptive_threshold, base_threshold * 1.5)
    
    def _morphological_cleanup(
        self, 
        binary_mask: np.ndarray, 
        iterations: int
    ) -> np.ndarray:
        """
        Apply morphological operations to clean up the binary mask.
        
        Uses opening (erosion + dilation) to remove small noise while
        preserving electrode contacts.
        """
        if iterations <= 0:
            return binary_mask
        
        # Create a small spherical structuring element
        struct = ndimage.generate_binary_structure(3, 1)
        
        # Opening: erosion followed by dilation
        # Removes small isolated noise
        cleaned = binary_erosion(binary_mask, structure=struct, iterations=iterations)
        cleaned = binary_dilation(cleaned, structure=struct, iterations=iterations)
        
        return cleaned
    
    def _extract_contact_centroids(
        self,
        binary_mask: np.ndarray,
        labeled_array: np.ndarray,
        num_features: int,
        min_size: int,
        max_size: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract centroids of valid contact components.
        
        Filters components by size to remove noise (too small) and
        large artifacts (too big).
        
        Returns:
            Tuple of (centroids array, component sizes array)
        """
        # Calculate component sizes
        component_sizes = ndimage.sum(
            binary_mask, 
            labeled_array, 
            range(1, num_features + 1)
        )
        component_sizes = np.array(component_sizes)
        
        # Filter by size
        valid_mask = (component_sizes >= min_size) & (component_sizes <= max_size)
        valid_labels = np.where(valid_mask)[0] + 1  # Labels are 1-indexed
        
        if len(valid_labels) == 0:
            return np.array([]).reshape(0, 3), np.array([])
        
        # Calculate centroids for valid components
        centroids = center_of_mass(
            binary_mask, 
            labeled_array, 
            valid_labels
        )
        centroids = np.array(centroids)
        
        return centroids, component_sizes[valid_mask]
    
    def _build_electrodes_from_clusters(
        self,
        centroids: np.ndarray,
        labels: np.ndarray,
        volume_shape: Tuple[int, int, int]
    ) -> List[DetectedElectrode]:
        """
        Build DetectedElectrode objects from clustered centroids.
        """
        electrodes = []
        unique_labels = set(labels) - {-1}  # Exclude noise label
        existing_names = []
        
        for cluster_label in sorted(unique_labels):
            mask = labels == cluster_label
            cluster_points = centroids[mask]
            
            if len(cluster_points) < self.config["min_contacts_per_electrode"]:
                continue
            
            # Fit axis and get ordered contacts
            tip, entry, ordered_contacts = fit_electrode_axis(
                cluster_points, 
                return_ordered=True
            )
            
            # Estimate inter-contact distance for type inference
            mean_dist, std_dist = estimate_inter_contact_distance(ordered_contacts)
            
            # Calculate confidence based on linearity and regularity
            confidence = self._calculate_confidence(
                ordered_contacts, 
                mean_dist, 
                std_dist
            )
            
            # Suggest electrode name and type
            name = suggest_electrode_name(tip, volume_shape, existing_names)
            existing_names.append(name)
            
            electrode_type = self._infer_electrode_type(
                len(ordered_contacts), 
                mean_dist
            )
            
            # Create electrode object
            electrode = DetectedElectrode(
                tip=tip,
                entry=entry,
                contacts=[tuple(c) for c in ordered_contacts],
                confidence=confidence,
                suggested_name=name,
                electrode_type=electrode_type
            )
            
            electrodes.append(electrode)
        
        # Sort by confidence (highest first)
        electrodes.sort(key=lambda e: e.confidence, reverse=True)
        
        return electrodes
    
    def _calculate_confidence(
        self,
        ordered_contacts: np.ndarray,
        mean_distance: float,
        std_distance: float
    ) -> float:
        """
        Calculate detection confidence based on electrode characteristics.
        
        Higher confidence for:
        - More contacts
        - Regular inter-contact spacing
        - Linear arrangement
        """
        if len(ordered_contacts) < 2:
            return 0.5
        
        # Factor 1: Number of contacts (more = more confident)
        contact_factor = min(1.0, len(ordered_contacts) / 15.0)
        
        # Factor 2: Spacing regularity (lower std = more regular = more confident)
        if mean_distance > 0:
            regularity_factor = max(0.0, 1.0 - (std_distance / mean_distance))
        else:
            regularity_factor = 0.5
        
        # Factor 3: Reasonable spacing (typical electrode spacing is 2-5mm in voxels ~3-10)
        spacing_factor = 1.0
        if mean_distance < 2.0 or mean_distance > 20.0:
            spacing_factor = 0.7
        
        # Combine factors
        confidence = (contact_factor * 0.3 + 
                     regularity_factor * 0.4 + 
                     spacing_factor * 0.3)
        
        return min(1.0, max(0.0, confidence))
    
    def _infer_electrode_type(
        self,
        num_contacts: int,
        mean_distance_mm: float
    ) -> Optional[str]:
        """
        Infer the electrode type based on contact count and spacing.
        
        This is a heuristic based on common SEEG electrode configurations.
        Uses both contact count and spacing to determine electrode variant.
        
        Electrode types and their spacings:
        - AM variants: 3.5mm spacing
        - BM variants: 4.3mm spacing  
        - CM variants: 4.6-4.9mm spacing
        """
        # Determine spacing variant based on mean distance
        if mean_distance_mm < 4.0:
            variant = "AM"  # Standard 3.5mm spacing
        elif mean_distance_mm < 4.5:
            variant = "BM"  # 4.3mm spacing
        else:
            variant = "CM"  # 4.6-4.9mm spacing
        
        # Common Dixi electrode configurations
        valid_contact_counts = [5, 8, 10, 12, 15, 18]
        
        # Find closest matching contact count
        closest_count = min(valid_contact_counts, key=lambda x: abs(x - num_contacts))
        
        return f"Dixi-D08-{closest_count:02d}{variant}"
    
    def detect_with_roi(
        self,
        volume_data: np.ndarray,
        roi_mask: np.ndarray,
        **kwargs
    ) -> List[DetectedElectrode]:
        """
        Detect electrodes within a specific region of interest.
        
        Args:
            volume_data: Full 3D CT volume
            roi_mask: Boolean mask defining region to search
            **kwargs: Additional detection parameters
            
        Returns:
            List of DetectedElectrode objects within ROI
        """
        # Apply ROI mask
        masked_volume = volume_data.copy()
        masked_volume[~roi_mask] = 0
        
        return self.detect(masked_volume, **kwargs)
    
    def refine_detection(
        self,
        volume_data: np.ndarray,
        initial_electrodes: List[DetectedElectrode],
        search_radius: int = 10
    ) -> List[DetectedElectrode]:
        """
        Refine initial electrode detections by searching locally.
        
        Useful for improving results from a coarse initial detection.
        
        Args:
            volume_data: 3D CT volume
            initial_electrodes: Initial electrode detections to refine
            search_radius: Radius around each contact to search
            
        Returns:
            Refined electrode detections
        """
        refined = []
        
        for electrode in initial_electrodes:
            # Create ROI mask around the electrode
            roi_mask = np.zeros(volume_data.shape, dtype=bool)
            
            for contact in electrode.contacts:
                x, y, z = int(contact[0]), int(contact[1]), int(contact[2])
                
                # Create spherical region around contact
                x_min = max(0, x - search_radius)
                x_max = min(volume_data.shape[0], x + search_radius)
                y_min = max(0, y - search_radius)
                y_max = min(volume_data.shape[1], y + search_radius)
                z_min = max(0, z - search_radius)
                z_max = min(volume_data.shape[2], z + search_radius)
                
                roi_mask[x_min:x_max, y_min:y_max, z_min:z_max] = True
            
            # Re-detect within ROI
            local_electrodes = self.detect_with_roi(
                volume_data, 
                roi_mask,
                min_contacts_per_electrode=2  # Allow fewer contacts for refinement
            )
            
            if local_electrodes:
                # Use the best detection from this region
                best = max(local_electrodes, key=lambda e: e.confidence)
                best.suggested_name = electrode.suggested_name
                best.electrode_type = electrode.electrode_type
                refined.append(best)
            else:
                # Keep original if refinement fails
                refined.append(electrode)
        
        return refined
