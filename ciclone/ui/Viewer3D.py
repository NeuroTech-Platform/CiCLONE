from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
import numpy as np
from vtkmodules.util import numpy_support

from PyQt6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QListWidgetItem,
    QSizePolicy,
    QHeaderView,
    QVBoxLayout,
    QWidget
)
from PyQt6.QtCore import Qt, QStandardPaths

from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap, QCursor
from ciclone.forms.Viewer3D_ui import Ui_Viewer3D
from ciclone.interfaces.view_interfaces import IViewer3D, IBaseView

class Viewer3D(QWidget, Ui_Viewer3D):
    def __init__(self, nifti_img=None, current_volume_data=None, *args, **kwargs):
        super(Viewer3D, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setup_3d_viewer()
        self.current_nifti_img = nifti_img
        self.current_volume_data = current_volume_data
        self.update_3d_view()
        
    def setup_3d_viewer(self):
        # Create VTK widget
        self.vtkWidget = QVTKRenderWindowInteractor(self.Preview3D)
        layout = QVBoxLayout()
        layout.addWidget(self.vtkWidget)
        self.Preview3D.setLayout(layout)
        
        # Create renderer and interactor
        self.ren = vtk.vtkRenderer()
        self.vtkWidget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.vtkWidget.GetRenderWindow().GetInteractor()
        
        # Set background color (black)
        self.ren.SetBackground(0, 0, 0)
        
        # Initialize the interactor and start
        self.iren.Initialize()
        self.iren.Start()

        # Set interactor style
        self.iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

    def update_3d_view(self):
        if self.current_volume_data is None:
            return

        self.ren.RemoveAllViewProps()

        pixdim = self.current_nifti_img.header.get_zooms()
        vtk_data = vtk.vtkImageData()
        vtk_data.SetDimensions(self.current_volume_data.shape)
        vtk_data.SetSpacing(pixdim)

        # Fast numpy-to-VTK conversion
        flat_data = np.ascontiguousarray(self.current_volume_data).astype(np.float32)
        vtk_array = numpy_support.numpy_to_vtk(
            num_array=flat_data.ravel(order='F'),  # VTK expects Fortran order
            deep=True,
            array_type=vtk.VTK_FLOAT
        )
        vtk_data.GetPointData().SetScalars(vtk_array)

        # Create volume mapper
        volumeMapper = vtk.vtkSmartVolumeMapper()
        volumeMapper.SetInputData(vtk_data)

        # Create volume property
        volumeProperty = vtk.vtkVolumeProperty()
        volumeProperty.ShadeOn()
        volumeProperty.SetInterpolationTypeToLinear()

        # Create color transfer function
        colorFun = vtk.vtkColorTransferFunction()
        colorFun.AddRGBPoint(0, 0.0, 0.0, 0.0)
        colorFun.AddRGBPoint(500, 1.0, 0.5, 0.3)
        colorFun.AddRGBPoint(1000, 1.0, 1.0, 0.9)
        volumeProperty.SetColor(colorFun)

        # Create opacity transfer function
        opacityFun = vtk.vtkPiecewiseFunction()
        opacityFun.AddPoint(0, 0.0)
        opacityFun.AddPoint(500, 0.2)
        opacityFun.AddPoint(1000, 0.8)
        volumeProperty.SetScalarOpacity(opacityFun)

        # Create volume
        volume = vtk.vtkVolume()
        volume.SetMapper(volumeMapper)
        volume.SetProperty(volumeProperty)

        # Add volume to renderer
        self.ren.AddVolume(volume)
        self.ren.ResetCamera()
        
        # Render
        self.vtkWidget.GetRenderWindow().Render()

    def keyPressEvent(self, event):
        camera = self.ren.GetActiveCamera()
        step = 10  # degrees
        if event.key() == Qt.Key.Key_Left:
            camera.Azimuth(-step)
        elif event.key() == Qt.Key.Key_Right:
            camera.Azimuth(step)
        elif event.key() == Qt.Key.Key_Up:
            camera.Elevation(step)
        elif event.key() == Qt.Key.Key_Down:
            camera.Elevation(-step)
        else:
            super().keyPressEvent(event)
        self.ren.ResetCameraClippingRange()
        self.vtkWidget.GetRenderWindow().Render()
    
    # =============================================================================
    # IViewer3D Interface Implementation
    # =============================================================================
    
    def load_volume_data(self, volume_data) -> bool:
        """Load volume data for 3D rendering."""
        try:
            self.current_volume_data = volume_data
            self.update_3d_view()
            return True
        except Exception:
            return False
    
    def update_rendering(self) -> None:
        """Update the 3D rendering."""
        self.update_3d_view()
    
    def reset_camera(self) -> None:
        """Reset camera to default position."""
        if hasattr(self, 'ren') and self.ren:
            self.ren.ResetCamera()
            self.vtkWidget.GetRenderWindow().Render()
    
    def add_electrode_to_scene(self, electrode_data) -> None:
        """Add an electrode to the 3D scene."""
        # Implementation would add electrode visualization
        # This would require extending the current VTK pipeline
        pass
    
    def remove_electrode_from_scene(self, electrode_name: str) -> None:
        """Remove an electrode from the 3D scene."""
        # Implementation would remove electrode visualization
        pass
    
    def update_electrode_visibility(self, electrode_name: str, visible: bool) -> None:
        """Update electrode visibility in 3D scene."""
        # Implementation would toggle electrode visibility
        pass
    
    def set_rendering_quality(self, quality: str) -> None:
        """Set rendering quality (low, medium, high)."""
        # Implementation would adjust VTK rendering parameters
        pass
    
    def enable_interaction(self, enabled: bool) -> None:
        """Enable or disable 3D view interaction."""
        if hasattr(self, 'iren') and self.iren:
            if enabled:
                self.iren.Enable()
            else:
                self.iren.Disable()
    
    def export_screenshot(self, file_path: str) -> bool:
        """Export current view as screenshot."""
        try:
            if hasattr(self, 'vtkWidget') and self.vtkWidget:
                # Capture window to image
                window_to_image = vtk.vtkWindowToImageFilter()
                window_to_image.SetInput(self.vtkWidget.GetRenderWindow())
                window_to_image.Update()
                
                # Write to file
                writer = vtk.vtkPNGWriter()
                writer.SetFileName(file_path)
                writer.SetInputConnection(window_to_image.GetOutputPort())
                writer.Write()
                return True
        except Exception:
            pass
        return False
    
    # =============================================================================
    # IBaseView Interface Implementation
    # =============================================================================
    
    def show_error_message(self, title: str, message: str) -> None:
        """Show an error message to the user."""
        QMessageBox.critical(self, title, message)
    
    def show_warning_message(self, title: str, message: str) -> None:
        """Show a warning message to the user."""
        QMessageBox.warning(self, title, message)
    
    def show_info_message(self, title: str, message: str) -> None:
        """Show an info message to the user."""
        QMessageBox.information(self, title, message)
    
    def set_busy_state(self, busy: bool) -> None:
        """Set the view to busy state (e.g., show loading cursor)."""
        if busy:
            self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    
    def get_widget(self) -> QWidget:
        """Get the underlying QWidget for this view."""
        return self
