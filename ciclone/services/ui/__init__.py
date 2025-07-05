# UI Services Package
# Provides UI-related services that maintain proper MVC separation

from .dialog_service import DialogService
from .view_delegate import ViewDelegate
from .electrode_view_delegate import ElectrodeViewDelegate

__all__ = ['DialogService', 'ViewDelegate', 'ElectrodeViewDelegate'] 