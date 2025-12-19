"""
Electrode validation module for filtering artifacts from auto-detection results.

Implements multiple validation checks:
1. Linearity - electrodes should be straight lines
2. Contact count - limited by known electrode types (max 18)
3. Spacing regularity - contacts should be evenly spaced
4. Intensity consistency - contacts should have similar intensity
5. Direction - electrodes should point toward brain center
"""

import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.decomposition import PCA

from ciclone.services.detection.detected_electrode import DetectedElectrode


# Validation parameters
# Updated based on full benchmark analysis (Dec 2024):
# Analysis showed that spacing_cv and max_deviation are NOT good discriminators:
# - 72% of correctly matched (REAL) electrodes have spacing_cv > 0.30
# - 91% of correctly matched (REAL) electrodes have spacing_cv > 0.25
# These rules were incorrectly flagging 75% of real electrodes as artifacts!
#
# Better discriminators:
# - Linearity: artifacts have mean 0.962, real electrodes have mean 0.982
# - Points outward: 45% of artifacts point outward from brain center
# - Low contact count: artifacts tend to have fewer contacts
#
# Relaxed thresholds to avoid false positives on real electrodes:
MAX_LINE_DEVIATION_MM = 5.0  # Very relaxed - real electrodes can deviate significantly
MAX_SPACING_CV = 0.50  # Relaxed from 0.25 - real electrodes have natural spacing variation
MAX_INTENSITY_CV = 0.5  # Max coefficient of variation for intensity
MAX_CONTACT_COUNT = 18  # Maximum contacts per electrode (from elecdef files)
MIN_LINEARITY = 0.88  # Relaxed to 0.88 - some real electrodes have lower linearity
MIN_CONTACT_SPACING_MM = 2.0  # Minimum spacing between contacts (shaft detection filter)
EXPECTED_CONTACT_SPACING_MM = 3.5  # Expected spacing for standard electrodes
MIN_CONTACTS_FOR_ELECTRODE = 6  # Minimum contacts to be considered a valid electrode


def load_valid_contact_counts() -> List[int]:
    """
    Load valid contact counts from electrode definition files.
    
    Returns:
        Sorted list of valid contact counts (e.g., [5, 8, 10, 12, 15, 18])
    """
    elecdef_dir = Path(__file__).parent.parent.parent / "config" / "electrodes"
    
    if not elecdef_dir.exists():
        return [5, 8, 10, 12, 15, 18]  # Default values
    
    counts = set()
    for f in elecdef_dir.glob("*.elecdef"):
        try:
            with open(f, 'rb') as file:
                data = pickle.load(file)
            n_contacts = sum(1 for k, v in data.items() 
                           if isinstance(v, dict) and v.get('type') == 'Plot')
            if n_contacts > 0:
                counts.add(n_contacts)
        except Exception:
            continue
    
    return sorted(counts) if counts else [5, 8, 10, 12, 15, 18]


class ElectrodeValidator:
    """
    Validates detected electrodes to filter out artifacts.
    
    Applies multiple quality checks and calculates an overall confidence score.
    """
    
    def __init__(
        self,
        volume_data: Optional[np.ndarray] = None,
        voxel_size_mm: float = 0.55,
        image_shape: Optional[Tuple[int, int, int]] = None
    ):
        """
        Initialize the validator.
        
        Args:
            volume_data: 3D image volume for intensity checks
            voxel_size_mm: Voxel size in mm for distance calculations
            image_shape: Shape of the image volume
        """
        self.volume_data = volume_data
        self.voxel_size_mm = voxel_size_mm
        self.image_shape = image_shape or (volume_data.shape if volume_data is not None else None)
        self.valid_contact_counts = load_valid_contact_counts()
        self.max_contacts = max(self.valid_contact_counts) if self.valid_contact_counts else 18
    
    def validate(self, electrode: DetectedElectrode) -> Dict[str, Any]:
        """
        Run all validation checks on an electrode.
        
        Args:
            electrode: The detected electrode to validate
            
        Returns:
            Dictionary of quality flags and metrics
        """
        flags = {}
        
        contacts = np.array(electrode.contacts)
        if len(contacts) < 2:
            flags["is_artifact"] = True
            flags["reason"] = "Too few contacts"
            return flags
        
        # 1. Linearity check
        linearity, max_deviation = self._check_linearity(contacts)
        flags["linearity"] = linearity
        flags["max_deviation_mm"] = max_deviation * self.voxel_size_mm
        
        # 2. Spacing regularity check
        spacing_cv, mean_spacing = self._check_spacing_regularity(contacts)
        flags["spacing_cv"] = spacing_cv
        flags["mean_spacing_mm"] = mean_spacing * self.voxel_size_mm
        
        # 3. Shaft detection check (contacts too close together)
        is_shaft_spacing, min_spacing, pct_too_close = self._check_shaft_detection(contacts)
        flags["min_spacing_mm"] = min_spacing * self.voxel_size_mm
        flags["pct_too_close"] = pct_too_close
        
        # 4. Intensity profile check (continuous vs discrete)
        if self.volume_data is not None:
            is_continuous, min_dip_ratio, segments_no_dip = self._check_intensity_profile(contacts, electrode)
            flags["is_continuous"] = is_continuous
            flags["min_dip_ratio"] = min_dip_ratio
            flags["segments_no_dip"] = segments_no_dip
        else:
            is_continuous = False
            flags["is_continuous"] = False
        
        # Combined shaft detection: either spacing-based or intensity-based
        flags["is_shaft"] = is_shaft_spacing or is_continuous
        
        # 5. Contact count check and trimming
        trimmed_contacts, original_count = self._check_contact_count(electrode)
        flags["original_contacts"] = original_count
        flags["trimmed_contacts"] = original_count - len(trimmed_contacts)
        
        # 5. Intensity consistency check
        if self.volume_data is not None:
            intensity_cv, mean_intensity = self._check_intensity_consistency(contacts)
            flags["intensity_cv"] = intensity_cv
            flags["mean_intensity"] = mean_intensity
        
        # 6. Direction check (points toward brain center)
        points_outward = self._check_direction(electrode)
        flags["points_outward"] = points_outward
        
        # Determine if this is likely an artifact
        flags["is_artifact"] = self._is_artifact(flags)
        
        return flags
    
    def _check_linearity(self, contacts: np.ndarray) -> Tuple[float, float]:
        """
        Check how linear the contact arrangement is.
        
        Returns:
            (linearity score 0-1, max deviation from line in voxels)
        """
        if len(contacts) < 3:
            return 1.0, 0.0
        
        # Fit PCA to get principal axis
        pca = PCA(n_components=min(3, len(contacts)))
        pca.fit(contacts)
        linearity = pca.explained_variance_ratio_[0]
        
        # Calculate max deviation from the fitted line
        center = contacts.mean(axis=0)
        direction = pca.components_[0]
        
        # Project points onto line and calculate perpendicular distances
        v = contacts - center
        proj_lengths = np.dot(v, direction)
        proj_points = center + np.outer(proj_lengths, direction)
        deviations = np.linalg.norm(contacts - proj_points, axis=1)
        max_deviation = np.max(deviations)
        
        return linearity, max_deviation
    
    def _check_spacing_regularity(self, contacts: np.ndarray) -> Tuple[float, float]:
        """
        Check how regular the spacing between contacts is.
        
        Returns:
            (coefficient of variation, mean spacing in voxels)
        """
        if len(contacts) < 2:
            return 0.0, 0.0
        
        # Order contacts along the electrode axis
        pca = PCA(n_components=1)
        pca.fit(contacts)
        projections = pca.transform(contacts).flatten()
        order = np.argsort(projections)
        ordered_contacts = contacts[order]
        
        # Calculate spacing between consecutive contacts
        spacings = np.linalg.norm(np.diff(ordered_contacts, axis=0), axis=1)
        
        if len(spacings) == 0:
            return 0.0, 0.0
        
        mean_spacing = np.mean(spacings)
        std_spacing = np.std(spacings)
        
        # Coefficient of variation
        cv = std_spacing / mean_spacing if mean_spacing > 0 else 0.0
        
        return cv, mean_spacing
    
    def _check_shaft_detection(self, contacts: np.ndarray) -> Tuple[bool, float, float]:
        """
        Check if detected points are actually shaft (continuous) rather than discrete contacts.
        
        When the electrode shaft is detected, points are very close together (< 2.5mm),
        whereas real contacts are spaced ~3.5mm apart.
        
        Returns:
            (is_shaft: bool, min_spacing in voxels, percentage of spacings that are too close)
        """
        if len(contacts) < 2:
            return False, 0.0, 0.0
        
        # Order contacts along the electrode axis
        pca = PCA(n_components=1)
        pca.fit(contacts)
        projections = pca.transform(contacts).flatten()
        order = np.argsort(projections)
        ordered_contacts = contacts[order]
        
        # Calculate spacing between consecutive contacts
        spacings = np.linalg.norm(np.diff(ordered_contacts, axis=0), axis=1)
        
        if len(spacings) == 0:
            return False, 0.0, 0.0
        
        min_spacing = np.min(spacings)
        
        # Convert threshold to voxels
        min_threshold_voxels = MIN_CONTACT_SPACING_MM / self.voxel_size_mm
        
        # Count how many spacings are below the threshold
        too_close = np.sum(spacings < min_threshold_voxels)
        pct_too_close = too_close / len(spacings)
        
        # If more than 50% of spacings are too close, it's likely shaft detection
        # Also require at least 3 spacings to avoid false positives on small clusters
        is_shaft = pct_too_close > 0.5 and len(spacings) >= 3
        
        return is_shaft, min_spacing, pct_too_close
    
    def _check_intensity_profile(
        self, 
        contacts: np.ndarray,
        electrode: DetectedElectrode
    ) -> Tuple[bool, float, int]:
        """
        Check if there are intensity dips between contacts (discrete) or continuous high intensity (shaft).
        
        Real electrode contacts have bright spots with lower intensity between them.
        A shaft has continuous high intensity along its length.
        
        Returns:
            (is_continuous: bool, min_dip_ratio, num_segments_without_dip)
        """
        if self.volume_data is None or len(contacts) < 3:
            return False, 1.0, 0
        
        # Order contacts along the electrode axis
        pca = PCA(n_components=1)
        pca.fit(contacts)
        projections = pca.transform(contacts).flatten()
        order = np.argsort(projections)
        ordered_contacts = contacts[order]
        
        # Get principal axis direction
        axis_direction = pca.components_[0]
        
        # Sample intensity between each pair of consecutive contacts
        segments_without_dip = 0
        min_dip_ratio = 1.0
        
        for i in range(len(ordered_contacts) - 1):
            start = ordered_contacts[i]
            end = ordered_contacts[i + 1]
            
            # Get intensity at start and end (contact positions)
            start_int = int(round(start[0])), int(round(start[1])), int(round(start[2]))
            end_int = int(round(end[0])), int(round(end[1])), int(round(end[2]))
            
            # Check bounds
            if not self._in_bounds(start_int) or not self._in_bounds(end_int):
                continue
            
            start_intensity = self.volume_data[start_int]
            end_intensity = self.volume_data[end_int]
            contact_intensity = (start_intensity + end_intensity) / 2
            
            if contact_intensity <= 0:
                continue
            
            # Sample midpoint between contacts
            midpoint = (start + end) / 2
            mid_int = int(round(midpoint[0])), int(round(midpoint[1])), int(round(midpoint[2]))
            
            if not self._in_bounds(mid_int):
                continue
            
            mid_intensity = self.volume_data[mid_int]
            
            # Calculate the dip ratio (midpoint intensity / contact intensity)
            # Real contacts: dip ratio < 0.85 (some dip between contacts)
            # Shaft: dip ratio > 0.95 (very continuous high intensity)
            dip_ratio = mid_intensity / contact_intensity if contact_intensity > 0 else 1.0
            
            min_dip_ratio = min(min_dip_ratio, dip_ratio)
            
            # If midpoint intensity is >= 95% of contact intensity, virtually no dip
            if dip_ratio >= 0.95:
                segments_without_dip += 1
        
        total_segments = len(ordered_contacts) - 1
        
        # Only flag as continuous if MOST segments have no dip (>80%)
        # AND we have enough segments to be confident (>=4)
        is_continuous = (segments_without_dip / total_segments) > 0.8 and total_segments >= 4 if total_segments > 0 else False
        
        return is_continuous, min_dip_ratio, segments_without_dip
    
    def _in_bounds(self, coords: Tuple[int, int, int]) -> bool:
        """Check if coordinates are within volume bounds."""
        x, y, z = coords
        return (0 <= x < self.volume_data.shape[0] and
                0 <= y < self.volume_data.shape[1] and
                0 <= z < self.volume_data.shape[2])
    
    def _check_contact_count(
        self, 
        electrode: DetectedElectrode
    ) -> Tuple[List[Tuple[float, float, float]], int]:
        """
        Check if contact count exceeds known electrode types and trim if needed.
        
        Trims contacts from the entry end (outer contacts are likely artifacts).
        
        Returns:
            (trimmed contacts list, original count)
        """
        contacts = list(electrode.contacts)
        original_count = len(contacts)
        
        if original_count <= self.max_contacts:
            return contacts, original_count
        
        # Order contacts from tip to entry
        contacts_arr = np.array(contacts)
        tip = np.array(electrode.tip)
        
        # Calculate distance from tip for each contact
        distances = np.linalg.norm(contacts_arr - tip, axis=1)
        order = np.argsort(distances)
        
        # Keep only the contacts closest to tip (up to max)
        trimmed_indices = order[:self.max_contacts]
        trimmed_contacts = [contacts[i] for i in sorted(trimmed_indices)]
        
        return trimmed_contacts, original_count
    
    def _check_intensity_consistency(
        self, 
        contacts: np.ndarray
    ) -> Tuple[float, float]:
        """
        Check how consistent the intensity is across contacts.
        
        Returns:
            (coefficient of variation, mean intensity)
        """
        if self.volume_data is None:
            return 0.0, 0.0
        
        intensities = []
        for contact in contacts:
            x, y, z = int(round(contact[0])), int(round(contact[1])), int(round(contact[2]))
            
            # Check bounds
            if (0 <= x < self.volume_data.shape[0] and
                0 <= y < self.volume_data.shape[1] and
                0 <= z < self.volume_data.shape[2]):
                intensities.append(self.volume_data[x, y, z])
        
        if len(intensities) < 2:
            return 0.0, 0.0
        
        intensities = np.array(intensities)
        mean_intensity = np.mean(intensities)
        std_intensity = np.std(intensities)
        
        # Coefficient of variation
        cv = std_intensity / mean_intensity if mean_intensity > 0 else 0.0
        
        return cv, mean_intensity
    
    def _check_direction(self, electrode: DetectedElectrode) -> bool:
        """
        Check if electrode points toward or away from brain center.
        
        Returns:
            True if electrode points outward (away from center) - likely artifact
        """
        if self.image_shape is None:
            return False
        
        # Approximate brain center as image center
        center = np.array(self.image_shape) / 2.0
        
        tip = np.array(electrode.tip)
        entry = np.array(electrode.entry)
        
        # Distance from tip and entry to center
        tip_to_center = np.linalg.norm(tip - center)
        entry_to_center = np.linalg.norm(entry - center)
        
        # If entry is closer to center than tip, electrode points outward
        points_outward = entry_to_center < tip_to_center
        
        return points_outward
    
    def _is_artifact(self, flags: Dict[str, Any]) -> bool:
        """
        Determine if the electrode is likely an artifact based on flags.
        
        Updated based on full benchmark analysis (Dec 2024):
        - spacing_cv is NOT a good discriminator (real electrodes have high spacing_cv too)
        - max_deviation is NOT a good discriminator (real electrodes can have deviation)
        - Best discriminators: is_shaft, very low linearity, points_outward + low linearity
        
        The goal is HIGH RECALL (don't miss real electrodes) with reasonable precision.
        It's better to have some artifacts than to filter out real electrodes.
        """
        # Check for shaft detection (contacts too close together) - very reliable
        if flags.get("is_shaft", False):
            return True
        
        # Check minimum contact count - reliable filter
        original_contacts = flags.get("original_contacts", 0)
        if original_contacts < MIN_CONTACTS_FOR_ELECTRODE:
            return True
        
        # Check very low linearity - likely artifact if below threshold
        linearity = flags.get("linearity", 1.0)
        if linearity < MIN_LINEARITY:
            return True
        
        # NOTE: max_deviation check removed - it was flagging too many real electrodes
        # The PCA-based linearity check is more robust
        
        # Combined rule: pointing outward + low linearity indicates artifact
        # 45% of artifacts point outward, vs fewer real electrodes
        if flags.get("points_outward", False):
            # Only filter if pointing outward AND borderline linearity
            if linearity < 0.96:
                return True
        
        # NOTE: We intentionally do NOT filter based on:
        # - spacing_cv: too many real electrodes have high spacing_cv
        # - intensity_cv: not reliable enough
        
        return False
    
    def calculate_confidence(self, flags: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score from quality flags.
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if flags.get("is_artifact"):
            # Artifacts get low confidence
            return 0.2
        
        scores = []
        
        # Linearity score (0.9-1.0 is good)
        linearity = flags.get("linearity", 1.0)
        linearity_score = min(1.0, linearity / 0.95)
        scores.append(linearity_score * 0.3)  # 30% weight
        
        # Spacing regularity score (lower CV is better)
        spacing_cv = flags.get("spacing_cv", 0.0)
        spacing_score = max(0.0, 1.0 - spacing_cv / MAX_SPACING_CV)
        scores.append(spacing_score * 0.25)  # 25% weight
        
        # Intensity consistency score (if available)
        intensity_cv = flags.get("intensity_cv")
        if intensity_cv is not None:
            intensity_score = max(0.0, 1.0 - intensity_cv / MAX_INTENSITY_CV)
            scores.append(intensity_score * 0.2)  # 20% weight
        else:
            scores.append(0.15)  # Default partial score
        
        # Direction score
        points_outward = flags.get("points_outward", False)
        direction_score = 0.0 if points_outward else 1.0
        scores.append(direction_score * 0.15)  # 15% weight
        
        # Contact count score (no trimming is better)
        trimmed = flags.get("trimmed_contacts", 0)
        original = flags.get("original_contacts", 1)
        count_score = 1.0 - (trimmed / original) if original > 0 else 1.0
        scores.append(count_score * 0.1)  # 10% weight
        
        return sum(scores)
    
    def validate_and_update(self, electrode: DetectedElectrode) -> DetectedElectrode:
        """
        Validate electrode and update its quality_flags and confidence.
        
        Also trims excess contacts if needed.
        
        Args:
            electrode: The electrode to validate
            
        Returns:
            The same electrode with updated quality_flags and confidence
        """
        flags = self.validate(electrode)
        electrode.quality_flags = flags
        electrode.confidence = self.calculate_confidence(flags)
        
        # Trim contacts if needed
        trimmed = flags.get("trimmed_contacts", 0)
        if trimmed > 0:
            trimmed_contacts, _ = self._check_contact_count(electrode)
            electrode.contacts = trimmed_contacts
            
            # Recalculate tip/entry after trimming
            if trimmed_contacts:
                contacts_arr = np.array(trimmed_contacts)
                pca = PCA(n_components=1)
                pca.fit(contacts_arr)
                proj = pca.transform(contacts_arr).flatten()
                tip_idx = np.argmin(proj)
                entry_idx = np.argmax(proj)
                electrode.tip = tuple(int(round(c)) for c in trimmed_contacts[tip_idx])
                electrode.entry = tuple(int(round(c)) for c in trimmed_contacts[entry_idx])
        
        return electrode
