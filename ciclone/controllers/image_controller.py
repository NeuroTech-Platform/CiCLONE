from typing import Optional, Tuple, Dict, List
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMessageBox

from ciclone.models.image_model import ImageModel


class ImageController:
    """Controller for managing image operations and coordinating between image model and views."""
    
    def __init__(self, image_model: ImageModel):
        self.image_model = image_model
        self._view = None
    
    def set_view(self, view):
        """Set the view reference for UI updates."""
        self._view = view
    
    def load_image(self, file_path: str) -> bool:
        """Load a NIFTI image file."""
        success = self.image_model.load_nifti_file(file_path)
        
        if success and self._view:
            self._view.enable_image_controls()
            self._view.update_slider_ranges()
            self._view.refresh_all_views()
        elif not success and self._view:
            self._show_error("Failed to load NIFTI file.")
            self._view.show_default_display()
        
        return success
    
    def get_slice_range(self, orientation: str) -> Tuple[int, int]:
        """Get the valid slice range for an orientation."""
        return self.image_model.get_slice_range(orientation)
    
    def get_initial_slice(self, orientation: str) -> int:
        """Get the initial slice index for an orientation."""
        return self.image_model.get_initial_slice(orientation)
    
    def create_slice_pixmap(self, 
                          orientation: str, 
                          slice_index: int,
                          label_width: int,
                          label_height: int,
                          electrode_points: Dict[str, Dict[str, Tuple[int, int, int]]],
                          processed_contacts: Dict[str, List[Tuple[int, int, int]]],
                          current_slices: Dict[str, int]) -> Optional[QPixmap]:
        """Create a pixmap for displaying a slice with electrode overlays."""
        slice_data = self.image_model.get_slice_data(orientation, slice_index)
        if slice_data is None:
            return None
        
        return self.image_model.create_slice_pixmap(
            slice_data, orientation,
            label_width, label_height,
            electrode_points, processed_contacts,
            current_slices
        )
    
    def get_3d_coordinates_from_click(self,
                                    orientation: str,
                                    click_x: int,
                                    click_y: int,
                                    label_width: int,
                                    label_height: int,
                                    pixmap_width: int,
                                    pixmap_height: int,
                                    current_slices: Dict[str, int]) -> Optional[Tuple[int, int, int]]:
        """Convert 2D click coordinates to 3D volume coordinates."""
        return self.image_model.get_3d_coordinates(
            orientation, click_x, click_y,
            label_width, label_height,
            pixmap_width, pixmap_height,
            current_slices
        )
    
    def is_image_loaded(self) -> bool:
        """Check if an image is currently loaded."""
        return self.image_model.is_loaded()
    
    def get_affine_transform(self):
        """Get the affine transformation matrix of the loaded image."""
        return self.image_model.get_affine()
    
    def get_current_nifti_image(self):
        """Get the current NIFTI image object."""
        return self.image_model.get_current_nifti_img()
    
    def get_volume_data(self):
        """Get the current volume data."""
        return self.image_model.get_volume_data()
    
    def _show_error(self, message: str):
        """Show error message to user."""
        if self._view:
            QMessageBox.warning(self._view, "Error", message) 