from typing import Optional, Callable, List, Dict, Any, Tuple
from PyQt6.QtCore import QObject

from ciclone.models.application_model import ApplicationModel
from ciclone.workers.ImageProcessingWorker import ImageProcessingWorker


class ProcessingController(QObject):
    """Controller for managing image processing operations and worker coordination."""
    
    def __init__(self, application_model: ApplicationModel):
        super().__init__()
        self.application_model = application_model
        self._view = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
        
        # Connect to application model signals
        self.application_model.worker_state_changed.connect(self._on_worker_state_changed)
        self.application_model.stages_selection_changed.connect(self._on_stages_selection_changed)
        
    def set_view(self, view):
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
    
    def run_all_stages(self, selected_subjects: List[str]) -> bool:
        """Run all configured stages for the selected subjects."""
        # Check if a process is already running
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
        
        # Get all stages from configuration
        stages_config = self.application_model.get_stages_config()
        if not stages_config:
            self._log_message("error", "No stages configured")
            return False
        
        return self._start_processing(selected_subjects, stages_config, "run_all_stages")
    
    def run_selected_stages(self, selected_subjects: List[str]) -> bool:
        """Run only the selected stages for the selected subjects."""
        # Check if a process is already running
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
        
        # Get selected stages configuration
        selected_stages_config = self.application_model.get_selected_stages_config()
        if not selected_stages_config:
            self._log_message("error", "No stages selected for processing")
            return False
        
        return self._start_processing(selected_subjects, selected_stages_config, "run_selected_stages")
    
    def _start_processing(self, subject_list: List[str], stages_config: List[Dict[str, Any]], operation_name: str) -> bool:
        """Start the image processing with the given parameters."""
        try:
            output_directory = self.application_model.get_output_directory()
            
            # Clear any previous progress and reset UI
            if self._view and hasattr(self._view, 'clear_processing_log'):
                self._view.clear_processing_log()
            
            self.application_model.update_worker_progress(0)
            
            # Log the start of processing
            stage_names = [stage.get("name", "Unknown") for stage in stages_config]
            self._log_message("info", f"{operation_name} => Starting processing {len(subject_list)} subjects with stages: {', '.join(stage_names)}")
            
            # Create worker
            worker = ImageProcessingWorker(output_directory, subject_list, stages_config)
            
            # Connect worker signals
            worker.update_progress_signal.connect(self._on_worker_progress_update)
            worker.log_signal.connect(self._on_worker_log_message)
            worker.finished.connect(self._on_worker_finished)
            
            # Update application state
            self.application_model.set_worker_running(worker)
            
            # Start the worker thread
            worker.start()
            
            return True
            
        except Exception as e:
            self._log_message("error", f"Failed to start processing: {str(e)}")
            return False
    
    def _on_worker_progress_update(self, progress: int):
        """Handle progress updates from the worker."""
        self.application_model.update_worker_progress(progress)
    
    def _on_worker_log_message(self, level: str, message: str):
        """Handle log messages from the worker."""
        self._log_message(level, message)
    
    def _on_worker_finished(self):
        """Handle worker completion."""
        self._log_message("info", "Processing completed")
        
        # Clean up worker state
        worker = self.application_model.get_worker_instance()
        if worker:
            worker.deleteLater()
        
        self.application_model.set_worker_stopped()
    
    def stop_processing(self) -> bool:
        """Stop the current processing operation."""
        worker = self.application_model.get_worker_instance()
        if worker and self.application_model.is_worker_running():
            try:
                print("[STOP] Attempting to stop processing gracefully...")
                
                # Attempt to terminate the worker gracefully
                worker.terminate()
                worker.wait(5000)  # Wait up to 5 seconds
                
                if worker.isRunning():
                    print("[STOP] Graceful termination failed, forcing kill...")
                    # Force kill if graceful termination failed
                    worker.kill()
                    worker.wait(2000)
                
                print("[STOP] Processing stopped successfully!")
                self._log_message("warning", "Processing stopped by user")
                self.application_model.set_worker_stopped()
                return True
                
            except Exception as e:
                print(f"[STOP] Failed to stop processing: {str(e)}")
                self._log_message("error", f"Failed to stop processing: {str(e)}")
                return False
        else:
            print("[STOP] No processing operation to stop")
            self._log_message("warning", "No processing operation to stop")
            return False
    
    def is_processing_running(self) -> bool:
        """Check if processing is currently running."""
        return self.application_model.is_worker_running()
    
    def get_processing_progress(self) -> int:
        """Get current processing progress."""
        return self.application_model.get_worker_progress()
    
    # Stage Selection Management
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
    
    # Utility Methods
    def validate_processing_prerequisites(self, selected_subjects: List[str]) -> Tuple[bool, str]:
        """Validate that all prerequisites for processing are met.
        Returns (is_valid, error_message)."""
        
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
            "is_running": self.application_model.is_worker_running(),
            "progress": self.application_model.get_worker_progress(),
            "available_stages_count": len(self.application_model.get_stages_config()),
            "selected_stages_count": len(self.application_model.get_selected_stages()),
            "selected_stages": self.application_model.get_selected_stages(),
            "output_directory_set": self.application_model.is_output_directory_set(),
            "output_directory": self.application_model.get_output_directory()
        } 