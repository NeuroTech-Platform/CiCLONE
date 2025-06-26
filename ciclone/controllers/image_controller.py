from typing import Optional, Tuple, Dict, List
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMessageBox
import numpy as np

from ciclone.models.image_model import ImageModel
from ciclone.interfaces.view_interfaces import IImageView


class ImageController:
    """Controller for managing image operations and coordinating between image model and views."""
    
    def __init__(self, image_model: ImageModel):
        self.image_model = image_model
        self._view = None
    
    def set_view(self, view: IImageView):
        """Set the view reference for UI updates."""
        self._view = view
    
    def load_image(self, file_path: str, opacity: float = 1.0) -> bool:
        """Load a NIFTI image file."""
        success = self.image_model.load_nifti_file(file_path, opacity)
        
        if success and self._view:
            self._view.enable_image_controls()
            self._view.update_slider_ranges()
            self._view.refresh_all_views()
            # Add the loaded file to the DataTreeWidget
            self._view.add_file_to_data_tree(file_path)
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
    
    def remove_image(self, file_path: str) -> bool:
        """Remove an image from the model."""
        success = self.image_model.remove_image(file_path)
        
        if success and self._view:
            self._view.remove_file_from_data_tree(file_path)
            self._view.refresh_all_views()
            
            # If no images left, show default display
            if not self.image_model.is_loaded():
                self._view.show_default_display()
        
        return success

    # Old individual image opacity methods removed - replaced with overlay system

    def get_loaded_images(self) -> List[str]:
        """Get list of loaded image file paths."""
        return self.image_model.get_loaded_images()

    def set_overlay_images(self, base_image_name: str, overlay_image_name: str, opacity: float) -> bool:
        """Set the base and overlay images for two-image overlay system."""
        success = self.image_model.set_overlay_images(base_image_name, overlay_image_name, opacity)
        
        if success and self._view:
            self._view.refresh_all_views()
        
        return success

    def get_overlay_opacity(self) -> float:
        """Get the current overlay opacity."""
        return self.image_model.get_overlay_opacity()

    def get_current_base_image_name(self) -> Optional[str]:
        """Get the current base image name."""
        return self.image_model.get_current_base_image_name()

    def get_current_overlay_image_name(self) -> Optional[str]:
        """Get the current overlay image name."""
        return self.image_model.get_current_overlay_image_name()

    def clear_overlay_state(self):
        """Clear the overlay state (show no images)."""
        self.image_model.clear_overlay_state()
        if self._view:
            self._view.refresh_all_views()
    
    def get_slice_data_for_display(self, orientation: str, slice_index: int) -> Optional[np.ndarray]:
        """Get slice data for display purposes."""
        return self.image_model.get_slice_data(orientation, slice_index)
    
    def create_clean_pixmap_for_display(self, slice_data: np.ndarray, orientation: str, 
                                      label_width: int, label_height: int) -> Optional[QPixmap]:
        """Create a clean pixmap without electrode overlays for display."""
        return self.image_model.create_slice_pixmap_clean(slice_data, orientation, label_width, label_height)
    
    def get_volume_data_for_coordinates(self) -> Optional[np.ndarray]:
        """Get volume data for coordinate calculations."""
        return self.image_model.get_volume_data()
    
    def is_point_visible_on_slice(self, point: Tuple[int, int, int], orientation: str,
                                 current_slices: Dict[str, int]) -> bool:
        """Check if a 3D point is visible on the current slice."""
        return self.image_model.is_point_visible_on_slice(point, orientation, current_slices)
    
    def convert_3d_to_pixel_coords(self, point: Tuple[int, int, int], orientation: str,
                                  scaled_width: int, scaled_height: int) -> Optional[Tuple[int, int]]:
        """Convert 3D coordinates to pixel coordinates for the current view."""
        return self.image_model.convert_3d_to_pixel_coords(point, orientation, scaled_width, scaled_height)
    
    def _show_error(self, message: str):
        """Show error message to user."""
        if self._view:
            QMessageBox.warning(self._view, "Error", message) 