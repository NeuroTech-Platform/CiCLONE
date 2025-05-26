"""
Domain models and entities for CiCLONE application.

This package contains the core domain objects that represent the business entities
of the application, such as electrodes, subjects, and their related components.
"""

from .electrodes import Electrode, Electrodes, Contact
from .electrode_element import ElectrodeElement
from .subject import Subject

__all__ = [
    'Electrode',
    'Electrodes', 
    'Contact',
    'ElectrodeElement',
    'Subject'
] 