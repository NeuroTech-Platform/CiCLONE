"""
Controller for managing image import operations.

This controller handles the execution of image import workflow (FSL robustfov crop
+ optional FSL FLIRT registration), coordinating between the UI, application model,
and background worker processes. It shares the same worker slot as ProcessingController
to ensure mutual exclusion.
"""

from typing import List

from ciclone.models.application_model import ApplicationModel
from ciclone.models.import_job import ImportJob
from ciclone.workers.ImportWorker import ImportWorker
from ciclone.controllers.abstract_worker_controller import AbstractWorkerController


class ImportController(AbstractWorkerController):
    """
    Controller for managing image import operations and worker coordination.

    This controller handles the complete import workflow (crop + optional registration)
    for medical images, coordinating between the UI, application model, and background
    worker processes. It ensures mutual exclusion with pipeline processing by sharing
    the same worker slot in ApplicationModel.

    Inherits common worker management functionality from AbstractWorkerController.
    """

    def __init__(self, application_model: ApplicationModel):
        """
        Initialize the import controller.

        Args:
            application_model: Shared application model for state management
        """
        super().__init__(application_model)

    # Abstract method implementations

    def _get_operation_name(self) -> str:
        """Get the human-readable operation name."""
        return "import"

    def _create_worker_instance(self, jobs: List[ImportJob]) -> ImportWorker:
        """Create and configure the import worker instance."""
        # Convert jobs to dictionaries for multiprocessing
        job_dicts = [job.to_dict() for job in jobs]
        return ImportWorker(job_dicts)

    def _get_job_display_names(self, jobs: List[ImportJob]) -> List[str]:
        """Get human-readable display names for import jobs."""
        return [job.get_display_name() for job in jobs]

    # Public API (convenience methods that delegate to base class)

    def run_imports(self, import_jobs: List[ImportJob]) -> bool:
        """
        Execute a list of import jobs.

        This method starts the import worker in the background, which will
        process each job sequentially (crop + optional registration). The worker
        shares the same slot as pipeline processing, ensuring mutual exclusion.

        Args:
            import_jobs: List of ImportJob objects to process

        Returns:
            bool: True if import started successfully, False otherwise
        """
        return self.run_jobs(import_jobs)

    def stop_import(self) -> bool:
        """
        Stop the current import operation gracefully.

        This method terminates the worker thread and all associated subprocesses
        (FSL robustfov and FLIRT tools) while ensuring proper cleanup and message
        ordering. Uses Qt's event processing to guarantee cleanup messages appear
        correctly.

        Returns:
            bool: True if stop was successful, False otherwise
        """
        return self.stop_operation()

    def is_import_running(self) -> bool:
        """Check if import is currently running."""
        return self.is_operation_running()

    def get_import_progress(self) -> int:
        """Get current import progress."""
        return self.get_operation_progress()
