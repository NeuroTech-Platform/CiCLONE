import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from PyQt6.QtGui import QColor

class SlicerFile:
    """Class to handle 3D Slicer file format operations."""
    
    SCHEMA_URL = "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.3.json#"
    
    def __init__(self):
        self.base_markup = {
            "@schema": self.SCHEMA_URL,
            "markups": []
        }

    def _generate_color_from_name(self, name: str) -> List[float]:
        """Generate a color based on the electrode name."""
        hue = abs(hash(name)) % 360
        h = hue / 360.0
        s = 0.8
        v = 0.8
        
        if s == 0.0:
            return [v, v, v]
            
        h *= 6.0
        i = int(h)
        f = h - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q
            
        return [r, g, b]

    def _create_fiducial_display(self, color: List[float]) -> Dict:
        """Create the display settings for a fiducial."""
        return {
            "visibility": True,
            "opacity": 1.0,
            "color": color,
            "selectedColor": [0.39, 1.0, 0.39],
            "activeColor": [0.4, 1.0, 0.0],
            "propertiesLabelVisibility": False,
            "pointLabelsVisibility": True,
            "textScale": 3.0,
            "glyphType": "Sphere3D",
            "glyphScale": 3.0,
            "glyphSize": 5.0,
            "useGlyphScale": True,
            "sliceProjection": False,
            "sliceProjectionUseFiducialColor": True,
            "sliceProjectionOutlinedBehindSlicePlane": False,
            "sliceProjectionColor": [1.0, 1.0, 1.0],
            "sliceProjectionOpacity": 0.6,
            "lineThickness": 0.2,
            "lineColorFadingStart": 1.0,
            "lineColorFadingEnd": 10.0,
            "lineColorFadingSaturation": 1.0,
            "lineColorFadingHueOffset": 0.0,
            "handlesInteractive": False,
            "translationHandleVisibility": True,
            "rotationHandleVisibility": True,
            "scaleHandleVisibility": True,
            "interactionHandleScale": 3.0,
            "snapMode": "toVisibleSurface"
        }

    def _create_control_point(self, 
                            index: int, 
                            label: str, 
                            description: str, 
                            position: List[float]) -> Dict:
        """Create a control point for a fiducial."""
        return {
            "id": str(index + 1),
            "label": label,
            "description": description,
            "associatedNodeID": "",
            "position": position,
            "orientation": [-1.0, -0.0, -0.0, -0.0, -1.0, -0.0, 0.0, 0.0, 1.0],
            "selected": True,
            "locked": True,
            "visibility": True,
            "positionStatus": "defined"
        }

    def _create_fiducial(self, 
                        electrode_name: str, 
                        electrode_type: str, 
                        contacts: List[Tuple[int, int, int]], 
                        affine: np.ndarray,
                        image_center: Optional[np.ndarray] = None) -> Dict:
        """Create a fiducial markup for an electrode."""
        color = self._generate_color_from_name(electrode_name)
        
        fiducial = {
            "type": "Fiducial",
            "coordinateSystem": "RAS",
            "coordinateUnits": "mm",
            "locked": False,
            "fixedNumberOfControlPoints": False,
            "labelFormat": "%N-%d",
            "lastUsedControlPointNumber": len(contacts),
            "controlPoints": [],
            "measurements": [],
            "display": self._create_fiducial_display(color),
            "name": electrode_name
        }
        
        # Add control points (contacts) for this electrode
        for i, contact in enumerate(contacts):
            voxel_coords = np.array([contact[0], contact[1], contact[2], 1.0])
            physical_coords = np.dot(affine, voxel_coords)[:3]
            
            # Apply center-relative transformation if image center is provided
            if image_center is not None:
                ras_coords = (physical_coords - image_center).tolist()
            else:
                ras_coords = physical_coords.tolist()
            
            control_point = self._create_control_point(
                i, f"{electrode_name}{i+1}", electrode_type, ras_coords
            )
            fiducial["controlPoints"].append(control_point)
        
        return fiducial

    def create_markup(self, 
                     electrodes: List[Dict], 
                     affine: np.ndarray,
                     image_center: Optional[np.ndarray] = None) -> Dict:
        """Create the complete markup structure for all electrodes."""
        markup = self.base_markup.copy()
        
        for electrode in electrodes:
            if not electrode.get('contacts'):
                continue
                
            fiducial = self._create_fiducial(
                electrode['name'],
                electrode['type'],
                electrode['contacts'],
                affine,
                image_center
            )
            markup["markups"].append(fiducial)
            
        return markup

    def save_to_file(self, file_path: str, markup: Dict) -> bool:
        """Save the markup to a JSON file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(markup, f, indent=4)
            return True
        except Exception:
            return False

    def load_from_file(self, file_path: str) -> Dict:
        """Load markup data from a Slicer JSON file."""
        try:
            with open(file_path, 'r') as f:
                markup_data = json.load(f)
            
            # Validate basic structure
            if not isinstance(markup_data, dict) or 'markups' not in markup_data:
                raise ValueError("Invalid Slicer file format: missing 'markups' field")
            
            if not isinstance(markup_data['markups'], list):
                raise ValueError("Invalid Slicer file format: 'markups' must be a list")
            
            return markup_data
        
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load file: {str(e)}")

    def parse_markup_to_electrodes(self, markup_data: Dict, 
                                 image_center: Optional[np.ndarray] = None,
                                 affine: Optional[np.ndarray] = None) -> List[Dict]:
        """
        Parse markup data into electrode format compatible with CiCLONE.
        
        Args:
            markup_data: Parsed JSON data from Slicer file
            image_center: Image center for coordinate transformation (if available)
            affine: Affine transformation matrix (if available)
            
        Returns:
            List of electrode dictionaries with format:
            [{'name': str, 'type': str, 'contacts': [(x, y, z), ...]}, ...]
        """
        electrodes = []
        
        try:
            markups = markup_data.get('markups', [])
            
            for markup in markups:
                if markup.get('type') != 'Fiducial':
                    continue  # Skip non-fiducial markups
                
                control_points = markup.get('controlPoints', [])
                if not control_points:
                    continue  # Skip empty markups
                
                # Extract electrode information from control points
                contacts = []
                electrode_name = None
                electrode_type = "Unknown"  # Default type
                
                for control_point in control_points:
                    # Extract position (center-relative coordinates from Slicer)
                    position = control_point.get('position', [0, 0, 0])
                    
                    if len(position) < 3:
                        continue  # Skip invalid positions
                    
                    # Convert to numpy array for processing
                    center_relative_coords = np.array(position[:3])
                    
                    # Transform center-relative coordinates back to image space
                    if image_center is not None and affine is not None:
                        # Convert center-relative to physical coordinates
                        physical_coords = center_relative_coords + image_center
                        
                        # Convert physical coordinates to voxel coordinates
                        physical_coords_homogeneous = np.append(physical_coords, 1.0)
                        try:
                            voxel_coords = np.dot(np.linalg.inv(affine), physical_coords_homogeneous)[:3]
                            image_coords = tuple(np.round(voxel_coords).astype(int))
                        except np.linalg.LinAlgError:
                            # Fallback: use center-relative coordinates directly as approximation
                            image_coords = tuple(np.round(center_relative_coords).astype(int))
                    else:
                        # No transformation available, use coordinates as-is
                        image_coords = tuple(np.round(center_relative_coords).astype(int))
                    
                    contacts.append(image_coords)
                    
                    # Extract electrode name from first control point label
                    if electrode_name is None:
                        label = control_point.get('label', '')
                        # Extract electrode name by removing numeric suffix
                        # e.g., "ElectrodeA1" -> "ElectrodeA"
                        import re
                        match = re.match(r'^(.+?)(\d+)$', label)
                        if match:
                            electrode_name = match.group(1)
                        else:
                            electrode_name = label or f"ImportedElectrode_{len(electrodes) + 1}"
                    
                    # Try to extract electrode type from description
                    description = control_point.get('description', '')
                    if description and electrode_type == "Unknown":
                        electrode_type = description
                
                # Create electrode entry if we have valid data
                if electrode_name and contacts:
                    electrodes.append({
                        'name': electrode_name,
                        'type': electrode_type,
                        'contacts': contacts
                    })
        
        except Exception as e:
            raise Exception(f"Failed to parse electrode data: {str(e)}")
        
        return electrodes 