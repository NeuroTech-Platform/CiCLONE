"""
Data class for representing detected electrodes.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np


@dataclass
class DetectedElectrode:
    """
    Represents an automatically detected electrode with its trajectory and contacts.
    
    Attributes:
        tip: The tip point (deepest point in brain) as (x, y, z) coordinates
        entry: The entry point (skull entry) as (x, y, z) coordinates
        contacts: List of detected contact centroids as (x, y, z) coordinates
        confidence: Detection confidence score (0.0 to 1.0)
        suggested_name: Suggested name for the electrode based on position
        electrode_type: Suggested electrode type based on contact count/spacing
    """
    tip: Tuple[int, int, int]
    entry: Tuple[int, int, int]
    contacts: List[Tuple[float, float, float]] = field(default_factory=list)
    confidence: float = 1.0
    suggested_name: Optional[str] = None
    electrode_type: Optional[str] = None
    
    @property
    def num_contacts(self) -> int:
        """Return the number of detected contacts."""
        return len(self.contacts)
    
    @property
    def length(self) -> float:
        """Calculate the length of the electrode trajectory in voxels."""
        tip_arr = np.array(self.tip)
        entry_arr = np.array(self.entry)
        return float(np.linalg.norm(entry_arr - tip_arr))
    
    @property
    def direction_vector(self) -> np.ndarray:
        """Return the normalized direction vector from tip to entry."""
        tip_arr = np.array(self.tip)
        entry_arr = np.array(self.entry)
        direction = entry_arr - tip_arr
        norm = np.linalg.norm(direction)
        if norm > 0:
            return direction / norm
        return direction
    
    def get_contacts_as_int(self) -> List[Tuple[int, int, int]]:
        """Return contacts as integer coordinates."""
        return [(int(round(c[0])), int(round(c[1])), int(round(c[2]))) 
                for c in self.contacts]
    
    def __repr__(self) -> str:
        name = self.suggested_name or "unnamed"
        return (f"DetectedElectrode(name={name}, contacts={self.num_contacts}, "
                f"confidence={self.confidence:.2f})")
