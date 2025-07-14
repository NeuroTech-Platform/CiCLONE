from PyQt6.QtWidgets import QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QMenu, QGraphicsEllipseItem
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPointF, QPoint
from PyQt6.QtGui import QPixmap, QWheelEvent, QMouseEvent, QPainter, QTransform, QKeySequence, QAction, QPen, QBrush, QColor

class ClickableImageLabel(QGraphicsView):
    clicked = pyqtSignal(int, int)  # x, y in original image coordinates
    marker_drag_started = pyqtSignal(str, str, int)  # electrode_name, coord_type, contact_index
    marker_drag_ended = pyqtSignal(str, str, int, int, int)  # electrode_name, coord_type, contact_index, x, y
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize graphics scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Pixmap item for the image
        self.pixmap_item = None
        self.original_pixmap = None
        
        # Zoom settings
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.1
        
        # Smooth zoom animation
        self.zoom_timer = QTimer()
        self.zoom_timer.timeout.connect(self._smooth_zoom_step)
        self.target_zoom = 1.0
        self.zoom_animation_speed = 0.15  # Controls smoothness - smaller = smoother
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # Disable default dragging
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # Zoom under mouse
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        
        # Keep scrollbars for proper zoom handling
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Enable mouse tracking for smooth zoom to cursor
        self.setMouseTracking(True)
        
        # Zoom center is now handled automatically by AnchorUnderMouse
        # Track if we're in fitted mode (auto-resize) or user zoom mode
        self._is_fitted_mode = True
        

        
        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable keyboard shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Track markers separately from the image
        self.markers = []  # List to keep track of marker items
        self.marker_data = {}  # Maps marker to electrode data: {marker: {'electrode_name': str, 'coord_type': str, 'contact_index': int}}
        
        # Drag state
        self.drag_mode = False
        self.dragged_marker = None
        self.drag_start_pos = None
        self.drag_offset = None  # Offset from marker center to mouse click
        self.drag_tolerance = 5  # pixels - reduced for more precise selection
        
        # Track crosshair elements separately
        self.crosshair_horizontal = None
        self.crosshair_vertical = None
    
    def setPixmap(self, pixmap: QPixmap):
        """Set the pixmap to display."""
        if pixmap is None:
            return
            
        self.original_pixmap = pixmap
        
        # Store current state if we have an existing image and we're in manual zoom mode
        preserve_zoom = False
        stored_zoom_factor = self.zoom_factor
        stored_target_zoom = self.target_zoom
        stored_transform = None
        
        if self.pixmap_item and not self._is_fitted_mode:
            preserve_zoom = True
            # Store the current transform to preserve both zoom and position
            stored_transform = self.transform()
        
        # Clear existing pixmap item
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)
        
        # Add new pixmap item
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        
        # Update scene rect
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        
        if preserve_zoom and stored_transform:
            # Restore the exact transform to preserve both zoom and position
            self.setTransform(stored_transform)
            
            # Restore zoom tracking variables
            self.zoom_factor = stored_zoom_factor
            self.target_zoom = stored_target_zoom
            # Stay in manual zoom mode
            self._is_fitted_mode = False
        else:
            # Either first time or we were in fitted mode - just fit to view
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._reset_to_fitted_mode()
    
    def _reset_to_fitted_mode(self):
        """Helper method to reset zoom tracking to fitted mode."""
        current_scale = self.transform().m11()
        self.zoom_factor = current_scale
        self.target_zoom = current_scale
        self._is_fitted_mode = True
    
    def pixmap(self):
        """Get the current pixmap."""
        return self.original_pixmap
    
    def clear(self):
        """Clear the image."""
        self.scene.clear()
        self.pixmap_item = None
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.target_zoom = 1.0
        self._is_fitted_mode = True
        self.markers.clear()  # Clear marker tracking list
        self.crosshair_horizontal = None
        self.crosshair_vertical = None
    
    def setText(self, text: str):
        """Set text when no image is available (for compatibility)."""
        self.clear()
        # You could add a text item to the scene if needed
        # For now, just clear the view
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events for zooming."""
        if self.pixmap_item is None:
            # Let the parent handle it if no image is loaded
            super().wheelEvent(event)
            return
        
        # The AnchorUnderMouse setting will automatically handle centering
        # No need to manually store zoom center
        
        # Calculate zoom delta - use smaller steps for smoother zooming
        delta = event.angleDelta().y()
        if delta == 0:
            return
            
        zoom_in = delta > 0
        
        # Use smaller zoom steps for smoother experience
        zoom_step = 0.05  # Reduced from 0.1 for smoother zooming
        
        # Set target zoom
        if zoom_in:
            self.target_zoom = min(self.zoom_factor * (1 + zoom_step), self.max_zoom)
        else:
            self.target_zoom = max(self.zoom_factor * (1 - zoom_step), self.min_zoom)
        
        # Only start animation if target changed significantly
        if abs(self.target_zoom - self.zoom_factor) > 0.001:
            # User is manually zooming, exit fitted mode
            self._is_fitted_mode = False
            if not self.zoom_timer.isActive():
                self.zoom_timer.start(16)  # ~60 FPS
        
        event.accept()
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for zoom control."""
        if self.pixmap_item is None:
            super().keyPressEvent(event)
            return
        
        # Handle zoom shortcuts
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_0:
                # Ctrl+0: Reset zoom to fit
                self.fit_to_view()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Equal or event.key() == Qt.Key.Key_Plus:
                # Ctrl+Plus: Zoom in
                self.zoom_in()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                # Ctrl+Minus: Zoom out
                self.zoom_out()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_1:
                # Ctrl+1: Reset to 100% (1:1)
                self.reset_zoom()
                event.accept()
                return
        
        super().keyPressEvent(event)
    
    def zoom_in(self):
        """Zoom in programmatically."""
        if self.pixmap_item:
            # Exit fitted mode when user zooms manually
            self._is_fitted_mode = False
            self.target_zoom = min(self.zoom_factor * (1 + self.zoom_step), self.max_zoom)
            if not self.zoom_timer.isActive():
                self.zoom_timer.start(16)
    
    def zoom_out(self):
        """Zoom out programmatically."""
        if self.pixmap_item:
            # Exit fitted mode when user zooms manually
            self._is_fitted_mode = False
            self.target_zoom = max(self.zoom_factor * (1 - self.zoom_step), self.min_zoom)
            if not self.zoom_timer.isActive():
                self.zoom_timer.start(16)
    
    def _show_context_menu(self, position):
        """Show context menu with zoom options."""
        if self.pixmap_item is None:
            return
        
        menu = QMenu(self)
        
        # Zoom actions
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
        zoom_in_action.triggered.connect(self.zoom_in)
        menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self.zoom_out)
        menu.addAction(zoom_out_action)
        
        menu.addSeparator()
        
        fit_view_action = QAction("Fit to View", self)
        fit_view_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_view_action.triggered.connect(self.fit_to_view)
        menu.addAction(fit_view_action)
        
        reset_zoom_action = QAction("100% (1:1)", self)
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+1"))
        reset_zoom_action.triggered.connect(self.reset_zoom)
        menu.addAction(reset_zoom_action)
        
        menu.addSeparator()
        
        # Show current zoom level
        zoom_info_action = QAction(f"Current Zoom: {self.zoom_factor:.1f}x", self)
        zoom_info_action.setEnabled(False)
        menu.addAction(zoom_info_action)
        
        # Show the menu
        menu.exec(self.mapToGlobal(position))
    
    def _smooth_zoom_step(self):
        """Perform one step of smooth zoom animation."""
        if abs(self.zoom_factor - self.target_zoom) < 0.01:
            # Animation complete
            self.zoom_factor = self.target_zoom
            self.zoom_timer.stop()
        else:
            # Continue animation
            diff = self.target_zoom - self.zoom_factor
            self.zoom_factor += diff * self.zoom_animation_speed
        
        # Apply zoom
        self._apply_zoom()
    
    def _apply_zoom(self):
        """Apply the current zoom factor."""
        if self.pixmap_item is None:
            return
        
        # Calculate the scale factor difference
        current_scale = self.transform().m11()
        scale_factor = self.zoom_factor / current_scale if current_scale != 0 else self.zoom_factor
        
        # Apply incremental scaling to use the anchor point properly
        if abs(scale_factor - 1.0) > 0.001:  # Only scale if there's a significant change
            self.scale(scale_factor, scale_factor)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap_item:
            # Convert view coordinates to scene coordinates
            scene_pos = self.mapToScene(event.position().toPoint())
            
            # Check if click is near a marker
            nearby_marker = self.get_marker_at_position(scene_pos, self.drag_tolerance)
            
            if nearby_marker and nearby_marker in self.marker_data and self.is_movement_enabled_for_marker(nearby_marker):
                # Start drag mode
                self.drag_mode = True
                self.dragged_marker = nearby_marker
                self.drag_start_pos = scene_pos
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                
                # Emit drag started signal
                marker_data = self.marker_data[nearby_marker]
                self.marker_drag_started.emit(
                    marker_data['electrode_name'],
                    marker_data['coord_type'],
                    marker_data['contact_index']
                )
                
                # Accept the event to prevent further processing
                event.accept()
                return
            
            # Convert scene coordinates to original image coordinates
            if self.pixmap_item and self.original_pixmap:
                # Get the position relative to the pixmap item
                item_pos = self.pixmap_item.mapFromScene(scene_pos)
                
                # Ensure coordinates are within image bounds
                pixmap_rect = self.pixmap_item.boundingRect()
                if pixmap_rect.contains(item_pos):
                    # Convert to integer coordinates for the original image
                    x = int(item_pos.x())
                    y = int(item_pos.y())
                    
                    # Emit signal with original image coordinates
                    self.clicked.emit(x, y)
                    
                    # Accept the event to prevent further processing that might reset zoom
                    event.accept()
                    return
        
        # Only call parent if we didn't handle the click
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events."""
        if self.drag_mode and self.dragged_marker and self.dragged_marker in self.marker_data:
            # Convert view coordinates to scene coordinates
            scene_pos = self.mapToScene(event.position().toPoint())
            
            # Convert to image coordinates - same as marker creation
            if self.pixmap_item and self.original_pixmap:
                # Get the position relative to the pixmap item
                item_pos = self.pixmap_item.mapFromScene(scene_pos)
                
                # Ensure coordinates are within image bounds
                pixmap_rect = self.pixmap_item.boundingRect()
                if pixmap_rect.contains(item_pos):
                    # Convert to integer coordinates for the original image
                    x = int(item_pos.x())
                    y = int(item_pos.y())
                    
                    # Get the original radius from marker data, with fallback
                    marker_data = self.marker_data[self.dragged_marker]
                    radius = marker_data.get('original_radius', 0.5)
                    
                    # Update marker position using same coordinate system as creation
                    self.dragged_marker.setRect(x - radius, y - radius, radius * 2, radius * 2)
            
            # Accept the event to prevent further processing
            event.accept()
            return
        elif self.drag_mode and self.dragged_marker:
            # Safety: Reset drag mode if marker has no data
            self.drag_mode = False
            self.dragged_marker = None
            self.drag_start_pos = None
            self.drag_offset = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # No need to track mouse position here since _apply_zoom gets it directly
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton and self.drag_mode and self.dragged_marker:
            # Only process if marker has data
            if self.dragged_marker in self.marker_data:
                # Convert view coordinates to scene coordinates
                scene_pos = self.mapToScene(event.position().toPoint())
                
                # Convert to image coordinates - same as normal click
                if self.pixmap_item and self.original_pixmap:
                    # Get the position relative to the pixmap item
                    item_pos = self.pixmap_item.mapFromScene(scene_pos)
                    
                    # Ensure coordinates are within image bounds
                    pixmap_rect = self.pixmap_item.boundingRect()
                    if pixmap_rect.contains(item_pos):
                        # Convert to integer coordinates for the original image
                        x = int(item_pos.x())
                        y = int(item_pos.y())
                        
                        
                        # Emit drag ended signal - this is like a click at the new position
                        marker_data = self.marker_data[self.dragged_marker]
                        self.marker_drag_ended.emit(
                            marker_data['electrode_name'],
                            marker_data['coord_type'],
                            marker_data['contact_index'],
                            x, y
                        )
            
            # Reset drag state
            self.drag_mode = False
            self.dragged_marker = None
            self.drag_start_pos = None
            self.drag_offset = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
            # Accept the event to prevent further processing
            event.accept()
            return
        
        # Call parent for other events
        super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        if self.pixmap_item:
            # If we're at the initial fitted zoom, re-fit on resize
            # Otherwise maintain current zoom level
            if self._is_at_fitted_zoom():
                self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            # Update zoom tracking to match the new fitted scale
                current_scale = self.transform().m11()
                self.zoom_factor = current_scale
                self.target_zoom = current_scale
    
    def _is_at_fitted_zoom(self):
        """Check if we're currently in fitted zoom mode."""
        return self._is_fitted_mode
    
    def fit_to_view(self):
        """Fit the image to the view."""
        if self.pixmap_item:
            # Stop any ongoing zoom animation
            if self.zoom_timer.isActive():
                self.zoom_timer.stop()
            
            # Fit the view using built-in functionality
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            
            # Update zoom tracking to match the current scale
            current_scale = self.transform().m11()
            self.zoom_factor = current_scale
            self.target_zoom = current_scale
            # Re-enter fitted mode
            self._is_fitted_mode = True
    
    def reset_zoom(self):
        """Reset zoom to 1:1 scale."""
        if self.pixmap_item:
            # Stop any ongoing zoom animation
            if self.zoom_timer.isActive():
                self.zoom_timer.stop()
            
            # Reset to 1:1 scale
            self.resetTransform()
            self.scale(1.0, 1.0)
            self.centerOn(self.pixmap_item)
            
            # Update zoom tracking
            self.zoom_factor = 1.0
            self.target_zoom = 1.0
            # Exit fitted mode - this is a manual 1:1 zoom
            self._is_fitted_mode = False
    
    def add_marker(self, x, y, color=QColor(255, 0, 0), radius=3, electrode_name=None, coord_type=None, contact_index=-1):
        """Add a marker at the specified image coordinates without affecting the image."""
        if not self.pixmap_item:
            return None
            
        # Create a marker (circle) at the specified position
        marker = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
        
        # Set marker appearance
        pen = QPen(color, 2)
        brush = QBrush(color)
        marker.setPen(pen)
        marker.setBrush(brush)
        
        # Set Z-value to ensure markers appear in front of the image
        marker.setZValue(5)  # Higher than image (default 0), but lower than crosshairs
        
        # Add to scene and track it
        self.scene.addItem(marker)
        self.markers.append(marker)
        
        # Store electrode data if provided
        if electrode_name and coord_type:
            self.marker_data[marker] = {
                'electrode_name': electrode_name,
                'coord_type': coord_type,
                'contact_index': contact_index,
                'original_radius': radius
            }
        
        return marker
    
    def remove_marker(self, marker):
        """Remove a specific marker from the scene."""
        if marker in self.markers:
            self.scene.removeItem(marker)
            self.markers.remove(marker)
            # Remove marker data if it exists
            if marker in self.marker_data:
                del self.marker_data[marker]
    
    def clear_markers(self):
        """Remove all markers from the scene."""
        for marker in self.markers:
            self.scene.removeItem(marker)
        self.markers.clear()
        self.marker_data.clear()
    
    def get_markers(self):
        """Get all current markers."""
        return self.markers.copy()
    
    def get_marker_at_position(self, scene_pos, tolerance=10):
        """Get marker at or near the specified scene position."""
        tolerance_squared = tolerance * tolerance
        
        # Find the closest marker within tolerance
        closest_marker = None
        closest_distance = float('inf')
        
        for marker in self.markers:
            # Get marker center position in scene coordinates
            marker_rect = marker.boundingRect()
            marker_center = marker_rect.center()
            # Add the marker's position to get the actual scene position
            marker_scene_center = marker.scenePos() + marker_center
            
            # Calculate distance from click point
            dx = scene_pos.x() - marker_scene_center.x()
            dy = scene_pos.y() - marker_scene_center.y()
            distance_squared = dx * dx + dy * dy
            
            if distance_squared <= tolerance_squared and distance_squared < closest_distance:
                closest_marker = marker
                closest_distance = distance_squared
        
        
        return closest_marker
    
    def is_movement_enabled_for_marker(self, marker):
        """Check if movement is enabled for a specific marker."""
        if marker not in self.marker_data:
            return False
        
        # This will be set by the parent/controller
        return getattr(self, '_movement_enabled_callback', lambda *args: False)(
            self.marker_data[marker]['electrode_name']
        )
    
    def set_movement_enabled_callback(self, callback):
        """Set callback function to check if movement is enabled for an electrode."""
        self._movement_enabled_callback = callback
    
    def debug_marker_data(self):
        """Debug method to check marker data consistency."""
        print(f"Total markers: {len(self.markers)}")
        print(f"Markers with data: {len(self.marker_data)}")
        for i, marker in enumerate(self.markers):
            if marker in self.marker_data:
                data = self.marker_data[marker]
                radius = data.get('original_radius', 'N/A')
                pos = marker.pos()
                rect = marker.rect()
                print(f"  Marker {i}: {data['electrode_name']} {data['coord_type']} {data['contact_index']} radius={radius}")
                print(f"    Position: ({pos.x():.1f}, {pos.y():.1f})")
                print(f"    Rect: ({rect.x():.1f}, {rect.y():.1f}, {rect.width():.1f}, {rect.height():.1f})")
            else:
                print(f"  Marker {i}: NO DATA")
        return len(self.markers), len(self.marker_data)

    def add_crosshairs(self, center_x, center_y, color=QColor(255, 255, 0), line_width=1):
        """Add crosshairs centered at the specified coordinates."""
        if not self.pixmap_item:
            return None
            
        # Remove existing crosshairs first
        self.remove_crosshairs()
        
        # Get the pixmap bounds
        pixmap_rect = self.pixmap_item.boundingRect()
        
        # Create horizontal line
        self.crosshair_horizontal = self.scene.addLine(
            pixmap_rect.left(), center_y,
            pixmap_rect.right(), center_y,
            QPen(color, line_width)
        )
        
        # Create vertical line  
        self.crosshair_vertical = self.scene.addLine(
            center_x, pixmap_rect.top(),
            center_x, pixmap_rect.bottom(),
            QPen(color, line_width)
        )
        
        # Set Z-value to ensure crosshairs appear in front of the image
        self.crosshair_horizontal.setZValue(10)  # Higher than image (default 0)
        self.crosshair_vertical.setZValue(10)
        
        return (self.crosshair_horizontal, self.crosshair_vertical)
    
    def update_crosshairs(self, center_x, center_y):
        """Update crosshair position without recreating them."""
        if not self.pixmap_item or not self.crosshair_horizontal or not self.crosshair_vertical:
            return
            
        # Get the pixmap bounds
        pixmap_rect = self.pixmap_item.boundingRect()
        
        # Update horizontal line position
        self.crosshair_horizontal.setLine(
            pixmap_rect.left(), center_y,
            pixmap_rect.right(), center_y
        )
        
        # Update vertical line position
        self.crosshair_vertical.setLine(
            center_x, pixmap_rect.top(),
            center_x, pixmap_rect.bottom()
        )
    
    def remove_crosshairs(self):
        """Remove all crosshair lines from the scene."""
        if self.crosshair_horizontal:
            self.scene.removeItem(self.crosshair_horizontal)
            self.crosshair_horizontal = None
            
        if self.crosshair_vertical:
            self.scene.removeItem(self.crosshair_vertical)
            self.crosshair_vertical = None
    
    def has_crosshairs(self):
        """Check if crosshairs are currently displayed."""
        return self.crosshair_horizontal is not None and self.crosshair_vertical is not None
