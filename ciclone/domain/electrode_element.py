import pickle
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np

@dataclass
class ElectrodeElement:
    """
    Represents a physical element of an electrode (tube or plot).
    """
    diameter: float
    length: float
    vector: Tuple[float, float, float]
    position: Tuple[float, float, float]
    type: str
    axis: str
    
    def is_tail_element(self) -> bool:
        """
        Check if this element is likely a tail/shaft element.
        Tail elements are typically much longer than contact elements.
        """
        return self.type.lower() == 'tube' and self.length > 20.0  # Threshold for tail detection

@dataclass
class ElectrodeStructure:
    """
    Represents the complete physical structure of an electrode including contacts and tail.
    """
    name: str
    electrode_type: str
    contact_positions: List[Tuple[float, float, float]]
    tail_element: Optional[ElectrodeElement] = None
    elements: List[ElectrodeElement] = None
    tail_endpoint: Optional[Tuple[float, float, float]] = None
    tail_start_point: Optional[Tuple[float, float, float]] = None  # Where the tail begins (last contact)
    
    @property
    def has_tail(self) -> bool:
        """Check if this electrode has a tail element."""
        return self.tail_element is not None
    
    @property 
    def tail_length(self) -> float:
        """Get the length of the tail element."""
        return self.tail_element.length if self.tail_element else 0.0
    
    @property
    def tail_position(self) -> Tuple[float, float, float]:
        """Get the position of the tail element."""
        return self.tail_element.position if self.tail_element else (0.0, 0.0, 0.0)