import numpy as np
from typing import Dict, Tuple, Optional, List
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt


class ImageData:
    """Container for individual image data with opacity."""
    def __init__(self, nifti_img, volume_data: np.ndarray, affine: np.ndarray, file_path: str, opacity: float = 1.0):
        self.nifti_img = nifti_img
        self.volume_data = volume_data
        self.affine = affine
        self.file_path = file_path
        self.opacity = opacity


class ImageModel:
    """Model for managing multiple image data and operations."""
    
    def __init__(self):
        self._images: Dict[str, ImageData] = {}  # file_path -> ImageData
        self._primary_image_path: Optional[str] = None  # Used for coordinate calculations
        self._base_image_path: Optional[str] = None  # Base image for overlay
        self._overlay_image_path: Optional[str] = None  # Overlay image
        self._overlay_opacity: float = 1.0  # Opacity of overlay image

    def load_nifti_file(self, nifti_path: str, opacity: float = 1.0) -> bool:
        """Load NIFTI file and store the data."""
        try:
            import nibabel as nib
            nifti_img = nib.load(nifti_path)
            volume_data = nifti_img.get_fdata()
            affine = nifti_img.affine
            
            # Store the image data
            self._images[nifti_path] = ImageData(nifti_img, volume_data, affine, nifti_path, opacity)
            
            # Set as primary if it's the first image
            if self._primary_image_path is None:
                self._primary_image_path = nifti_path
                
            return True
        except Exception:
            return False

    def remove_image(self, file_path: str) -> bool:
        """Remove an image from the model."""
        if file_path in self._images:
            del self._images[file_path]
            
            # Clean up overlay state if the deleted image was being used
            overlay_state_changed = False
            
            if self._base_image_path == file_path:
                self._base_image_path = None
                overlay_state_changed = True
                
            if self._overlay_image_path == file_path:
                self._overlay_image_path = None
                overlay_state_changed = True
            
            # If overlay state was affected, handle the reorganization
            if overlay_state_changed and self._images:
                # Case 1: Base was removed but overlay still exists - promote overlay to base
                if not self._base_image_path and self._overlay_image_path and self._overlay_image_path in self._images:
                    print(f"Info: Promoting overlay to base image after base removal")
                    self._base_image_path = self._overlay_image_path
                    self._overlay_image_path = self._overlay_image_path  # Keep same image in both slots
                    self._overlay_opacity = 0.0  # Show as single image
                # Case 2: Both base and overlay were removed - set first remaining image as base
                elif not self._base_image_path and not self._overlay_image_path:
                    first_image_path = next(iter(self._images.keys()))
                    self._base_image_path = first_image_path
                    self._overlay_image_path = first_image_path
                    self._overlay_opacity = 0.0  # Show as single image
            
            # Update primary image if needed
            if self._primary_image_path == file_path:
                self._primary_image_path = next(iter(self._images.keys())) if self._images else None
                
            return True
        return False

    # Old individual image opacity methods removed - replaced with overlay system

    def get_loaded_images(self) -> List[str]:
        """Get list of loaded image file paths."""
        return list(self._images.keys())

    def set_overlay_images(self, base_image_name: str, overlay_image_name: str, opacity: float) -> bool:
        """Set the base and overlay images for two-image overlay system."""
        import os
        
        # Find the full paths for the given image names
        base_path = None
        overlay_path = None
        
        for file_path in self._images.keys():
            file_name = os.path.basename(file_path)
            if file_name == base_image_name:
                base_path = file_path
            if file_name == overlay_image_name:
                overlay_path = file_path
        
        if base_path and overlay_path and base_path in self._images and overlay_path in self._images:
            # Check if image shapes are compatible
            base_img = self._images[base_path]
            overlay_img = self._images[overlay_path]
            
            if base_img.volume_data.shape != overlay_img.volume_data.shape:
                print(f"Info: Different image sizes detected:")
                print(f"  Base ({os.path.basename(base_path)}): {base_img.volume_data.shape}")
                print(f"  Overlay ({os.path.basename(overlay_path)}): {overlay_img.volume_data.shape}")
                print("Base image will be displayed at full resolution. Overlay blending available only for matching slices.")
            
            self._base_image_path = base_path
            self._overlay_image_path = overlay_path
            self._overlay_opacity = max(0.0, min(1.0, opacity))
            
            # Set primary image to base image for coordinate calculations
            self._primary_image_path = base_path
            return True
        return False

    def get_overlay_opacity(self) -> float:
        """Get the current overlay opacity."""
        return self._overlay_opacity

    def get_current_base_image_name(self) -> Optional[str]:
        """Get the current base image name."""
        if self._base_image_path:
            import os
            return os.path.basename(self._base_image_path)
        return None

    def get_current_overlay_image_name(self) -> Optional[str]:
        """Get the current overlay image name."""
        if self._overlay_image_path:
            import os
            return os.path.basename(self._overlay_image_path)
        return None

    def clear_overlay_state(self):
        """Clear the overlay state (show no images)."""
        self._base_image_path = None
        self._overlay_image_path = None
        self._overlay_opacity = 1.0

    def get_slice_data(self, orientation: str, slice_index: int) -> Optional[np.ndarray]:
        """Get composite slice data for two-image overlay system."""
        if not self._images:
            return None

        # If no overlay configuration is set, return None (show nothing)
        if not self._base_image_path or self._base_image_path not in self._images:
            return None

        # Get base and overlay images
        base_img = self._images.get(self._base_image_path)
        overlay_img = self._images.get(self._overlay_image_path) if self._overlay_image_path else None
        
        if not base_img:
            return None

        try:
            # Get base slice
            if orientation == 'axial':
                base_slice = base_img.volume_data[:, :, slice_index]
            elif orientation == 'sagittal':
                base_slice = base_img.volume_data[slice_index, :, :]
            elif orientation == 'coronal':
                base_slice = base_img.volume_data[:, slice_index, :]
            else:
                return None

            # If no overlay image or opacity is 0, return base image only
            if not overlay_img or self._overlay_opacity <= 0:
                return base_slice.astype(float)

            # Get overlay slice
            try:
                if orientation == 'axial':
                    overlay_slice = overlay_img.volume_data[:, :, slice_index]
                elif orientation == 'sagittal':
                    overlay_slice = overlay_img.volume_data[slice_index, :, :]
                elif orientation == 'coronal':
                    overlay_slice = overlay_img.volume_data[:, slice_index, :]
            except IndexError:
                # If overlay slice doesn't exist, return base only
                return base_slice.astype(float)

            # Handle shape mismatch - resample overlay to match base image size
            if base_slice.shape != overlay_slice.shape:
                print(f"Info: Resampling overlay to match base image size")
                print(f"  Base: {base_slice.shape}, Overlay: {overlay_slice.shape}")
                overlay_slice = self._resample_slice_to_match(overlay_slice, base_slice.shape)

            # Normalize both slices
            base_slice = base_slice.astype(float)
            overlay_slice = overlay_slice.astype(float)
            
            if base_slice.max() != base_slice.min():
                base_slice = (base_slice - base_slice.min()) / (base_slice.max() - base_slice.min())
            
            if overlay_slice.max() != overlay_slice.min():
                overlay_slice = (overlay_slice - overlay_slice.min()) / (overlay_slice.max() - overlay_slice.min())

            # Blend base and overlay with opacity
            try:
                composite_slice = base_slice * (1.0 - self._overlay_opacity) + overlay_slice * self._overlay_opacity
                return composite_slice
            except ValueError as e:
                print(f"Error blending images: {e}")
                print("Returning base image only")
                return base_slice
            
        except IndexError:
            return None

    def _resample_slice_to_match(self, overlay_slice: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        """Resample overlay slice to match target shape using numpy-based interpolation."""
        import numpy as np
        
        # Get source and target dimensions
        src_h, src_w = overlay_slice.shape
        tgt_h, tgt_w = target_shape
        
        # Create coordinate grids for the target shape
        y_coords = np.linspace(0, src_h - 1, tgt_h)
        x_coords = np.linspace(0, src_w - 1, tgt_w)
        
        # Create meshgrid for interpolation coordinates
        yy, xx = np.meshgrid(y_coords, x_coords, indexing='ij')
        
        # Get integer coordinates and fractional parts
        y0 = np.floor(yy).astype(int)
        x0 = np.floor(xx).astype(int)
        y1 = np.minimum(y0 + 1, src_h - 1)
        x1 = np.minimum(x0 + 1, src_w - 1)
        
        # Get fractional parts
        wy = yy - y0
        wx = xx - x0
        
        # Bilinear interpolation
        # Get the four corner values
        val_00 = overlay_slice[y0, x0]
        val_01 = overlay_slice[y0, x1]
        val_10 = overlay_slice[y1, x0]
        val_11 = overlay_slice[y1, x1]
        
        # Interpolate
        val_0 = val_00 * (1 - wx) + val_01 * wx
        val_1 = val_10 * (1 - wx) + val_11 * wx
        resampled_slice = val_0 * (1 - wy) + val_1 * wy
        
        print(f"  Resampled overlay from {overlay_slice.shape} to {resampled_slice.shape}")
        return resampled_slice.astype(overlay_slice.dtype)

    def get_slice_range(self, orientation: str) -> Tuple[int, int]:
        """Get the valid slice range for a given orientation."""
        if not self._images:
            return (0, 0)

        # Get primary image for reference dimensions
        primary_img = self._images.get(self._primary_image_path)
        if not primary_img:
            return (0, 0)

        if orientation == 'axial':
            return (0, primary_img.volume_data.shape[2] - 1)
        elif orientation == 'sagittal':
            return (0, primary_img.volume_data.shape[0] - 1)
        elif orientation == 'coronal':
            return (0, primary_img.volume_data.shape[1] - 1)
        return (0, 0)

    def get_initial_slice(self, orientation: str) -> int:
        """Get the initial slice index for a given orientation."""
        if not self._images:
            return 0

        # Get primary image for reference dimensions
        primary_img = self._images.get(self._primary_image_path)
        if not primary_img:
            return 0

        if orientation == 'axial':
            return primary_img.volume_data.shape[2] // 2
        elif orientation == 'sagittal':
            return primary_img.volume_data.shape[0] // 2
        elif orientation == 'coronal':
            return primary_img.volume_data.shape[1] // 2
        return 0

    def create_slice_pixmap(self, 
                          slice_data: np.ndarray, 
                          orientation: str,
                          label_width: int,
                          label_height: int,
                          electrode_points: Dict[str, Dict[str, Tuple[int, int, int]]],
                          processed_contacts: Dict[str, List[Tuple[int, int, int]]],
                          current_slices: Dict[str, int]) -> QPixmap:
        """Create a QPixmap for a slice with electrode points and contacts."""
        # Create clean pixmap first
        clean_pixmap = self.create_slice_pixmap_clean(slice_data, orientation, label_width, label_height)
        
        # Draw points on the pixmap
        painter = QPainter(clean_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get scale factors for coordinate conversion
        scaled_width = clean_pixmap.width()
        scaled_height = clean_pixmap.height()
        
        # Apply orientation-specific transformations to get original dimensions
        transformed_slice = np.rot90(slice_data)
        if orientation == 'sagittal':
            transformed_slice = np.fliplr(transformed_slice)
        orig_height, orig_width = transformed_slice.shape

        # Draw entry and output points
        for electrode_name, points in electrode_points.items():
            hue = abs(hash(electrode_name)) % 360
            electrode_color = QColor()
            electrode_color.setHsv(hue, 200, 255, 180)

            if 'entry' in points:
                self._draw_point_if_visible(painter, points['entry'], orientation,
                                          current_slices, orig_width, orig_height,
                                          scaled_width, scaled_height, electrode_color)

            if 'output' in points:
                self._draw_point_if_visible(painter, points['output'], orientation,
                                          current_slices, orig_width, orig_height,
                                          scaled_width, scaled_height, electrode_color)

        # Draw processed contacts
        for electrode_name, contacts in processed_contacts.items():
            hue = abs(hash(electrode_name)) % 360
            contact_color = QColor()
            contact_color.setHsv(hue, 200, 255, 180)

            for contact_point in contacts:
                self._draw_point_if_visible(painter, contact_point, orientation,
                                          current_slices, orig_width, orig_height,
                                          scaled_width, scaled_height, contact_color)

        painter.end()
        return clean_pixmap
    
    def create_slice_pixmap_clean(self, 
                                slice_data: np.ndarray, 
                                orientation: str,
                                label_width: int,
                                label_height: int) -> QPixmap:
        """Create a clean QPixmap for a slice without electrode overlays."""
        # Apply orientation-specific transformations
        slice_data = np.rot90(slice_data)
        if orientation == 'sagittal':
            slice_data = np.fliplr(slice_data)

        # Normalize to 0-255 for display
        slice_data = slice_data.astype(float)
        slice_data = ((slice_data - slice_data.min()) /
                      (slice_data.max() - slice_data.min()) * 255).astype(np.uint8)

        # Create QImage
        height, width = slice_data.shape
        bytes_per_line = width
        q_img = QImage(slice_data.tobytes(), width, height, bytes_per_line, QImage.Format.Format_Grayscale8)

        # Calculate aspect ratio based on voxel dimensions
        pixdim = self._images.get(self._primary_image_path).nifti_img.header.get_zooms()
        if orientation == 'axial':
            aspect_ratio = pixdim[1] / pixdim[0]  # y/x
        elif orientation == 'sagittal':
            aspect_ratio = 1 / (pixdim[2] / pixdim[1])  # z/y
        else:  # coronal
            aspect_ratio = 1 / (pixdim[2] / pixdim[0])  # z/x

        # Calculate dimensions to fill the label while maintaining aspect ratio
        image_aspect = width / height
        corrected_aspect = image_aspect * aspect_ratio

        if corrected_aspect >= label_width / label_height:
            scaled_width = label_width
            scaled_height = int(scaled_width / corrected_aspect)
        else:
            scaled_height = label_height
            scaled_width = int(scaled_height * corrected_aspect)

        # Scale the image
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        return scaled_pixmap

    def _draw_point_if_visible(self, 
                             painter: QPainter,
                             point: Tuple[int, int, int],
                             orientation: str,
                             current_slices: Dict[str, int],
                             orig_width: int,
                             orig_height: int,
                             scaled_width: int,
                             scaled_height: int,
                             color: QColor):
        """Draw a point on the current slice if it's visible."""
        x, y, z = point
        is_visible = False
        pixel_x, pixel_y = 0, 0

        if orientation == 'axial' and abs(z - current_slices['axial']) <= 1:
            is_visible = True
            pixel_x = int(x * scaled_width / orig_width)
            pixel_y = int((orig_height - 1 - y) * scaled_height / orig_height)
        elif orientation == 'sagittal' and abs(x - current_slices['sagittal']) <= 1:
            is_visible = True
            pixel_x = int((orig_width - 1 - y) * scaled_width / orig_width)
            pixel_y = int((orig_height - 1 - z) * scaled_height / orig_height)
        elif orientation == 'coronal' and abs(y - current_slices['coronal']) <= 1:
            is_visible = True
            pixel_x = int(x * scaled_width / orig_width)
            pixel_y = int((orig_height - 1 - z) * scaled_height / orig_height)

        if is_visible:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            circle_radius = 5
            painter.drawEllipse(pixel_x - circle_radius, pixel_y - circle_radius,
                              circle_radius * 2, circle_radius * 2)

    def get_3d_coordinates(self,
                         orientation: str,
                         click_x: int,
                         click_y: int,
                         label_width: int,
                         label_height: int,
                         pixmap_width: int,
                         pixmap_height: int,
                         current_slices: Dict[str, int]) -> Optional[Tuple[int, int, int]]:
        """Convert 2D click coordinates to 3D volume coordinates."""
        if not self._images:
            return None

        # Get primary image for reference dimensions
        primary_img = self._images.get(self._primary_image_path)
        if not primary_img:
            return None

        # Calculate the offset to center the pixmap in the label
        x_offset = (label_width - pixmap_width) // 2
        y_offset = (label_height - pixmap_height) // 2

        # Adjust click coordinates relative to the pixmap
        adjusted_x = click_x - x_offset
        adjusted_y = click_y - y_offset

        # Check if click is within pixmap bounds
        if adjusted_x < 0 or adjusted_x >= pixmap_width or adjusted_y < 0 or adjusted_y >= pixmap_height:
            return None

        # Convert to volume coordinates
        if orientation == 'axial':
            x_coord = int(adjusted_x * primary_img.volume_data.shape[0] / pixmap_width)
            y_coord = int((pixmap_height - 1 - adjusted_y) * primary_img.volume_data.shape[1] / pixmap_height)
            z_coord = current_slices['axial']
        elif orientation == 'sagittal':
            x_coord = current_slices['sagittal']
            y_coord = int((pixmap_width - 1 - adjusted_x) * primary_img.volume_data.shape[1] / pixmap_width)
            z_coord = int((pixmap_height - 1 - adjusted_y) * primary_img.volume_data.shape[2] / pixmap_height)
        elif orientation == 'coronal':
            x_coord = int(adjusted_x * primary_img.volume_data.shape[0] / pixmap_width)
            y_coord = current_slices['coronal']
            z_coord = int((pixmap_height - 1 - adjusted_y) * primary_img.volume_data.shape[2] / pixmap_height)
        else:
            return None

        # Clamp coordinates to valid ranges
        x_coord = max(0, min(x_coord, primary_img.volume_data.shape[0] - 1))
        y_coord = max(0, min(y_coord, primary_img.volume_data.shape[1] - 1))
        z_coord = max(0, min(z_coord, primary_img.volume_data.shape[2] - 1))

        return (x_coord, y_coord, z_coord)

    def is_loaded(self) -> bool:
        """Check if an image is currently loaded."""
        return bool(self._images)

    def get_affine(self):
        """Get the affine transformation matrix."""
        if not self._images:
            return None
        return self._images[self._primary_image_path].affine

    def get_current_nifti_img(self):
        """Get the current NIFTI image object."""
        if not self._images:
            return None
        return self._images[self._primary_image_path].nifti_img

    def get_volume_data(self):
        """Get the current volume data."""
        if not self._images:
            return None
        return self._images[self._primary_image_path].volume_data

    def get_current_path(self) -> Optional[str]:
        """Get the path of the currently loaded image."""
        return self._primary_image_path
    
    def is_point_visible_on_slice(self, point: Tuple[int, int, int], orientation: str, 
                                 current_slices: Dict[str, int]) -> bool:
        """Check if a 3D point is visible on the current slice."""
        x, y, z = point
        
        if orientation == 'axial' and abs(z - current_slices['axial']) <= 1:
            return True
        elif orientation == 'sagittal' and abs(x - current_slices['sagittal']) <= 1:
            return True
        elif orientation == 'coronal' and abs(y - current_slices['coronal']) <= 1:
            return True
        
        return False
    
    def convert_3d_to_pixel_coords(self, point: Tuple[int, int, int], orientation: str,
                                  scaled_width: int, scaled_height: int) -> Optional[Tuple[int, int]]:
        """Convert 3D coordinates to pixel coordinates for the current view."""
        if not self._images or not self._primary_image_path:
            return None
            
        x, y, z = point
        primary_img = self._images.get(self._primary_image_path)
        if not primary_img:
            return None
            
        volume_data = primary_img.volume_data
        
        # Use the same logic as the original _draw_point_if_visible method
        if orientation == 'axial':
            pixel_x = int(x * scaled_width / volume_data.shape[0])
            pixel_y = int((volume_data.shape[1] - 1 - y) * scaled_height / volume_data.shape[1])
        elif orientation == 'sagittal':
            pixel_x = int((volume_data.shape[1] - 1 - y) * scaled_width / volume_data.shape[1])
            pixel_y = int((volume_data.shape[2] - 1 - z) * scaled_height / volume_data.shape[2])
        elif orientation == 'coronal':
            pixel_x = int(x * scaled_width / volume_data.shape[0])
            pixel_y = int((volume_data.shape[2] - 1 - z) * scaled_height / volume_data.shape[2])
        else:
            return None
        
        return (pixel_x, pixel_y) 