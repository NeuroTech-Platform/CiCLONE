"""
Import worker for background image import operations.

This module provides the QThread worker that coordinates image import operations
(crop + optional registration) in a background process using multiprocessing.
"""

from typing import List, Dict, Any
from PyQt6.QtCore import pyqtSignal

from ciclone.workers.AbstractWorker import AbstractWorker
from ciclone.workers.ImportProcess import processImports


class ImportWorker(AbstractWorker):
    """
    QThread worker for executing image import operations in a separate process.

    This worker handles the complete import workflow (crop + optional registration)
    for medical images, coordinating between the UI and background FSL operations.
    Progress is tracked naturally across all operations (no artificial scaling needed).

    Signals:
        progress_signal: Emitted for progress updates (completed_ops, total_ops)
        log_signal: Emitted for log messages (level, message)
        job_complete_signal: Emitted when a job finishes (job_index, success, message)
        finished: Emitted when all operations complete (success_count, error_count)
        error_signal: Emitted on fatal error (error_message)
    """

    # Define signals (required by PyQt6)
    progress_signal = pyqtSignal(int, int)  # completed_operations, total_operations
    log_signal = pyqtSignal(str, str)  # level, message
    job_complete_signal = pyqtSignal(int, bool, str)  # job_index, success, message
    finished = pyqtSignal(int, int)  # success_count, error_count
    error_signal = pyqtSignal(str)  # error_message

    def __init__(self, import_jobs: List[Dict[str, Any]]):
        """
        Initialize the import worker.

        Args:
            import_jobs: List of import job dictionaries (serialized ImportJob objects)
        """
        super().__init__(import_jobs)

    def _get_process_function(self):
        """Get the target function for multiprocessing.Process."""
        return processImports

    def _get_process_args(self) -> tuple:
        """Get arguments to pass to the process function."""
        return (self.jobs,)

    def _get_progress_signal_params(self) -> int:
        """Get expected number of progress signal parameters."""
        return 2  # completed_operations, total_operations
