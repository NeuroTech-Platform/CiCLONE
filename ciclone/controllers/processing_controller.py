from typing import Optional, Callable, List, Dict, Any, Tuple

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from ciclone.models.application_model import ApplicationModel
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker
from ciclone.interfaces.view_interfaces import IMainView


class ProcessingController(QObject):
    """
    Controller for managing image processing operations and worker coordination.
    
    This controller handles the execution of medical image processing pipelines,
    coordinating between the UI, application model, and background worker processes.
    It manages stage selection, progress tracking, and graceful termination of
    long-running operations involving external tools like FSL and FreeSurfer.
    """
    
    def __init__(self, application_model: ApplicationModel):
        super().__init__()
        self.application_model = application_model
        self._view = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
        
        # Connect to application model signals for state synchronization
        self.application_model.worker_state_changed.connect(self._on_worker_state_changed)
        self.application_model.stages_selection_changed.connect(self._on_stages_selection_changed)
        
    def set_view(self, view: IMainView):
        """Set the view reference for UI updates."""
        self._view = view
        
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set callback function for logging messages."""
        self._log_callback = callback
        
    def _log_message(self, level: str, message: str):
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, message)
    
    def _on_worker_state_changed(self, is_running: bool, progress: int):
        """Handle worker state changes from application model."""
        if self._view and hasattr(self._view, 'update_processing_ui'):
            self._view.update_processing_ui(is_running, progress)
    
    def _on_stages_selection_changed(self, selected_stages: List[str]):
        """Handle stages selection changes from application model."""
        if self._view and hasattr(self._view, 'update_stages_selection_ui'):
            self._view.update_stages_selection_ui(selected_stages)
    
    # Processing Operations
    
    def run_all_stages(self, selected_subjects: List[str]) -> bool:
        """Run all configured stages for the selected subjects."""
        if self.application_model.is_worker_running():
            self._log_message("warning", "Processing is already in progress")
            return False
        
        if not selected_subjects:
            self._log_message("error", "No subjects selected for processing")
            return False
        
        output_directory = self.application_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        stages_config = self.application_model.get_stages_config()
        if not stages_config:
            self._log_message("error", "No stages configured")
            return False
        
        return self._start_processing(selected_subjects, stages_config, "run_all_stages")
    
    def run_selected_stages(self, selected_subjects: List[str]) -> bool:
        """Run only the selected stages for the selected subjects."""
        if self.application_model.is_worker_running():
            self._log_message("warning", "Processing is already in progress")
            return False
        
        if not selected_subjects:
            self._log_message("error", "No subjects selected for processing")
            return False
        
        output_directory = self.application_model.get_output_directory()
        if not output_directory:
            self._log_message("error", "Output directory not set")
            return False
        
        selected_stages_config = self.application_model.get_selected_stages_config()
        if not selected_stages_config:
            self._log_message("error", "No stages selected for processing")
            return False
        
        return self._start_processing(selected_subjects, selected_stages_config, "run_selected_stages")
    
    def _start_processing(self, subject_list: List[str], stages_config: List[Dict[str, Any]], operation_name: str) -> bool:
        """Start the image processing with the given parameters."""
        try:
            output_directory = self.application_model.get_output_directory()
            
            if self._view and hasattr(self._view, 'clear_processing_log'):
                self._view.clear_processing_log()
            
            self.application_model.update_worker_progress(0)
            
            stage_names = [stage.get("name", "Unknown") for stage in stages_config]
            self._log_message("info", f"{operation_name} => Starting processing {len(subject_list)} subjects with stages: {', '.join(stage_names)}")
            
            worker_config = self._build_worker_config(stages_config)
            worker = ImageProcessingWorker(output_directory, subject_list, worker_config)
            
            # Connect worker signals
            worker.update_progress_signal.connect(self._on_worker_progress_update)
            worker.log_signal.connect(self._on_worker_log_message)
            worker.finished.connect(self._on_worker_finished)
            
            self.application_model.set_worker_running(worker)
            worker.start()
            
            return True
            
        except Exception as e:
            self._log_message("error", f"Failed to start processing: {str(e)}")
            return False
    
    def _build_worker_config(self, stages_to_run: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build configuration for the worker containing only the necessary data."""
        base_config = self.application_model.get_config()
        
        worker_config = {
            'stages': stages_to_run,
        }
        
        for key in ['stage_outputs', 'settings', 'paths', 'defaults']:
            if key in base_config:
                worker_config[key] = base_config[key]
        
        return worker_config
    
    # Worker Event Handlers
    
    def _on_worker_progress_update(self, progress: int):
        """Handle progress updates from the worker."""
        self.application_model.update_worker_progress(progress)
    
    def _on_worker_log_message(self, level: str, message: str):
        """Handle log messages from the worker."""
        self._log_message(level, message)
    
    def _on_worker_finished(self):
        """Handle worker completion."""
        self._log_message("info", "Processing completed")
        
        worker = self.application_model.get_worker_instance()
        if worker:
            worker.deleteLater()
        
        self.application_model.set_worker_stopped()
    
    def stop_processing(self) -> bool:
        """
        Stop the current processing operation gracefully.
        
        This method terminates the worker thread and all associated subprocesses
        (FSL, FreeSurfer, ANTs tools) while ensuring proper cleanup and message ordering.
        Uses Qt's event processing to guarantee cleanup messages appear before success.
        
        Returns:
            bool: True if stop was successful, False otherwise
        """
        worker = self.application_model.get_worker_instance()
        if worker and self.application_model.is_worker_running():
            try:
                self._log_message("info", "Stopping processing operation...")
                
                # Terminate worker thread and wait for graceful shutdown
                worker.terminate()
                worker.wait(5000)  # Wait up to 5 seconds
                
                if worker.isRunning():
                    self._log_message("warning", "Graceful termination failed, forcing stop...")
                    worker.kill()
                    worker.wait(2000)  # Wait up to 2 more seconds for force kill
                
                # Process any remaining Qt events to ensure proper message ordering
                # This guarantees cleanup messages from subprocesses are handled before success
                QApplication.processEvents()
                
                # Declare success after all cleanup is complete
                self._log_message("success", "✅ Processing stopped successfully")
                self.application_model.set_worker_stopped()
                return True
                
            except Exception as e:
                self._log_message("error", f"Failed to stop processing: {str(e)}")
                return False
        else:
            self._log_message("warning", "No processing operation to stop")
            return False
    
    # Processing State Queries
    
    def is_processing_running(self) -> bool:
        """Check if processing is currently running."""
        return self.application_model.is_worker_running()
    
    def get_processing_progress(self) -> int:
        """Get current processing progress."""
        return self.application_model.get_worker_progress()
    
    # Stage Management
    
    def update_stage_selection_from_ui(self, stage_names: List[str]):
        """Update stage selection based on UI state."""
        self.application_model.set_selected_stages(stage_names)
    
    def toggle_stage_selection(self, stage_name: str):
        """Toggle a stage selection."""
        self.application_model.toggle_stage_selection(stage_name)
    
    def select_all_stages(self):
        """Select all available stages."""
        all_stages = self.application_model.get_stages_config()
        stage_names = [stage.get("name") for stage in all_stages if stage.get("name")]
        self.application_model.set_selected_stages(stage_names)
    
    def deselect_all_stages(self):
        """Deselect all stages."""
        self.application_model.set_selected_stages([])
    
    def get_available_stages(self) -> List[Dict[str, Any]]:
        """Get all available stages from configuration."""
        return self.application_model.get_stages_config()
    
    def get_selected_stages(self) -> List[str]:
        """Get currently selected stage names."""
        return self.application_model.get_selected_stages()
    
    def is_stage_selected(self, stage_name: str) -> bool:
        """Check if a specific stage is selected."""
        return stage_name in self.application_model.get_selected_stages()
    
    # Validation and Summary
    
    def validate_processing_prerequisites(self, selected_subjects: List[str]) -> Tuple[bool, str]:
        """Validate that all prerequisites for processing are met."""
        
        if not self.application_model.is_output_directory_set():
            return False, "Output directory not set or does not exist"
        
        if not selected_subjects:
            return False, "No subjects selected for processing"
        
        if not self.application_model.get_stages_config():
            return False, "No processing stages configured"
        
        if self.application_model.is_worker_running():
            return False, "Processing is already running"
        
        return True, ""
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Get a summary of current processing state."""
        return {
            'is_running': self.is_processing_running(),
            'progress': self.get_processing_progress(),
            'selected_stages': self.get_selected_stages(),
            'available_stages': len(self.get_available_stages()),
            'output_directory': self.application_model.get_output_directory()
        } 