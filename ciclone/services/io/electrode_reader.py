import pickle
from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np

from ciclone.domain.electrode_element import ElectrodeElement

class ElectrodeReader:
    def __init__(self, file_path: str):
        """
        Initialize the ElectrodeReader with a path to an electrode definition file.
        
        Args:
            file_path (str): Path to the .elecdef file
        """
        self.file_path = file_path
        self.elements: Dict[str, ElectrodeElement] = {}
        self.load_electrode()

    def load_electrode(self) -> None:
        """Load and parse the electrode definition file."""
        try:
            with open(self.file_path, 'rb') as f:
                data = pickle.load(f)
                
            for key, element_data in data.items():
                if key.startswith('Element') or key.startswith('Plot'):
                    self.elements[key] = ElectrodeElement(
                        diameter=element_data['diameter'],
                        length=element_data['length'],
                        vector=tuple(element_data['vector']),
                        position=tuple(element_data['position']),
                        type=element_data['type'],
                        axis=element_data['axis']
                    )
        except Exception as e:
            raise Exception(f"Error loading electrode file: {str(e)}")

    def get_elements(self) -> Dict[str, ElectrodeElement]:
        """Get all elements of the electrode."""
        return self.elements

    def get_tubes(self) -> Dict[str, ElectrodeElement]:
        """Get only the tube elements."""
        return {k: v for k, v in self.elements.items() if v.type == 'Tube'}

    def get_plots(self) -> Dict[str, ElectrodeElement]:
        """Get only the plot (contact) elements."""
        return {k: v for k, v in self.elements.items() if v.type == 'Plot'}

    def get_element_positions(self) -> List[Tuple[float, float, float]]:
        """Get all element positions as a list of (x, y, z) coordinates."""
        return [element.position for element in self.elements.values()]

    def get_element_dimensions(self) -> List[Tuple[float, float]]:
        """Get all element dimensions as a list of (diameter, length) tuples."""
        return [(element.diameter, element.length) for element in self.elements.values()]

    def get_bounding_box(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Get the bounding box of the electrode as (min_point, max_point)."""
        positions = self.get_element_positions()
        if not positions:
            return ((0, 0, 0), (0, 0, 0))
        
        positions = np.array(positions)
        min_point = positions.min(axis=0)
        max_point = positions.max(axis=0)
        return (tuple(min_point), tuple(max_point))

# Example usage:
if __name__ == "__main__":
    # Example of how to use the class
    reader = ElectrodeReader("ciclone/config/electrodes/Dixi-D08-05AM.elecdef")
    
    # Get all elements
    elements = reader.get_elements()
    
    # Get only tubes
    tubes = reader.get_tubes()
    
    # Get only plots (contacts)
    plots = reader.get_plots()
    
    # Get all positions for 3D visualization
    positions = reader.get_element_positions()
    
    # Get bounding box for visualization
    min_point, max_point = reader.get_bounding_box()
    
    print(f"Number of elements: {len(elements)}")
    print(f"Number of tubes: {len(tubes)}")
    print(f"Number of plots: {len(plots)}")
    print(f"Bounding box: {min_point} to {max_point}") 

    # Print all elements
    for key, element in elements.items():
        print(f"Element {key}:")
        print(f"  Diameter: {element.diameter}")
        print(f"  Length: {element.length}")
        print(f"  Vector: {element.vector}")
    