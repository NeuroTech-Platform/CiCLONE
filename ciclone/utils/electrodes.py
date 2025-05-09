import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class Contact:
    """
    Represents a single electrode contact with 3D coordinates.
    """
    label: str
    x: float
    y: float
    z: float
    
    @property
    def coordinates(self) -> Tuple[float, float, float]:
        """Return the coordinates as a tuple."""
        return (self.x, self.y, self.z)


class Electrode:
    """
    Represents an electrode with one or more contacts.
    """
    def __init__(self, name: str, electrode_type: str = ""):
        """
        Initialize an electrode with a name and type.
        
        Args:
            name (str): Name of the electrode
            electrode_type (str): Type of the electrode
        """
        self.name = name
        self.electrode_type = electrode_type
        self.contacts: List[Contact] = []
    
    def add_contact(self, label: str, x: float, y: float, z: float) -> None:
        """
        Add a contact to the electrode.
        
        Args:
            label (str): Label for the contact
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate
        """        
        self.contacts.append(Contact(label=label, x=x, y=y, z=z))
    
    def get_contact(self, index: int) -> Optional[Contact]:
        """
        Get a contact by index.
        
        Args:
            index (int): Index of the contact
            
        Returns:
            Contact or None: The contact at the specified index, or None if not found
        """
        if 0 <= index < len(self.contacts):
            return self.contacts[index]
        return None
    
    def get_all_contacts(self) -> List[Contact]:
        """
        Get all contacts for this electrode.
        
        Returns:
            List[Contact]: List of all contacts
        """
        return self.contacts
    
    def get_coordinates_array(self) -> np.ndarray:
        """
        Get all contact coordinates as a numpy array.
        
        Returns:
            np.ndarray: Array of shape (n_contacts, 3) containing all coordinates
        """
        return np.array([contact.coordinates for contact in self.contacts])


class Electrodes:
    """
    Collection of multiple electrodes.
    """
    def __init__(self):
        """Initialize an empty collection of electrodes."""
        self.electrodes: Dict[str, Electrode] = {}
    
    def add_electrode(self, electrode: Electrode) -> None:
        """
        Add an electrode to the collection.
        
        Args:
            electrode (Electrode): The electrode to add
        """
        self.electrodes[electrode.name] = electrode
    
    def create_electrode(self, name: str, electrode_type: str = "") -> Electrode:
        """
        Create and add a new electrode to the collection.
        
        Args:
            name (str): Name of the electrode
            electrode_type (str): Type of the electrode
            
        Returns:
            Electrode: The newly created electrode
        """
        electrode = Electrode(name=name, electrode_type=electrode_type)
        self.electrodes[name] = electrode
        return electrode
    
    def get_electrode(self, name: str) -> Optional[Electrode]:
        """
        Get an electrode by name.
        
        Args:
            name (str): Name of the electrode
            
        Returns:
            Electrode or None: The electrode with the specified name, or None if not found
        """
        return self.electrodes.get(name)
    
    def get_all_electrodes(self) -> Dict[str, Electrode]:
        """
        Get all electrodes in the collection.
        
        Returns:
            Dict[str, Electrode]: Dictionary of all electrodes, keyed by name
        """
        return self.electrodes
    
    def get_all_contacts(self) -> List[Tuple[str, Contact]]:
        """
        Get all contacts from all electrodes.
        
        Returns:
            List[Tuple[str, Contact]]: List of tuples containing (electrode_name, contact)
        """
        all_contacts = []
        for name, electrode in self.electrodes.items():
            for contact in electrode.contacts:
                all_contacts.append((name, contact))
        return all_contacts
