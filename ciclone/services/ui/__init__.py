# UI Services Package
# Provides UI-related services that maintain proper MVC separation

from .dialog_service import DialogService
from .view_delegate import ViewDelegate

__all__ = ['DialogService', 'ViewDelegate'] 