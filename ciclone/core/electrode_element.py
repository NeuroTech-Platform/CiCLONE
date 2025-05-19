import pickle
from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np

@dataclass
class ElectrodeElement:
    diameter: float
    length: float
    vector: Tuple[float, float, float]
    position: Tuple[float, float, float]
    type: str
    axis: str