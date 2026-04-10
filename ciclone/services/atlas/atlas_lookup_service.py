"""
Atlas lookup service for FreeSurfer-based electrode labeling.

This service handles loading FreeSurfer atlas volumes and looking up
anatomical labels for electrode contact coordinates.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import nibabel as nib

from ciclone.models.atlas_model import AtlasType, AtlasLabel, AtlasData, UNKNOWN_LABEL
from ciclone.services.atlas.color_lut_parser import parse_freesurfer_color_lut, get_default_color_lut_path


class AtlasLookupService:
    """
    Service for looking up anatomical labels from FreeSurfer atlases.

    This service handles:
    - Loading and caching FreeSurfer atlas volumes (.mgz files)
    - Loading the FreeSurfer color lookup table
    - Transforming coordinates from T1 space to atlas space
    - Looking up anatomical labels for given coordinates
    """

    def __init__(self, freesurfer_dir: Path):
        """
        Initialize the atlas lookup service.

        Args:
            freesurfer_dir: Path to FreeSurfer subject directory
                           (e.g., {subject}/processed_tmp/freesurfer_{name})
        """
        self._freesurfer_dir = Path(freesurfer_dir)
        self._mri_dir = self._freesurfer_dir / "mri"
        self._atlas_cache: Dict[AtlasType, AtlasData] = {}
        self._color_lut: Dict[int, AtlasLabel] = {}
        self._lut_loaded = False

    @property
    def freesurfer_dir(self) -> Path:
        """Return the FreeSurfer directory path."""
        return self._freesurfer_dir

    def is_valid(self) -> bool:
        """
        Check if the FreeSurfer directory is valid and contains required files.

        Returns:
            True if the directory contains at least one atlas file
        """
        if not self._mri_dir.exists():
            return False

        # Check for at least one atlas file
        for atlas_type in AtlasType:
            atlas_path = self._mri_dir / atlas_type.filename
            if atlas_path.exists():
                return True

        return False

    def get_available_atlases(self) -> List[AtlasType]:
        """
        Get list of available atlas types in this FreeSurfer directory.

        Returns:
            List of AtlasType values for which .mgz files exist
        """
        available = []
        for atlas_type in AtlasType:
            atlas_path = self._mri_dir / atlas_type.filename
            if atlas_path.exists():
                available.append(atlas_type)
        return available

    def _load_color_lut(self) -> bool:
        """
        Load the FreeSurfer color lookup table.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._lut_loaded:
            return True

        lut_path = get_default_color_lut_path()
        if lut_path is None:
            return False

        try:
            self._color_lut = parse_freesurfer_color_lut(lut_path)
            self._lut_loaded = True
            return True
        except (FileNotFoundError, ValueError):
            return False

    def _load_atlas(self, atlas_type: AtlasType) -> Optional[AtlasData]:
        """
        Load an atlas volume from the FreeSurfer directory.

        Args:
            atlas_type: Type of atlas to load

        Returns:
            AtlasData object if successful, None otherwise
        """
        # Check cache first
        if atlas_type in self._atlas_cache:
            return self._atlas_cache[atlas_type]

        atlas_path = self._mri_dir / atlas_type.filename
        if not atlas_path.exists():
            return None

        try:
            img = nib.load(str(atlas_path))
            volume = np.asarray(img.dataobj, dtype=np.int32)
            affine = img.affine

            atlas_data = AtlasData(
                volume=volume,
                affine=affine,
                atlas_type=atlas_type
            )

            # Cache for future lookups
            self._atlas_cache[atlas_type] = atlas_data
            return atlas_data

        except Exception:
            return None

    def _transform_coordinate(self,
                              voxel_coord: Tuple[float, float, float],
                              source_affine: np.ndarray,
                              target_affine: np.ndarray) -> Tuple[int, int, int]:
        """
        Transform a voxel coordinate from source space to target space.

        Pipeline:
        1. Source voxel -> physical (RAS) space using source affine
        2. Physical -> target voxel using inverse target affine

        Args:
            voxel_coord: (x, y, z) coordinate in source voxel space
            source_affine: 4x4 affine matrix of source image
            target_affine: 4x4 affine matrix of target image

        Returns:
            (x, y, z) coordinate in target voxel space (rounded to integers)
        """
        # Create homogeneous coordinate
        voxel_homog = np.array([voxel_coord[0], voxel_coord[1], voxel_coord[2], 1.0])

        # Transform to physical (RAS) space
        physical_coord = source_affine @ voxel_homog

        # Transform to target voxel space
        target_affine_inv = np.linalg.inv(target_affine)
        target_voxel = target_affine_inv @ physical_coord

        # Round to nearest integer voxel
        return (int(round(target_voxel[0])),
                int(round(target_voxel[1])),
                int(round(target_voxel[2])))

    def _is_valid_voxel(self, voxel: Tuple[int, int, int], shape: Tuple[int, ...]) -> bool:
        """
        Check if a voxel coordinate is within the volume bounds.

        Args:
            voxel: (x, y, z) voxel coordinate
            shape: Shape of the volume

        Returns:
            True if the voxel is within bounds
        """
        return (0 <= voxel[0] < shape[0] and
                0 <= voxel[1] < shape[1] and
                0 <= voxel[2] < shape[2])

    def get_label_for_coordinate(self,
                                  voxel_coord: Tuple[float, float, float],
                                  t1_affine: np.ndarray,
                                  atlas_type: AtlasType) -> AtlasLabel:
        """
        Get the anatomical label for a coordinate.

        Args:
            voxel_coord: (x, y, z) coordinate in T1 voxel space
            t1_affine: 4x4 affine matrix of the T1 image
            atlas_type: Type of atlas to use for lookup

        Returns:
            AtlasLabel object with the anatomical label, or UNKNOWN_LABEL if
            the coordinate is outside the brain or atlas not available
        """
        # Load color LUT if not already loaded
        if not self._load_color_lut():
            return UNKNOWN_LABEL

        # Load the atlas
        atlas_data = self._load_atlas(atlas_type)
        if atlas_data is None:
            return UNKNOWN_LABEL

        # Transform coordinate from T1 space to atlas space
        atlas_voxel = self._transform_coordinate(
            voxel_coord,
            t1_affine,
            atlas_data.affine
        )

        # Check bounds
        if not self._is_valid_voxel(atlas_voxel, atlas_data.shape):
            return UNKNOWN_LABEL

        # Look up the label ID in the atlas volume
        label_id = int(atlas_data.volume[atlas_voxel[0], atlas_voxel[1], atlas_voxel[2]])

        # Get the label info from the color LUT
        if label_id in self._color_lut:
            return self._color_lut[label_id]

        return UNKNOWN_LABEL

    def get_labels_for_coordinate(self,
                                   voxel_coord: Tuple[float, float, float],
                                   t1_affine: np.ndarray,
                                   atlas_types: Optional[List[AtlasType]] = None) -> Dict[str, AtlasLabel]:
        """
        Get anatomical labels for a coordinate from multiple atlases.

        Args:
            voxel_coord: (x, y, z) coordinate in T1 voxel space
            t1_affine: 4x4 affine matrix of the T1 image
            atlas_types: List of atlas types to query (default: all available)

        Returns:
            Dictionary mapping atlas type value to AtlasLabel
        """
        if atlas_types is None:
            atlas_types = self.get_available_atlases()

        results: Dict[str, AtlasLabel] = {}
        for atlas_type in atlas_types:
            label = self.get_label_for_coordinate(voxel_coord, t1_affine, atlas_type)
            results[atlas_type.value] = label

        return results

    def get_labels_for_contacts(self,
                                 contacts: List[Tuple[str, Tuple[float, float, float]]],
                                 t1_affine: np.ndarray,
                                 atlas_types: Optional[List[AtlasType]] = None) -> Dict[str, Dict[str, AtlasLabel]]:
        """
        Get anatomical labels for multiple electrode contacts.

        Args:
            contacts: List of (contact_label, (x, y, z)) tuples
            t1_affine: 4x4 affine matrix of the T1 image
            atlas_types: List of atlas types to query (default: all available)

        Returns:
            Dictionary mapping contact_label to {atlas_type: AtlasLabel}
        """
        if atlas_types is None:
            atlas_types = self.get_available_atlases()

        results: Dict[str, Dict[str, AtlasLabel]] = {}
        for contact_label, voxel_coord in contacts:
            results[contact_label] = self.get_labels_for_coordinate(
                voxel_coord, t1_affine, atlas_types
            )

        return results

    def clear_cache(self) -> None:
        """Clear the atlas cache to free memory."""
        self._atlas_cache.clear()


def detect_freesurfer_directory(subject_dir: Path) -> Optional[Path]:
    """
    Detect the FreeSurfer output directory for a subject.

    Args:
        subject_dir: Path to the CiCLONE subject directory

    Returns:
        Path to FreeSurfer directory if found, None otherwise
    """
    subject_dir = Path(subject_dir)

    # Get subject name from folder
    subject_name = subject_dir.name

    # Standard location: {subject_dir}/processed_tmp/freesurfer_{name}
    fs_dir = subject_dir / "processed_tmp" / f"freesurfer_{subject_name}"

    if fs_dir.exists() and (fs_dir / "mri").exists():
        return fs_dir

    # Alternative: look for any freesurfer_* directory
    processed_tmp = subject_dir / "processed_tmp"
    if processed_tmp.exists():
        for item in processed_tmp.iterdir():
            if item.is_dir() and item.name.startswith("freesurfer_"):
                if (item / "mri").exists():
                    return item

    return None
