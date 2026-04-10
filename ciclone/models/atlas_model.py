"""
Atlas data models for FreeSurfer atlas-based electrode labeling.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, Optional
import numpy as np


class AtlasType(Enum):
    """Supported FreeSurfer atlas types."""
    DESIKAN_KILLIANY = "aparc+aseg"           # 34 cortical regions/hemisphere + subcortical
    DESTRIEUX = "aparc.a2009s+aseg"           # 74 cortical regions/hemisphere + subcortical
    DKT = "aparc.DKTatlas+aseg"               # DKT atlas + subcortical
    SUBCORTICAL = "aseg"                       # Subcortical structures only

    @property
    def filename(self) -> str:
        """Return the .mgz filename for this atlas type."""
        return f"{self.value}.mgz"

    @property
    def display_name(self) -> str:
        """Return a human-readable name for display in UI."""
        names = {
            AtlasType.DESIKAN_KILLIANY: "Desikan-Killiany",
            AtlasType.DESTRIEUX: "Destrieux",
            AtlasType.DKT: "DKT",
            AtlasType.SUBCORTICAL: "Subcortical (aseg)"
        }
        return names.get(self, self.value)


@dataclass
class AtlasLabel:
    """
    Represents an anatomical label from a FreeSurfer atlas.

    Attributes:
        label_id: Integer label ID in the atlas volume
        name: Full label name from FreeSurferColorLUT.txt
        abbreviation: Short abbreviation for display
        hemisphere: 'L' for left, 'R' for right, '' for midline/bilateral
        rgb_color: RGB color tuple for visualization
    """
    label_id: int
    name: str
    abbreviation: str = ""
    hemisphere: str = ""
    rgb_color: Tuple[int, int, int] = (128, 128, 128)

    @property
    def display_name(self) -> str:
        """Return formatted display name, optionally with hemisphere prefix."""
        # Clean up FreeSurfer naming conventions for display
        clean_name = self.name

        # Remove common prefixes for cleaner display
        prefixes_to_remove = ['ctx-lh-', 'ctx-rh-', 'Left-', 'Right-', 'ctx_lh_', 'ctx_rh_']
        for prefix in prefixes_to_remove:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break

        # Add hemisphere indicator if known
        if self.hemisphere:
            return f"{self.hemisphere}-{clean_name}"
        return clean_name

    @property
    def short_name(self) -> str:
        """Return the shortest reasonable name for compact display."""
        if self.abbreviation:
            if self.hemisphere:
                return f"{self.hemisphere}-{self.abbreviation}"
            return self.abbreviation
        return self.display_name

    def __str__(self) -> str:
        return self.display_name


@dataclass
class AtlasData:
    """
    Container for loaded atlas volume data.

    Attributes:
        volume: 3D numpy array of label IDs
        affine: 4x4 affine transformation matrix
        atlas_type: The type of atlas this data represents
    """
    volume: np.ndarray
    affine: np.ndarray
    atlas_type: AtlasType

    @property
    def shape(self) -> Tuple[int, ...]:
        """Return the shape of the atlas volume."""
        return self.volume.shape


# Special label for coordinates outside the brain or with no valid label
UNKNOWN_LABEL = AtlasLabel(
    label_id=0,
    name="Unknown",
    abbreviation="Unk",
    hemisphere="",
    rgb_color=(0, 0, 0)
)
