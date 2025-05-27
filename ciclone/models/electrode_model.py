import os
import pickle
import numpy as np
from typing import Dict, List, Tuple, Optional
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt, QObject, pyqtSignal

from ciclone.domain.electrodes import Electrode


class ElectrodeModel:
    """Model for managing electrode data and business logic."""
    
    def __init__(self):
        self._electrodes: Dict[str, Electrode] = {}
        self._processed_contacts: Dict[str, List[Tuple[int, int, int]]] = {}
        self._electrode_definitions = self._load_electrode_definitions()
    
    def _load_electrode_definitions(self) -> Dict[str, str]:
        """Load electrode definition files from the config directory."""
        electrode_files = []
        config_path = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "electrodes"))
        print(f"Loading electrode definitions from {config_path}")

        if not os.path.exists(config_path):
            return {}
        
        for file in os.listdir(config_path):
            if file.endswith(".elecdef"):
                name = file.replace(".elecdef", "")
                full_path = os.path.join(config_path, file)
                electrode_files.append((name, full_path))
        
        # Sort electrode files alphabetically by name
        electrode_files.sort(key=lambda x: x[0])
        return dict(electrode_files)
    
    def add_electrode(self, name: str, electrode_type: str) -> bool:
        """Add a new electrode to the model."""
        if name in self._electrodes:
            return False
        
        electrode = Electrode(name=name, electrode_type=electrode_type)
        self._electrodes[name] = electrode
        return True
    
    def remove_electrode(self, name: str) -> bool:
        """Remove an electrode from the model."""
        if name not in self._electrodes:
            return False
        
        del self._electrodes[name]
        if name in self._processed_contacts:
            del self._processed_contacts[name]
        
        return True
    
    def get_electrode(self, name: str) -> Optional[Electrode]:
        """Get an electrode by name."""
        return self._electrodes.get(name)
    
    def get_electrode_names(self) -> List[str]:
        """Get list of all electrode names."""
        return list(self._electrodes.keys())
    
    def get_all_electrodes(self) -> List[Electrode]:
        """Get all electrodes."""
        return list(self._electrodes.values())
    
    def electrode_exists(self, name: str) -> bool:
        """Check if an electrode with the given name exists."""
        return name in self._electrodes
    
    def get_available_electrode_types(self) -> List[str]:
        """Get list of available electrode types."""
        return list(self._electrode_definitions.keys())
    
    def process_electrode_contacts(self, 
                                 electrode_name: str, 
                                 entry_point: Tuple[int, int, int], 
                                 output_point: Tuple[int, int, int]) -> bool:
        """Process coordinates for an electrode and calculate contact positions."""
        electrode = self.get_electrode(electrode_name)
        if not electrode:
            return False
        
        try:
            # Load electrode definition
            elec_def_path = self._electrode_definitions.get(electrode.electrode_type)
            if not elec_def_path or not os.path.exists(elec_def_path):
                return False
            
            with open(elec_def_path, 'rb') as f:
                elec_def = pickle.load(f)
            
            # Extract plot positions
            plot_positions = []
            for key, value in elec_def.items():
                if key.startswith('Plot'):
                    position = value.get('position', [0, 0, 0])
                    plot_positions.append((key, position))
            
            if not plot_positions:
                return False
            
            # Sort plots by z-position
            plot_positions.sort(key=lambda x: x[1][2])
            
            # Calculate direction vector
            entry_array = np.array(entry_point)
            output_array = np.array(output_point)
            direction = output_array - entry_array
            direction_norm = np.linalg.norm(direction)
            
            if direction_norm == 0:
                return False
            
            direction = direction / direction_norm
            
            # Calculate contact positions
            min_z = min(pos[1][2] for pos in plot_positions)
            max_z = max(pos[1][2] for pos in plot_positions)
            z_span = max_z - min_z
            
            if z_span == 0:
                return False
            
            entry_output_distance = np.linalg.norm(output_array - entry_array)
            contacts = []
            
            for plot_name, plot_pos in plot_positions:
                relative_pos = (plot_pos[2] - min_z) / z_span
                contact_pos = entry_array + relative_pos * direction * entry_output_distance
                contacts.append(tuple(np.round(contact_pos).astype(int)))
            
            # Store contacts
            self._processed_contacts[electrode_name] = contacts
            
            # Update electrode object
            electrode.contacts.clear()
            for i, contact_pos in enumerate(contacts):
                label = f"{electrode_name}{i+1}"
                electrode.add_contact(label, contact_pos[0], contact_pos[1], contact_pos[2])
            
            return True
        
        except Exception:
            return False
    
    def get_processed_contacts(self, electrode_name: str) -> List[Tuple[int, int, int]]:
        """Get processed contacts for a specific electrode."""
        return self._processed_contacts.get(electrode_name, [])
    
    def get_all_processed_contacts(self) -> Dict[str, List[Tuple[int, int, int]]]:
        """Get all processed contacts for display purposes."""
        contacts_dict = {}
        for electrode in self.get_all_electrodes():
            if electrode.contacts:
                contacts_dict[electrode.name] = [
                    (contact.x, contact.y, contact.z) for contact in electrode.contacts
                ]
        return contacts_dict
    
    def create_tree_item(self, electrode: Electrode) -> QTreeWidgetItem:
        """Create a tree widget item for an electrode."""
        item = QTreeWidgetItem()
        item.setText(0, electrode.name)
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        
        # Add contact sub-items
        for contact in electrode.contacts:
            contact_item = QTreeWidgetItem(item)
            contact_item.setText(0, contact.label)
            contact_item.setText(1, str(int(contact.x)))
            contact_item.setText(2, str(int(contact.y)))
            contact_item.setText(3, str(int(contact.z)))
            contact_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            contact_item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
        
        return item
    
    def has_processed_contacts(self) -> bool:
        """Check if any electrodes have processed contacts."""
        return any(electrode.contacts for electrode in self.get_all_electrodes())
    
    def get_electrodes_with_contacts(self) -> List[Electrode]:
        """Get all electrodes that have processed contacts."""
        return [electrode for electrode in self.get_all_electrodes() if electrode.contacts] 