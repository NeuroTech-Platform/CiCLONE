"""
Factory for creating parameter input widgets based on type information.
Unified system where files are just Path-typed parameters.
"""
from typing import Any, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QCheckBox, QHBoxLayout, QFrame, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal


class ParameterWidget(QFrame):
    """Base class for parameter input widgets."""
    
    valueChanged = pyqtSignal(str, object)  # parameter_name, value
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.param_name = param_name
        self.param_info = param_info
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setContentsMargins(0, 0, 0, 0)
        
    def get_value(self) -> Any:
        """Get the current value of the parameter."""
        raise NotImplementedError
        
    def set_value(self, value: Any) -> None:
        """Set the value of the parameter."""
        raise NotImplementedError
    
    def cleanup(self) -> None:
        """Clean up resources when widget is being destroyed."""
        # Default implementation - subclasses can override for specific cleanup
        pass


class PathParameterWidget(ParameterWidget):
    """Widget for Path/file parameters with optional file browser."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        display_name = param_info.get('display_name', param_name)
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        label.setToolTip(param_info.get('description', ''))
        
        # Create line edit for path
        self.line_edit = QLineEdit()
        placeholder = param_info.get('description', f"Enter {display_name}")
        self.line_edit.setPlaceholderText(placeholder)
        
        # Set default value
        default_value = param_info.get('default', '')
        if default_value:
            self.line_edit.setText(str(default_value))
        
        # Connect signal - use editingFinished to avoid prompting on every keystroke
        # Use a safe signal connection that checks if the widget still exists
        self.line_edit.editingFinished.connect(self._on_text_changed)
        
        layout.addWidget(label)
        layout.addWidget(self.line_edit)
        
        self.setLayout(layout)
    
    def _on_text_changed(self):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'line_edit') and self.line_edit is not None:
                self.valueChanged.emit(self.param_name, self.line_edit.text())
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> str:
        return self.line_edit.text()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            self.line_edit.setText(str(value))


class FloatParameterWidget(ParameterWidget):
    """Widget for float parameters using QDoubleSpinBox."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        display_name = param_info.get('display_name', param_name)
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        label.setToolTip(param_info.get('description', ''))
        
        # Create spin box
        self.spin_box = QDoubleSpinBox()
        
        # Set range based on parameter constraints
        if 'min' in param_info:
            self.spin_box.setMinimum(param_info['min'])
        else:
            self.spin_box.setMinimum(-999999.0)
            
        if 'max' in param_info:
            self.spin_box.setMaximum(param_info['max'])
        else:
            self.spin_box.setMaximum(999999.0)
        
        self.spin_box.setSingleStep(param_info.get('step', 0.01))
        self.spin_box.setDecimals(param_info.get('decimals', 2))
        
        # Set default value
        default_value = param_info.get('default', 0.0)
        if default_value is not None:
            self.spin_box.setValue(float(default_value))
        
        # Connect signal with safe handler
        self.spin_box.valueChanged.connect(self._on_value_changed)
        
        layout.addWidget(label)
        layout.addWidget(self.spin_box)
        self.setLayout(layout)
    
    def _on_value_changed(self, value):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'spin_box') and self.spin_box is not None:
                self.valueChanged.emit(self.param_name, value)
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> float:
        return self.spin_box.value()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            self.spin_box.setValue(float(value))


class IntParameterWidget(ParameterWidget):
    """Widget for integer parameters using QSpinBox."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        display_name = param_info.get('display_name', param_name)
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        label.setToolTip(param_info.get('description', ''))
        
        # Create spin box
        self.spin_box = QSpinBox()
        self.spin_box.setMinimum(param_info.get('min', -999999))
        self.spin_box.setMaximum(param_info.get('max', 999999))
        self.spin_box.setSingleStep(param_info.get('step', 1))
        
        # Set default value
        default_value = param_info.get('default', 0)
        if default_value is not None:
            self.spin_box.setValue(int(default_value))
        
        # Connect signal with safe handler
        self.spin_box.valueChanged.connect(self._on_value_changed)
        
        layout.addWidget(label)
        layout.addWidget(self.spin_box)
        self.setLayout(layout)
    
    def _on_value_changed(self, value):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'spin_box') and self.spin_box is not None:
                self.valueChanged.emit(self.param_name, value)
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> int:
        return self.spin_box.value()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            self.spin_box.setValue(int(value))


class BoolParameterWidget(ParameterWidget):
    """Widget for boolean parameters using QCheckBox."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create checkbox with label
        display_name = param_info.get('display_name', param_name)
        self.checkbox = QCheckBox(display_name)
        self.checkbox.setToolTip(param_info.get('description', ''))
        
        # Set default value
        default_value = param_info.get('default', False)
        if default_value is not None:
            self.checkbox.setChecked(bool(default_value))
        
        # Connect signal with safe handler
        self.checkbox.toggled.connect(self._on_toggled)
        
        layout.addWidget(self.checkbox)
        layout.addStretch()
        self.setLayout(layout)
    
    def _on_toggled(self, checked):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'checkbox') and self.checkbox is not None:
                self.valueChanged.emit(self.param_name, checked)
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> bool:
        return self.checkbox.isChecked()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            self.checkbox.setChecked(bool(value))


class StringParameterWidget(ParameterWidget):
    """Widget for string parameters using QLineEdit."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        display_name = param_info.get('display_name', param_name)
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        label.setToolTip(param_info.get('description', ''))
        
        # Create line edit
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(param_info.get('placeholder', ''))
        
        # Set default value
        default_value = param_info.get('default', '')
        if default_value is not None:
            self.line_edit.setText(str(default_value))
        
        # Connect signal - use editingFinished to avoid prompting on every keystroke
        # Use a safe signal connection that checks if the widget still exists
        self.line_edit.editingFinished.connect(self._on_text_changed)
        
        layout.addWidget(label)
        layout.addWidget(self.line_edit)
        self.setLayout(layout)
    
    def _on_text_changed(self):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'line_edit') and self.line_edit is not None:
                self.valueChanged.emit(self.param_name, self.line_edit.text())
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> str:
        return self.line_edit.text()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            self.line_edit.setText(str(value))


class ChoiceParameterWidget(ParameterWidget):
    """Widget for choice parameters using QComboBox."""
    
    def __init__(self, param_name: str, param_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(param_name, param_info, parent)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create label
        display_name = param_info.get('display_name', param_name)
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        label.setToolTip(param_info.get('description', ''))
        
        # Create combo box
        self.combo_box = QComboBox()
        choices = param_info.get('choices', [])
        self.combo_box.addItems([str(c) for c in choices])
        
        # Set default value
        default_value = param_info.get('default')
        if default_value is not None and str(default_value) in [str(c) for c in choices]:
            self.combo_box.setCurrentText(str(default_value))
        
        # Connect signal with safe handler
        self.combo_box.currentTextChanged.connect(self._on_text_changed)
        
        layout.addWidget(label)
        layout.addWidget(self.combo_box)
        self.setLayout(layout)
    
    def _on_text_changed(self, text):
        """Safe signal handler that checks if widget still exists."""
        try:
            if hasattr(self, 'combo_box') and self.combo_box is not None:
                self.valueChanged.emit(self.param_name, text)
        except RuntimeError:
            # Widget has been deleted, ignore the signal
            pass
    
    def get_value(self) -> str:
        return self.combo_box.currentText()
    
    def set_value(self, value: Any) -> None:
        if value is not None:
            index = self.combo_box.findText(str(value))
            if index >= 0:
                self.combo_box.setCurrentIndex(index)


class ParameterWidgetFactory:
    """Factory for creating parameter input widgets based on type information."""
    
    @staticmethod
    def create_widget(param_name: str, param_info: Dict[str, Any], 
                     parent: Optional[QWidget] = None) -> Optional[ParameterWidget]:
        """
        Create appropriate widget based on parameter type and metadata.
        
        Args:
            param_name: Name of the parameter
            param_info: Dictionary containing parameter metadata including:
                - type: Parameter type (str, int, float, bool, Path, etc.)
                - description: Description of the parameter
                - default: Default value
                - choices: List of valid choices (for choice parameters)
                - min/max: Minimum and maximum values (for numeric parameters)
                - step: Step size (for numeric parameters)
                - decimals: Number of decimal places (for float parameters)
                - display_name: Human-readable name for display
                - is_file: Whether this is a file parameter (for Path types)
            parent: Parent widget
            
        Returns:
            ParameterWidget instance or None if type not supported
        """
        param_type = param_info.get('type', 'str').lower()
        
        # Handle choice parameters
        if 'choices' in param_info and param_info['choices']:
            return ChoiceParameterWidget(param_name, param_info, parent)
        
        # Handle Path and file parameters
        if 'path' in param_type or param_info.get('is_file', False):
            return PathParameterWidget(param_name, param_info, parent)
        
        # Create widget based on type
        if param_type in ['float', 'double']:
            # Special handling for fractional_intensity (0-1 range)
            if 'fractional' in param_name.lower() or 'intensity' in param_name.lower():
                param_info['min'] = param_info.get('min', 0.0)
                param_info['max'] = param_info.get('max', 1.0)
                param_info['step'] = param_info.get('step', 0.05)
                param_info['decimals'] = param_info.get('decimals', 2)
            return FloatParameterWidget(param_name, param_info, parent)
        elif param_type in ['int', 'integer']:
            return IntParameterWidget(param_name, param_info, parent)
        elif param_type in ['bool', 'boolean']:
            return BoolParameterWidget(param_name, param_info, parent)
        elif param_type in ['str', 'string', 'any']:
            return StringParameterWidget(param_name, param_info, parent)
        else:
            # Default to string widget for unknown types
            print(f"Warning: Unknown parameter type '{param_type}' for '{param_name}', using string widget")
            return StringParameterWidget(param_name, param_info, parent)
    
    @staticmethod
    def create_widgets_from_metadata(parameters: Dict[str, Dict[str, Any]], 
                                    parent: Optional[QWidget] = None) -> Dict[str, ParameterWidget]:
        """
        Create multiple parameter widgets from metadata dictionary.
        
        Args:
            parameters: Dictionary mapping parameter names to their metadata
            parent: Parent widget
            
        Returns:
            Dictionary mapping parameter names to their widgets
        """
        widgets = {}
        for param_name, param_info in parameters.items():
            widget = ParameterWidgetFactory.create_widget(param_name, param_info, parent)
            if widget:
                widgets[param_name] = widget
        return widgets