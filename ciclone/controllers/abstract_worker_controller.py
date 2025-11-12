"""
Abstract base controller for background worker management.

This module provides a base class for controllers that manage background workers
(crop, registration, pipeline processing, etc.). It extracts common patterns for
worker lifecycle management, progress tracking, and UI coordination.
"""

from typing import Optional, Callable, List, Dict, Any

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from ciclone.models.application_model import ApplicationModel
from ciclone.interfaces.view_interfaces import IMainView


class AbstractWorkerController(QObject):
    """
    Abstract base controller for managing background worker operations.

    This controller provides common functionality for managing background workers
    that perform long-running operations (crop, registration, pipeline processing).
    It handles worker lifecycle, progress tracking, logging, and UI coordination.

    Subclasses must implement:
    - _get_operation_name(): Return human-readable operation name
    - _create_worker_instance(): Create and configure the worker instance
    - _get_job_display_names(): Get display names for jobs being processed
    """

    def __init__(self, application_model: ApplicationModel):
        """
        Initialize the worker controller.

        Args:
            application_model: Shared application model for state management
        """
        super().__init__()
        self.application_model = application_model
        self._view: Optional[IMainView] = None
        self._log_callback: Optional[Callable[[str, str], None]] = None
        self._completion_callback: Optional[Callable[[int, int], None]] = None

        # Connect to application model signals for state synchronization
        self.application_model.worker_state_changed.connect(self._on_worker_state_changed)

    # Methods that MUST be implemented by subclasses
    # (Cannot use @abstractmethod due to PyQt metaclass conflicts)

    def _get_operation_name(self) -> str:
        """
        Get the human-readable operation name (e.g., "cropping", "registration").

        MUST be implemented by subclasses.

        Returns:
            str: Operation name for logging and UI messages

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement _get_operation_name()")

    def _create_worker_instance(self, jobs: List[Any]) -> QObject:
        """
        Create and configure the worker instance for the given jobs.

        MUST be implemented by subclasses.

        Args:
            jobs: List of job objects (CropJob, RegistrationJob, etc.)

        Returns:
            QObject: Configured worker instance (must be a QThread)

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement _create_worker_instance()")

    def _get_job_display_names(self, jobs: List[Any]) -> List[str]:
        """
        Get human-readable display names for the jobs.

        MUST be implemented by subclasses.

        Args:
            jobs: List of job objects

        Returns:
            List[str]: Display names for logging

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement _get_job_display_names()")

    # View and Logging Setup

    def set_view(self, view: IMainView):
        """Set the view reference for UI updates."""
        self._view = view

    def set_log_callback(self, callback: Callable[[str, str], None]):
        """Set callback function for logging messages."""
        self._log_callback = callback

    def set_completion_callback(self, callback: Callable[[int, int], None]):
        """
        Set callback function to be called when operations complete.

        Args:
            callback: Function taking (success_count, error_count) as arguments
        """
        self._completion_callback = callback

    def _log_message(self, level: str, message: str):
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, message)

    def _on_worker_state_changed(self, is_running: bool, progress: int):
        """Handle worker state changes from application model."""
        if self._view and hasattr(self._view, 'update_processing_ui'):
            self._view.update_processing_ui(is_running, progress)

    # Worker Lifecycle Management

    def run_jobs(self, jobs: List[Any]) -> bool:
        """
        Execute a list of jobs.

        This method starts the worker in the background, which will process each
        job sequentially. The worker shares the same slot as other operations,
        ensuring mutual exclusion.

        Args:
            jobs: List of job objects to process

        Returns:
            bool: True if operation started successfully, False otherwise
        """
        operation_name = self._get_operation_name()

        # Check for mutual exclusion with other operations
        if self.application_model.is_worker_running():
            self._log_message("warning", f"Cannot start {operation_name}: another operation is already in progress")
            return False

        if not jobs:
            self._log_message("error", "No jobs to process")
            return False

        # Validate all jobs before starting (if jobs have validate method)
        for job in jobs:
            if hasattr(job, 'validate'):
                is_valid, error_msg = job.validate()
                if not is_valid:
                    self._log_message("error", f"Invalid {operation_name} job: {error_msg}")
                    return False

        return self._start_worker(jobs)

    def _start_worker(self, jobs: List[Any]) -> bool:
        """Start the worker with the given jobs."""
        try:
            # Reset progress at start of new operation
            self.application_model.update_worker_progress(0)

            # Log start message
            operation_name = self._get_operation_name()
            job_count = len(jobs)
            self._log_message("info", f"Starting {operation_name} of {job_count} item(s)")

            # Log job details
            display_names = self._get_job_display_names(jobs)
            for name in display_names:
                self._log_message("info", f"  • {name}")

            # Create and configure worker (set self as parent to manage lifecycle)
            worker = self._create_worker_instance(jobs)
            worker.setParent(self)  # Set parent to prevent premature garbage collection

            # Connect worker signals (standard signal names expected)
            worker.progress_signal.connect(self._on_worker_progress_update)
            worker.log_signal.connect(self._on_worker_log_message)
            worker.job_complete_signal.connect(self._on_job_complete)
            worker.finished.connect(self._on_worker_finished)
            worker.error_signal.connect(self._on_worker_error)

            # Register with application model (shares slot with other operations)
            self.application_model.set_worker_running(worker)

            worker.start()

            # Process Qt events to ensure the worker thread is fully started
            QApplication.processEvents()

            return True

        except Exception as e:
            operation_name = self._get_operation_name()
            self._log_message("error", f"Failed to start {operation_name}: {str(e)}")
            import traceback
            self._log_message("error", traceback.format_exc())
            return False

    # Worker Event Handlers

    def _on_worker_progress_update(self, *args):
        """
        Handle progress updates from the worker.

        Args can be (completed_operations, total_operations) or other formats
        depending on the worker implementation.
        """
        # Extract completed and total from args (first two parameters)
        completed = args[0]
        total = args[1]

        # Calculate natural percentage based on operation progress
        progress = int((completed / total) * 100)

        self.application_model.update_worker_progress(progress)

    def _on_worker_log_message(self, level: str, message: str):
        """Handle log messages from the worker."""
        self._log_message(level, message)

    def _on_job_complete(self, job_index: int, success: bool, message: str):
        """Handle individual job completion."""
        if success:
            self._log_message("success", f"Job {job_index} completed: {message}")
        else:
            self._log_message("error", f"Job {job_index} failed: {message}")

    def _on_worker_finished(self, success_count: int, error_count: int):
        """Handle worker completion."""
        total = success_count + error_count
        operation_name = self._get_operation_name()

        if error_count == 0:
            self._log_message("success", f"✅ All {total} {operation_name} operation(s) completed successfully")
        elif success_count == 0:
            self._log_message("error", f"❌ All {total} {operation_name} operation(s) failed")
        else:
            self._log_message("warning", f"⚠️  {operation_name.capitalize()} completed with mixed results: {success_count} succeeded, {error_count} failed")

        # Clean up worker
        worker = self.application_model.get_worker_instance()
        if worker:
            worker.deleteLater()

        # Mark worker as stopped and reset progress
        self.application_model.set_worker_stopped()

        # Call completion callback if set, then clear it to avoid stale callbacks
        if self._completion_callback:
            callback = self._completion_callback
            self._completion_callback = None  # Clear before calling to prevent re-use
            callback(success_count, error_count)

    def _on_worker_error(self, error_message: str):
        """Handle fatal worker errors."""
        operation_name = self._get_operation_name()
        self._log_message("error", f"{operation_name.capitalize()} worker error: {error_message}")
        
        # Clear completion callback on error to avoid stale callbacks
        self._completion_callback = None

    def stop_operation(self) -> bool:
        """
        Stop the current operation gracefully.

        This method terminates the worker thread and all associated subprocesses
        while ensuring proper cleanup and message ordering. Uses Qt's event
        processing to guarantee cleanup messages appear correctly.

        Returns:
            bool: True if stop was successful, False otherwise
        """
        worker = self.application_model.get_worker_instance()
        if worker and self.application_model.is_worker_running():
            try:
                operation_name = self._get_operation_name()
                self._log_message("info", f"Stopping {operation_name} operation...")

                # Terminate worker thread and wait for graceful shutdown
                worker.terminate()
                worker.wait(5000)  # Wait up to 5 seconds

                if worker.isRunning():
                    self._log_message("warning", "Graceful termination failed, forcing stop...")
                    worker.kill()
                    worker.wait(2000)  # Wait up to 2 more seconds for force kill

                # Process any remaining Qt events to ensure proper message ordering
                QApplication.processEvents()

                # Declare success after all cleanup is complete
                self._log_message("success", f"✅ {operation_name.capitalize()} stopped successfully")
                self.application_model.set_worker_stopped()
                
                # Clear completion callback when operation is manually stopped
                self._completion_callback = None
                
                return True

            except Exception as e:
                operation_name = self._get_operation_name()
                self._log_message("error", f"Failed to stop {operation_name}: {str(e)}")
                # Clear callback even on stop failure to prevent stale state
                self._completion_callback = None
                return False
        else:
            operation_name = self._get_operation_name()
            self._log_message("warning", f"No {operation_name} operation to stop")
            return False

    # State Queries

    def is_operation_running(self) -> bool:
        """Check if operation is currently running."""
        return self.application_model.is_worker_running()

    def get_operation_progress(self) -> int:
        """Get current operation progress."""
        return self.application_model.get_worker_progress()

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get a summary of current operation state."""
        operation_name = self._get_operation_name()
        return {
            'operation_name': operation_name,
            'is_running': self.is_operation_running(),
            'progress': self.get_operation_progress()
        }
