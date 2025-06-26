"""
View Interfaces for CiCLONE Application

This package contains view interfaces that define contracts between controllers and views,
completing the MVC architecture implementation.

These interfaces enable:
- Proper separation of concerns between controllers and views
- Better testability through mockable view contracts
- Standardized communication protocols
- Future-proof architecture for view swapping
"""

from .view_interfaces import IMainView, IImageView, IViewer3D

__all__ = [
    'IMainView',
    'IImageView', 
    'IViewer3D'
] 