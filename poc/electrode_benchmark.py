#!/usr/bin/env python3
"""
Electrode Detection Benchmark Script

This script benchmarks the electrode auto-detection algorithm against ground truth
coordinates from multiple subjects. It identifies artifact patterns and suggests
improvements to the detection/validation rules.

Usage:
    poetry run python poc/electrode_benchmark.py --data-dir /path/to/DataElectrodes

Author: CiCLONE Team
Date: December 2024
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
from sklearn.decomposition import PCA

from ciclone.services.detection.ct_detector import CTElectrodeDetector
from ciclone.services.detection.electrode_validator import ElectrodeValidator
from ciclone.services.detection.detected_electrode import DetectedElectrode


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GroundTruthElectrode:
    """Represents a ground truth electrode from JSON."""
    name: str
    electrode_type: str
    contacts_ras: List[np.ndarray]  # RAS/mm coordinates
    contacts_voxel: List[np.ndarray] = field(default_factory=list)  # Voxel coordinates
    
    @property
    def num_contacts(self) -> int:
        return len(self.contacts_ras)
    
    @property
    def centroid_voxel(self) -> np.ndarray:
        """Get centroid in voxel space."""
        if self.contacts_voxel:
            return np.mean(self.contacts_voxel, axis=0)
        return np.array([0, 0, 0])


@dataclass
class MatchResult:
    """Result of matching detected electrodes to ground truth."""
    detected: DetectedElectrode
    ground_truth: Optional[GroundTruthElectrode]
    distance_mm: float
    is_match: bool
    contact_count_diff: int = 0
    quality_flags: Dict = field(default_factory=dict)


@dataclass
class SubjectResult:
    """Results for a single subject."""
    subject_id: str
    num_ground_truth: int
    num_detected: int
    num_matched: int
    true_positives: List[MatchResult] = field(default_factory=list)
    false_positives: List[MatchResult] = field(default_factory=list)  # Artifacts
    false_negatives: List[GroundTruthElectrode] = field(default_factory=list)  # Missed


@dataclass
class ArtifactAnalysis:
    """Analysis of artifact characteristics."""
    total_artifacts: int = 0
    linearity_distribution: List[float] = field(default_factory=list)
    spacing_cv_distribution: List[float] = field(default_factory=list)
    contact_count_distribution: List[int] = field(default_factory=list)
    distance_from_center_distribution: List[float] = field(default_factory=list)
    points_outward_count: int = 0
    is_shaft_count: int = 0
    mean_intensity_distribution: List[float] = field(default_factory=list)


# =============================================================================
# Utility Functions
# =============================================================================

def get_image_center_physical(volume_shape: Tuple[int, int, int], affine: np.ndarray) -> np.ndarray:
    """
    Calculate the image center in physical (RAS) coordinate space.
    
    This matches the calculation in CiCLONE's image_model.py.
    Slicer JSON files store coordinates as CENTER-RELATIVE RAS, not absolute RAS.
    
    Args:
        volume_shape: Shape of the NIfTI volume (x, y, z)
        affine: NIfTI affine matrix (4, 4)
    
    Returns:
        Image center in physical/RAS space
    """
    # Calculate center in voxel space (0-based indexing)
    center_voxel = np.array([
        (volume_shape[0] - 1) / 2.0,  # x center
        (volume_shape[1] - 1) / 2.0,  # y center  
        (volume_shape[2] - 1) / 2.0,  # z center
        1.0  # homogeneous coordinate
    ])
    
    # Transform to physical space using affine matrix
    center_physical = np.dot(affine, center_voxel)[:3]
    
    return center_physical


def ras_to_voxel(ras_coords: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """
    Convert RAS (mm) coordinates to voxel coordinates.
    
    Args:
        ras_coords: RAS coordinates (3,) or (N, 3) - ABSOLUTE RAS, not center-relative
        affine: NIfTI affine matrix (4, 4)
    
    Returns:
        Voxel coordinates
    """
    # Invert affine to go from RAS to voxel
    inv_affine = np.linalg.inv(affine)
    
    if ras_coords.ndim == 1:
        # Single point
        homogeneous = np.append(ras_coords, 1.0)
        voxel = np.dot(inv_affine, homogeneous)[:3]
        return voxel
    else:
        # Multiple points
        homogeneous = np.hstack([ras_coords, np.ones((len(ras_coords), 1))])
        voxel = np.dot(inv_affine, homogeneous.T).T[:, :3]
        return voxel


def voxel_to_ras(voxel_coords: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """
    Convert voxel coordinates to RAS (mm) coordinates.
    
    Args:
        voxel_coords: Voxel coordinates (3,) or (N, 3)
        affine: NIfTI affine matrix (4, 4)
    
    Returns:
        ABSOLUTE RAS coordinates in mm
    """
    if voxel_coords.ndim == 1:
        homogeneous = np.append(voxel_coords, 1.0)
        ras = np.dot(affine, homogeneous)[:3]
        return ras
    else:
        homogeneous = np.hstack([voxel_coords, np.ones((len(voxel_coords), 1))])
        ras = np.dot(affine, homogeneous.T).T[:, :3]
        return ras


def center_relative_to_absolute_ras(
    center_relative_coords: np.ndarray, 
    image_center: np.ndarray
) -> np.ndarray:
    """
    Convert center-relative RAS coordinates to absolute RAS.
    
    Slicer JSON stores positions as (physical_coords - image_center).
    This reverses that transformation.
    
    Args:
        center_relative_coords: Coordinates from Slicer JSON
        image_center: Image center in physical space
    
    Returns:
        Absolute RAS coordinates
    """
    return center_relative_coords + image_center


def load_ground_truth(
    json_path: Path, 
    affine: np.ndarray, 
    image_center: np.ndarray
) -> List[GroundTruthElectrode]:
    """
    Load ground truth electrodes from Slicer JSON file.
    
    IMPORTANT: Slicer JSON stores coordinates as CENTER-RELATIVE RAS, not absolute RAS.
    The position in the JSON is: (absolute_RAS - image_center).
    We need to add image_center back to get the actual RAS coordinates.
    
    Args:
        json_path: Path to coordinates JSON file
        affine: NIfTI affine matrix for coordinate conversion
        image_center: Image center in physical/RAS space (from get_image_center_physical)
    
    Returns:
        List of GroundTruthElectrode objects
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    electrodes_dict: Dict[str, GroundTruthElectrode] = {}
    
    for markup in data.get('markups', []):
        if markup.get('type') != 'Fiducial':
            continue
        
        for control_point in markup.get('controlPoints', []):
            label = control_point.get('label', '')
            position = control_point.get('position', [0, 0, 0])
            description = control_point.get('description', 'Unknown')
            
            # Extract electrode name (e.g., "B1" -> "B", "A'1" -> "A'", "M"1" -> "M"")
            # The apostrophe/quote indicates hemisphere (left vs right side)
            match = re.match(r'^([A-Za-z]+[\'"]?)(\d+)$', label)
            if match:
                electrode_name = match.group(1)
            else:
                electrode_name = label
            
            # CRITICAL: JSON position is center-relative, convert to absolute RAS
            center_relative_coords = np.array(position[:3])
            absolute_ras_coords = center_relative_to_absolute_ras(center_relative_coords, image_center)
            
            # Now convert absolute RAS to voxel coordinates
            voxel_coords = ras_to_voxel(absolute_ras_coords, affine)
            
            if electrode_name not in electrodes_dict:
                electrodes_dict[electrode_name] = GroundTruthElectrode(
                    name=electrode_name,
                    electrode_type=description,
                    contacts_ras=[],
                    contacts_voxel=[]
                )
            
            # Store absolute RAS (for display) and voxel (for comparison)
            electrodes_dict[electrode_name].contacts_ras.append(absolute_ras_coords)
            electrodes_dict[electrode_name].contacts_voxel.append(voxel_coords)
    
    return list(electrodes_dict.values())


def find_subject_files(data_dir: Path) -> List[Dict]:
    """
    Find all subjects with both masked SEEG and coordinates files.
    
    Args:
        data_dir: Root directory containing subject folders
    
    Returns:
        List of dicts with subject_id, seeg_path, coordinates_path
    """
    subjects = []
    
    for subdir in sorted(data_dir.iterdir()):
        if not subdir.is_dir() or not subdir.name.startswith('sub'):
            continue
        
        # Look for masked SEEG file
        seeg_files = list(subdir.glob('**/r_*_seeg_masked.nii.gz'))
        if not seeg_files:
            continue
        
        # Prefer pipeline_output over processed_tmp
        seeg_path = None
        for f in seeg_files:
            if 'pipeline_output' in str(f):
                seeg_path = f
                break
        if seeg_path is None:
            seeg_path = seeg_files[0]
        
        # Look for coordinates file (non-MNI)
        coords_files = list(subdir.glob('**/pipeline_output/*_coordinates.json'))
        coords_files = [f for f in coords_files if not f.name.startswith('MNI_')]
        
        if not coords_files:
            # Try processed_tmp
            coords_files = list(subdir.glob('**/processed_tmp/*_coordinates.json'))
            coords_files = [f for f in coords_files if not f.name.startswith('MNI_')]
        
        if not coords_files:
            print(f"  Warning: No coordinates file found for {subdir.name}")
            continue
        
        subjects.append({
            'subject_id': subdir.name,
            'seeg_path': seeg_path,
            'coordinates_path': coords_files[0]
        })
    
    return subjects


def match_electrodes(
    detected: List[DetectedElectrode],
    ground_truth: List[GroundTruthElectrode],
    voxel_size_mm: float,
    match_threshold_mm: float = 15.0,
    affine: Optional[np.ndarray] = None
) -> Tuple[List[MatchResult], List[MatchResult], List[GroundTruthElectrode]]:
    """
    Match detected electrodes to ground truth using centroid proximity.
    
    Compares in RAS (mm) space since ground truth is stored in RAS.
    
    Args:
        detected: List of detected electrodes
        ground_truth: List of ground truth electrodes
        voxel_size_mm: Voxel size for distance calculation
        match_threshold_mm: Maximum distance for a match (mm)
        affine: NIfTI affine matrix for voxel->RAS conversion
    
    Returns:
        Tuple of (true_positives, false_positives, false_negatives)
    """
    true_positives = []
    false_positives = []
    matched_gt_indices = set()
    
    for det in detected:
        # Calculate centroid of detected electrode in voxel space
        det_contacts = np.array(det.contacts)
        det_centroid_voxel = det_contacts.mean(axis=0)
        
        # Convert to RAS space for comparison (ground truth is in RAS)
        if affine is not None:
            det_centroid_ras = voxel_to_ras(det_centroid_voxel, affine)
        else:
            det_centroid_ras = det_centroid_voxel * voxel_size_mm
        
        # Find closest ground truth electrode (compare in RAS space)
        best_match = None
        best_distance = float('inf')
        best_gt_idx = -1
        
        for gt_idx, gt in enumerate(ground_truth):
            if gt_idx in matched_gt_indices:
                continue
            
            # Ground truth centroid in RAS space
            gt_centroid_ras = np.mean(gt.contacts_ras, axis=0)
            
            # Distance in RAS (mm) space
            distance_mm = np.linalg.norm(det_centroid_ras - gt_centroid_ras)
            
            if distance_mm < best_distance:
                best_distance = distance_mm
                best_match = gt
                best_gt_idx = gt_idx
        
        # Determine if it's a match
        is_match = best_distance < match_threshold_mm
        
        result = MatchResult(
            detected=det,
            ground_truth=best_match if is_match else None,
            distance_mm=best_distance,
            is_match=is_match,
            contact_count_diff=abs(det.num_contacts - best_match.num_contacts) if best_match else 0
        )
        
        if is_match:
            true_positives.append(result)
            matched_gt_indices.add(best_gt_idx)
        else:
            false_positives.append(result)
    
    # Find false negatives (unmatched ground truth)
    false_negatives = [gt for i, gt in enumerate(ground_truth) 
                       if i not in matched_gt_indices]
    
    return true_positives, false_positives, false_negatives


def calculate_distance_from_center(
    electrode: DetectedElectrode, 
    volume_shape: Tuple[int, int, int],
    voxel_size_mm: float
) -> float:
    """Calculate distance of electrode centroid from volume center in mm."""
    center = np.array(volume_shape) / 2.0
    contacts = np.array(electrode.contacts)
    centroid = contacts.mean(axis=0)
    distance_voxels = np.linalg.norm(centroid - center)
    return distance_voxels * voxel_size_mm


# =============================================================================
# Main Benchmark Functions
# =============================================================================

def run_detection(
    volume_data: np.ndarray,
    voxel_size_mm: float = 0.55
) -> Tuple[List[DetectedElectrode], List[Dict]]:
    """
    Run electrode detection and validation.
    
    Args:
        volume_data: 3D CT volume
        voxel_size_mm: Voxel size in mm
    
    Returns:
        Tuple of (detected_electrodes, quality_flags_list)
    """
    detector = CTElectrodeDetector()
    electrodes = detector.detect(volume_data, voxel_size_mm=voxel_size_mm)
    
    # Run validation
    validator = ElectrodeValidator(
        volume_data=volume_data,
        voxel_size_mm=voxel_size_mm,
        image_shape=volume_data.shape
    )
    
    quality_flags_list = []
    for electrode in electrodes:
        flags = validator.validate(electrode)
        electrode.quality_flags = flags
        quality_flags_list.append(flags)
    
    return electrodes, quality_flags_list


def process_subject(
    subject_info: Dict,
    verbose: bool = True,
    debug: bool = False
) -> SubjectResult:
    """
    Process a single subject: run detection and compare to ground truth.
    
    Args:
        subject_info: Dict with subject_id, seeg_path, coordinates_path
        verbose: Print progress messages
        debug: Print debug info about coordinate matching
    
    Returns:
        SubjectResult with detection metrics
    """
    subject_id = subject_info['subject_id']
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Processing {subject_id}")
        print(f"{'='*60}")
    
    # Load NIfTI volume
    nii = nib.load(subject_info['seeg_path'])
    volume_data = nii.get_fdata()
    affine = nii.affine
    
    # Calculate voxel size from affine
    voxel_sizes = np.sqrt(np.sum(affine[:3, :3] ** 2, axis=0))
    voxel_size_mm = float(np.mean(voxel_sizes))
    
    # Calculate image center in physical (RAS) space
    # This is CRITICAL for reading Slicer JSON files, which store center-relative coordinates
    image_center = get_image_center_physical(volume_data.shape, affine)
    
    if verbose:
        print(f"  Volume shape: {volume_data.shape}")
        print(f"  Voxel size: {voxel_size_mm:.3f} mm")
    
    if debug:
        print(f"  Affine matrix:\n{affine}")
        print(f"  Image center (RAS): {image_center}")
    
    # Load ground truth (passing image_center for center-relative coordinate conversion)
    ground_truth = load_ground_truth(subject_info['coordinates_path'], affine, image_center)
    if verbose:
        print(f"  Ground truth electrodes: {len(ground_truth)}")
        for gt in ground_truth:
            print(f"    - {gt.name}: {gt.num_contacts} contacts ({gt.electrode_type})")
    
    if debug and ground_truth:
        # Show sample ground truth coordinates
        gt0 = ground_truth[0]
        print(f"\n  DEBUG - Ground truth '{gt0.name}' sample coordinates:")
        print(f"    RAS (mm): {gt0.contacts_ras[0]}")
        print(f"    Voxel:    {gt0.contacts_voxel[0]}")
        print(f"    Centroid (voxel): {gt0.centroid_voxel}")
    
    # Run detection
    detected, quality_flags = run_detection(volume_data, voxel_size_mm)
    if verbose:
        print(f"  Detected electrodes: {len(detected)}")
    
    if debug and detected:
        # Show sample detected coordinates
        det0 = detected[0]
        det_contacts = np.array(det0.contacts)
        det_centroid_voxel = det_contacts.mean(axis=0)
        det_centroid_ras = voxel_to_ras(det_centroid_voxel, affine)
        print(f"\n  DEBUG - Detected electrode '{det0.suggested_name}' sample coordinates:")
        print(f"    First contact (voxel): {det0.contacts[0]}")
        print(f"    Centroid (voxel): {det_centroid_voxel}")
        print(f"    Centroid (RAS mm): {det_centroid_ras}")
        
        # Calculate distance to first ground truth in RAS space
        if ground_truth:
            gt0 = ground_truth[0]
            gt0_centroid_ras = np.mean(gt0.contacts_ras, axis=0)
            dist_ras = np.linalg.norm(det_centroid_ras - gt0_centroid_ras)
            print(f"    GT '{gt0.name}' centroid (RAS mm): {gt0_centroid_ras}")
            print(f"    Distance to GT '{gt0.name}' in RAS: {dist_ras:.1f} mm")
    
    # Match electrodes (compare in RAS space)
    true_pos, false_pos, false_neg = match_electrodes(
        detected, ground_truth, voxel_size_mm, affine=affine
    )
    
    # Add quality flags to match results
    for i, result in enumerate(true_pos + false_pos):
        idx = detected.index(result.detected)
        result.quality_flags = quality_flags[idx]
    
    if verbose:
        print(f"  Results:")
        print(f"    True Positives (matched): {len(true_pos)}")
        print(f"    False Positives (artifacts): {len(false_pos)}")
        print(f"    False Negatives (missed): {len(false_neg)}")
        
        if false_neg:
            print(f"  Missed electrodes:")
            for gt in false_neg:
                print(f"    - {gt.name}: {gt.num_contacts} contacts")
    
    return SubjectResult(
        subject_id=subject_id,
        num_ground_truth=len(ground_truth),
        num_detected=len(detected),
        num_matched=len(true_pos),
        true_positives=true_pos,
        false_positives=false_pos,
        false_negatives=false_neg
    )


def analyze_artifacts(
    results: List[SubjectResult],
    data_dir: Path
) -> ArtifactAnalysis:
    """
    Analyze characteristics of artifacts (false positives).
    
    Args:
        results: List of SubjectResult from all subjects
        data_dir: Data directory for loading volumes if needed
    
    Returns:
        ArtifactAnalysis with statistical summaries
    """
    analysis = ArtifactAnalysis()
    
    for subject_result in results:
        for fp in subject_result.false_positives:
            analysis.total_artifacts += 1
            
            flags = fp.quality_flags
            
            # Collect distributions
            if 'linearity' in flags:
                analysis.linearity_distribution.append(flags['linearity'])
            if 'spacing_cv' in flags:
                analysis.spacing_cv_distribution.append(flags['spacing_cv'])
            if 'mean_intensity' in flags:
                analysis.mean_intensity_distribution.append(flags['mean_intensity'])
            
            analysis.contact_count_distribution.append(fp.detected.num_contacts)
            
            if flags.get('points_outward', False):
                analysis.points_outward_count += 1
            if flags.get('is_shaft', False):
                analysis.is_shaft_count += 1
    
    return analysis


def analyze_incorrectly_flagged_true_positives(results: List[SubjectResult]):
    """Analyze why true positives are being incorrectly flagged as artifacts."""
    print(f"\n{'='*60}")
    print("ANALYSIS OF INCORRECTLY FLAGGED TRUE POSITIVES")
    print(f"{'='*60}")
    
    incorrectly_flagged = []
    correctly_kept = []
    
    for r in results:
        for tp in r.true_positives:
            flags = tp.quality_flags
            if flags.get("is_artifact", False):
                incorrectly_flagged.append((r.subject_id, tp))
            else:
                correctly_kept.append((r.subject_id, tp))
    
    if not incorrectly_flagged:
        print("\nNo true positives incorrectly flagged!")
        return
    
    print(f"\nTotal incorrectly flagged: {len(incorrectly_flagged)}/{len(incorrectly_flagged)+len(correctly_kept)}")
    
    # Analyze why they were flagged
    reasons = {
        "is_shaft": 0,
        "min_contacts": 0,
        "linearity": 0,
        "max_deviation": 0,
        "spacing_cv": 0,
        "intensity_cv": 0,
        "points_outward_low_linearity": 0,
    }
    
    linearity_values = []
    spacing_cv_values = []
    contact_counts = []
    
    for subject_id, tp in incorrectly_flagged:
        flags = tp.quality_flags
        
        # Collect values
        linearity_values.append(flags.get("linearity", 1.0))
        spacing_cv_values.append(flags.get("spacing_cv", 0.0))
        contact_counts.append(flags.get("original_contacts", 0))
        
        # Determine which rule triggered the artifact flag
        if flags.get("is_shaft", False):
            reasons["is_shaft"] += 1
        elif flags.get("original_contacts", 100) < 6:
            reasons["min_contacts"] += 1
        elif flags.get("linearity", 1.0) < 0.95:
            reasons["linearity"] += 1
        elif flags.get("max_deviation_mm", 0.0) > 2.0:
            reasons["max_deviation"] += 1
        elif flags.get("spacing_cv", 0.0) > 0.25:
            reasons["spacing_cv"] += 1
        elif flags.get("intensity_cv", 0.0) > 0.5:
            reasons["intensity_cv"] += 1
        elif flags.get("points_outward", False) and flags.get("linearity", 1.0) < 0.98:
            reasons["points_outward_low_linearity"] += 1
    
    print(f"\nReason for incorrect flagging:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = 100 * count / len(incorrectly_flagged)
            print(f"  {reason}: {count} ({pct:.1f}%)")
    
    # Distribution analysis
    if linearity_values:
        lin = np.array(linearity_values)
        print(f"\nLinearity of incorrectly flagged (real electrodes):")
        print(f"  Mean: {np.mean(lin):.3f}")
        print(f"  Min:  {np.min(lin):.3f}")
        print(f"  Max:  {np.max(lin):.3f}")
        print(f"  < 0.95: {np.sum(lin < 0.95)} ({100*np.sum(lin < 0.95)/len(lin):.1f}%)")
        print(f"  < 0.98: {np.sum(lin < 0.98)} ({100*np.sum(lin < 0.98)/len(lin):.1f}%)")
    
    if spacing_cv_values:
        scv = np.array(spacing_cv_values)
        print(f"\nSpacing CV of incorrectly flagged (real electrodes):")
        print(f"  Mean: {np.mean(scv):.3f}")
        print(f"  Min:  {np.min(scv):.3f}")
        print(f"  Max:  {np.max(scv):.3f}")
        print(f"  > 0.20: {np.sum(scv > 0.20)} ({100*np.sum(scv > 0.20)/len(scv):.1f}%)")
        print(f"  > 0.25: {np.sum(scv > 0.25)} ({100*np.sum(scv > 0.25)/len(scv):.1f}%)")
        print(f"  > 0.30: {np.sum(scv > 0.30)} ({100*np.sum(scv > 0.30)/len(scv):.1f}%)")
    
    if contact_counts:
        cc = np.array(contact_counts)
        print(f"\nContact counts of incorrectly flagged (real electrodes):")
        print(f"  Mean: {np.mean(cc):.1f}")
        print(f"  Min:  {np.min(cc)}")
        print(f"  Max:  {np.max(cc)}")


def print_artifact_analysis(analysis: ArtifactAnalysis):
    """Print artifact analysis summary."""
    print(f"\n{'='*60}")
    print("ARTIFACT ANALYSIS")
    print(f"{'='*60}")
    
    print(f"\nTotal artifacts detected: {analysis.total_artifacts}")
    
    if analysis.linearity_distribution:
        lin = np.array(analysis.linearity_distribution)
        print(f"\nLinearity Distribution:")
        print(f"  Mean: {np.mean(lin):.3f}")
        print(f"  Std:  {np.std(lin):.3f}")
        print(f"  Min:  {np.min(lin):.3f}")
        print(f"  Max:  {np.max(lin):.3f}")
        print(f"  < 0.90: {np.sum(lin < 0.90)} ({100*np.sum(lin < 0.90)/len(lin):.1f}%)")
        print(f"  < 0.95: {np.sum(lin < 0.95)} ({100*np.sum(lin < 0.95)/len(lin):.1f}%)")
    
    if analysis.spacing_cv_distribution:
        scv = np.array(analysis.spacing_cv_distribution)
        print(f"\nSpacing CV Distribution:")
        print(f"  Mean: {np.mean(scv):.3f}")
        print(f"  Std:  {np.std(scv):.3f}")
        print(f"  Min:  {np.min(scv):.3f}")
        print(f"  Max:  {np.max(scv):.3f}")
        print(f"  > 0.20: {np.sum(scv > 0.20)} ({100*np.sum(scv > 0.20)/len(scv):.1f}%)")
        print(f"  > 0.30: {np.sum(scv > 0.30)} ({100*np.sum(scv > 0.30)/len(scv):.1f}%)")
    
    if analysis.contact_count_distribution:
        cc = np.array(analysis.contact_count_distribution)
        print(f"\nContact Count Distribution:")
        print(f"  Mean: {np.mean(cc):.1f}")
        print(f"  Std:  {np.std(cc):.1f}")
        print(f"  Min:  {np.min(cc)}")
        print(f"  Max:  {np.max(cc)}")
        print(f"  <= 5:  {np.sum(cc <= 5)} ({100*np.sum(cc <= 5)/len(cc):.1f}%)")
        print(f"  <= 6:  {np.sum(cc <= 6)} ({100*np.sum(cc <= 6)/len(cc):.1f}%)")
    
    print(f"\nDirectional Flags:")
    print(f"  Points outward: {analysis.points_outward_count} ({100*analysis.points_outward_count/max(1,analysis.total_artifacts):.1f}%)")
    print(f"  Is shaft: {analysis.is_shaft_count} ({100*analysis.is_shaft_count/max(1,analysis.total_artifacts):.1f}%)")
    
    if analysis.mean_intensity_distribution:
        mi = np.array(analysis.mean_intensity_distribution)
        print(f"\nMean Intensity Distribution:")
        print(f"  Mean: {np.mean(mi):.1f}")
        print(f"  Std:  {np.std(mi):.1f}")
        print(f"  Min:  {np.min(mi):.1f}")
        print(f"  Max:  {np.max(mi):.1f}")


def print_summary(results: List[SubjectResult]):
    """Print overall benchmark summary."""
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    
    total_gt = sum(r.num_ground_truth for r in results)
    total_detected = sum(r.num_detected for r in results)
    total_matched = sum(r.num_matched for r in results)
    total_fp = sum(len(r.false_positives) for r in results)
    total_fn = sum(len(r.false_negatives) for r in results)
    
    print(f"\nSubjects analyzed: {len(results)}")
    print(f"\nGround Truth Summary:")
    print(f"  Total electrodes: {total_gt}")
    print(f"  Average per subject: {total_gt/len(results):.1f}")
    
    print(f"\nDetection Summary:")
    print(f"  Total detected: {total_detected}")
    print(f"  Average per subject: {total_detected/len(results):.1f}")
    
    print(f"\nMatching Results:")
    print(f"  True Positives: {total_matched} ({100*total_matched/total_gt:.1f}% detection rate)")
    print(f"  False Positives (artifacts): {total_fp}")
    print(f"  False Negatives (missed): {total_fn}")
    
    precision = total_matched / total_detected if total_detected > 0 else 0
    recall = total_matched / total_gt if total_gt > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\nMetrics:")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall: {recall:.3f}")
    print(f"  F1 Score: {f1:.3f}")
    
    # Count how many artifacts are flagged by validator
    artifacts_flagged = 0
    tp_flagged_as_artifact = 0
    for r in results:
        for fp in r.false_positives:
            if fp.quality_flags.get("is_artifact", False):
                artifacts_flagged += 1
        for tp in r.true_positives:
            if tp.quality_flags.get("is_artifact", False):
                tp_flagged_as_artifact += 1
    
    print(f"\nValidator Filter Impact:")
    print(f"  Artifacts flagged by validator: {artifacts_flagged}/{total_fp} ({100*artifacts_flagged/max(1,total_fp):.1f}%)")
    print(f"  True positives incorrectly flagged: {tp_flagged_as_artifact}/{total_matched} ({100*tp_flagged_as_artifact/max(1,total_matched):.1f}%)")
    
    # Calculate filtered metrics
    filtered_fp = total_fp - artifacts_flagged
    filtered_tp = total_matched - tp_flagged_as_artifact
    filtered_detected = total_detected - artifacts_flagged
    
    if filtered_detected > 0:
        filtered_precision = filtered_tp / filtered_detected
        filtered_recall = filtered_tp / total_gt if total_gt > 0 else 0
        filtered_f1 = 2 * filtered_precision * filtered_recall / (filtered_precision + filtered_recall) if (filtered_precision + filtered_recall) > 0 else 0
        
        print(f"\nMetrics AFTER filtering artifacts:")
        print(f"  True Positives: {filtered_tp}")
        print(f"  False Positives: {filtered_fp}")
        print(f"  Precision: {filtered_precision:.3f} (was {precision:.3f})")
        print(f"  Recall: {filtered_recall:.3f} (was {recall:.3f})")
        print(f"  F1 Score: {filtered_f1:.3f} (was {f1:.3f})")
    
    # Per-subject breakdown
    print(f"\nPer-Subject Results:")
    print(f"  {'Subject':<12} {'GT':>4} {'Det':>4} {'TP':>4} {'FP':>4} {'FN':>4} {'Rate':>6}")
    print(f"  {'-'*12} {'-'*4} {'-'*4} {'-'*4} {'-'*4} {'-'*4} {'-'*6}")
    for r in results:
        rate = r.num_matched / r.num_ground_truth if r.num_ground_truth > 0 else 0
        print(f"  {r.subject_id:<12} {r.num_ground_truth:>4} {r.num_detected:>4} "
              f"{r.num_matched:>4} {len(r.false_positives):>4} {len(r.false_negatives):>4} "
              f"{100*rate:>5.1f}%")


def suggest_improvements(analysis: ArtifactAnalysis, results: List[SubjectResult]):
    """Suggest improvements to detection/validation based on analysis."""
    print(f"\n{'='*60}")
    print("SUGGESTED IMPROVEMENTS")
    print(f"{'='*60}")
    
    suggestions = []
    
    # Analyze linearity
    if analysis.linearity_distribution:
        lin = np.array(analysis.linearity_distribution)
        low_linearity_pct = 100 * np.sum(lin < 0.95) / len(lin)
        if low_linearity_pct > 30:
            suggestions.append({
                'rule': 'Increase MIN_LINEARITY threshold',
                'current': '0.90',
                'suggested': '0.95',
                'reason': f'{low_linearity_pct:.0f}% of artifacts have linearity < 0.95'
            })
    
    # Analyze contact count
    if analysis.contact_count_distribution:
        cc = np.array(analysis.contact_count_distribution)
        low_count_pct = 100 * np.sum(cc <= 5) / len(cc)
        if low_count_pct > 40:
            suggestions.append({
                'rule': 'Increase min_contacts_per_electrode',
                'current': '4',
                'suggested': '6',
                'reason': f'{low_count_pct:.0f}% of artifacts have <= 5 contacts'
            })
    
    # Analyze spacing CV
    if analysis.spacing_cv_distribution:
        scv = np.array(analysis.spacing_cv_distribution)
        high_cv_pct = 100 * np.sum(scv > 0.25) / len(scv)
        if high_cv_pct > 30:
            suggestions.append({
                'rule': 'Decrease MAX_SPACING_CV threshold',
                'current': '0.30',
                'suggested': '0.25',
                'reason': f'{high_cv_pct:.0f}% of artifacts have spacing CV > 0.25'
            })
    
    # Analyze direction
    if analysis.total_artifacts > 0:
        outward_pct = 100 * analysis.points_outward_count / analysis.total_artifacts
        if outward_pct > 20:
            suggestions.append({
                'rule': 'Filter electrodes pointing outward',
                'current': 'Not filtered (only combined with low linearity)',
                'suggested': 'Filter if points_outward AND linearity < 0.98',
                'reason': f'{outward_pct:.0f}% of artifacts point outward from brain center'
            })
    
    # Analyze shaft detection
    if analysis.total_artifacts > 0:
        shaft_pct = 100 * analysis.is_shaft_count / analysis.total_artifacts
        if shaft_pct > 10:
            suggestions.append({
                'rule': 'Shaft detection is catching artifacts',
                'current': 'Enabled',
                'suggested': 'Keep enabled, working well',
                'reason': f'{shaft_pct:.0f}% of artifacts flagged as shaft'
            })
    
    # Print suggestions
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            print(f"\n{i}. {s['rule']}")
            print(f"   Current: {s['current']}")
            print(f"   Suggested: {s['suggested']}")
            print(f"   Reason: {s['reason']}")
    else:
        print("\nNo specific improvements suggested based on current analysis.")
    
    # Analyze false negatives
    missed_electrodes = []
    for r in results:
        for fn in r.false_negatives:
            missed_electrodes.append((r.subject_id, fn))
    
    if missed_electrodes:
        print(f"\n\nMISSED ELECTRODES ANALYSIS ({len(missed_electrodes)} total):")
        print("-" * 40)
        
        # Group by contact count
        contact_counts = [fn.num_contacts for _, fn in missed_electrodes]
        print(f"Contact count distribution of missed electrodes:")
        print(f"  Mean: {np.mean(contact_counts):.1f}")
        print(f"  Min:  {np.min(contact_counts)}")
        print(f"  Max:  {np.max(contact_counts)}")
        
        # List missed electrodes
        print(f"\nMissed electrode details:")
        for subject_id, fn in missed_electrodes:
            print(f"  {subject_id} - {fn.name}: {fn.num_contacts} contacts ({fn.electrode_type})")


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark electrode auto-detection against ground truth'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path('/Users/fl6985/Desktop/DataElectrodes'),
        help='Directory containing subject folders'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='Print detailed progress'
    )
    parser.add_argument(
        '--subject',
        type=str,
        default=None,
        help='Process only a specific subject (e.g., sub-002)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Print debug information about coordinate matching'
    )
    
    args = parser.parse_args()
    
    print(f"Electrode Detection Benchmark")
    print(f"Data directory: {args.data_dir}")
    
    # Find all subjects
    subjects = find_subject_files(args.data_dir)
    
    if args.subject:
        subjects = [s for s in subjects if s['subject_id'] == args.subject]
    
    print(f"Found {len(subjects)} subjects with required files")
    
    if not subjects:
        print("No subjects found!")
        return
    
    # Process each subject
    results = []
    for subject_info in subjects:
        try:
            result = process_subject(subject_info, verbose=args.verbose, debug=args.debug)
            results.append(result)
        except Exception as e:
            print(f"Error processing {subject_info['subject_id']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    if results:
        print_summary(results)
        
        # Analyze incorrectly flagged true positives FIRST
        analyze_incorrectly_flagged_true_positives(results)
        
        # Analyze artifacts
        analysis = analyze_artifacts(results, args.data_dir)
        print_artifact_analysis(analysis)
        
        # Suggest improvements
        suggest_improvements(analysis, results)


if __name__ == '__main__':
    main()
