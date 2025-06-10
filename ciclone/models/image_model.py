import numpy as np
from typing import Dict, Tuple, Optional, List
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt


class ImageModel:
    """Model for managing image data and operations."""
    
    def __init__(self):
        self._volume_data: Optional[np.ndarray] = None
        self._affine: Optional[np.ndarray] = None
        self._current_nifti_img = None
        self._current_nifti_path: Optional[str] = None

    def load_nifti_file(self, nifti_path: str) -> bool:
        """Load NIFTI file and store the data."""
        try:
            import nibabel as nib
            self._current_nifti_img = nib.load(nifti_path)
            self._volume_data = self._current_nifti_img.get_fdata()
            self._current_nifti_path = nifti_path
            self._affine = self._current_nifti_img.affine
            return True
        except Exception:
            self._volume_data = None
            self._current_nifti_path = None
            self._current_nifti_img = None
            self._affine = None
            return False

    def get_slice_data(self, orientation: str, slice_index: int) -> Optional[np.ndarray]:
        """Get slice data for a given orientation and index."""
        if self._volume_data is None:
            return None

        try:
            if orientation == 'axial':
                return self._volume_data[:, :, slice_index]
            elif orientation == 'sagittal':
                return self._volume_data[slice_index, :, :]
            elif orientation == 'coronal':
                return self._volume_data[:, slice_index, :]
            return None
        except IndexError:
            return None

    def get_slice_range(self, orientation: str) -> Tuple[int, int]:
        """Get the valid slice range for a given orientation."""
        if self._volume_data is None:
            return (0, 0)

        if orientation == 'axial':
            return (0, self._volume_data.shape[2] - 1)
        elif orientation == 'sagittal':
            return (0, self._volume_data.shape[0] - 1)
        elif orientation == 'coronal':
            return (0, self._volume_data.shape[1] - 1)
        return (0, 0)

    def get_initial_slice(self, orientation: str) -> int:
        """Get the initial slice index for a given orientation."""
        if self._volume_data is None:
            return 0

        if orientation == 'axial':
            return self._volume_data.shape[2] // 2
        elif orientation == 'sagittal':
            return self._volume_data.shape[0] // 2
        elif orientation == 'coronal':
            return self._volume_data.shape[1] // 2
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
        pixdim = self._current_nifti_img.header.get_zooms()
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
            pixel_x = int(x * scaled_width / self._volume_data.shape[0])
            pixel_y = int((self._volume_data.shape[1] - 1 - y) * scaled_height / self._volume_data.shape[1])
        elif orientation == 'sagittal' and abs(x - current_slices['sagittal']) <= 1:
            is_visible = True
            pixel_x = int((self._volume_data.shape[1] - 1 - y) * scaled_width / self._volume_data.shape[1])
            pixel_y = int((self._volume_data.shape[2] - 1 - z) * scaled_height / self._volume_data.shape[2])
        elif orientation == 'coronal' and abs(y - current_slices['coronal']) <= 1:
            is_visible = True
            pixel_x = int(x * scaled_width / self._volume_data.shape[0])
            pixel_y = int((self._volume_data.shape[2] - 1 - z) * scaled_height / self._volume_data.shape[2])

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
        if self._volume_data is None:
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
            x_coord = int(adjusted_x * self._volume_data.shape[0] / pixmap_width)
            y_coord = int((pixmap_height - 1 - adjusted_y) * self._volume_data.shape[1] / pixmap_height)
            z_coord = current_slices['axial']
        elif orientation == 'sagittal':
            x_coord = current_slices['sagittal']
            y_coord = int((pixmap_width - 1 - adjusted_x) * self._volume_data.shape[1] / pixmap_width)
            z_coord = int((pixmap_height - 1 - adjusted_y) * self._volume_data.shape[2] / pixmap_height)
        elif orientation == 'coronal':
            x_coord = int(adjusted_x * self._volume_data.shape[0] / pixmap_width)
            y_coord = current_slices['coronal']
            z_coord = int((pixmap_height - 1 - adjusted_y) * self._volume_data.shape[2] / pixmap_height)
        else:
            return None

        # Clamp coordinates to valid ranges
        x_coord = max(0, min(x_coord, self._volume_data.shape[0] - 1))
        y_coord = max(0, min(y_coord, self._volume_data.shape[1] - 1))
        z_coord = max(0, min(z_coord, self._volume_data.shape[2] - 1))

        return (x_coord, y_coord, z_coord)

    def is_loaded(self) -> bool:
        """Check if an image is currently loaded."""
        return self._volume_data is not None

    def get_affine(self):
        """Get the affine transformation matrix."""
        return self._affine

    def get_current_nifti_img(self):
        """Get the current NIFTI image object."""
        return self._current_nifti_img

    def get_volume_data(self):
        """Get the current volume data."""
        return self._volume_data

    def get_current_path(self) -> Optional[str]:
        """Get the path of the currently loaded image."""
        return self._current_nifti_path 