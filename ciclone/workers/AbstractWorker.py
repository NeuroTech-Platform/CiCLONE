"""
Abstract base worker thread for background processing operations.

This module provides a base class for QThread workers that spawn separate processes
to perform long-running operations (crop, registration, pipeline processing).
It extracts common patterns for multiprocessing communication, message processing,
and process lifecycle management.
"""

import multiprocessing as mp
from typing import List, Dict, Any, Callable

from PyQt6.QtCore import QThread


class AbstractWorker(QThread):
    """
    Abstract base QThread worker for executing operations in a separate process.

    This worker provides common infrastructure for spawning multiprocessing.Process
    that performs operations sequentially. Progress updates and logs are communicated
    back via pipe connection.

    Subclasses must implement:
    - _get_process_function(): Return the target function for multiprocessing.Process
    - _get_process_args(): Return arguments to pass to the process function
    - _get_progress_signal_params(): Return expected number of progress signal parameters

    Standard Signals (defined in subclass):
        progress_signal: Emitted for progress updates (2-3 params depending on operation)
        log_signal: Emitted for log messages (level, message)
        job_complete_signal: Emitted when a job finishes (job_index, success, message)
        finished: Emitted when all operations complete (success_count, error_count)
        error_signal: Emitted on fatal error (error_message)
    """

    # Note: Signals must be defined in concrete subclasses due to PyQt6 metaclass requirements
    # progress_signal = pyqtSignal(...)  # Define in subclass with appropriate params
    # log_signal = pyqtSignal(str, str)
    # job_complete_signal = pyqtSignal(int, bool, str)
    # finished = pyqtSignal(int, int)
    # error_signal = pyqtSignal(str)

    def __init__(self, jobs: List[Dict[str, Any]]):
        """
        Initialize the worker.

        Args:
            jobs: List of job dictionaries (serialized job objects)
        """
        super().__init__()
        self.jobs = jobs
        self.process = None
        self.parent_conn = None

    # Methods that MUST be implemented by subclasses
    # (Cannot use @abstractmethod due to PyQt metaclass conflicts)

    def _get_process_function(self) -> Callable:
        """
        Get the target function for multiprocessing.Process.

        MUST be implemented by subclasses.

        Returns:
            Callable: Function to execute in separate process (e.g., processCrops, processRegistrations)

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement _get_process_function()")

    def _get_process_args(self) -> tuple:
        """
        Get arguments to pass to the process function.

        MUST be implemented by subclasses.

        Returns:
            tuple: Arguments for process function (typically (child_conn, *other_args))

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement _get_process_args()")

    def _get_progress_signal_params(self) -> int:
        """
        Get expected number of progress signal parameters.

        Returns:
            int: Number of parameters (2 for crop: job_index, total_jobs;
                                       3 for registration: job_index, total_jobs, message)
        """
        return 2  # Default to 2 parameters

    # Main Worker Thread Execution

    def run(self):
        """
        Main worker thread execution.

        Spawns a separate process to perform operations and processes messages
        from the pipe connection until completion.
        """
        try:
            self.parent_conn, child_conn = mp.Pipe()
            process_func = self._get_process_function()
            process_args = self._get_process_args()

            self.process = mp.Process(
                target=process_func,
                args=(child_conn,) + process_args  # child_conn is always first argument
            )
            self.process.start()
        except Exception as e:
            error_msg = f"Failed to start process: {str(e)}"
            self.error_signal.emit(error_msg)
            self.log_signal.emit('error', error_msg)
            self.finished.emit(0, len(self.jobs))
            return

        try:
            while True:
                # Poll with timeout to avoid hanging indefinitely
                if self.parent_conn.poll(timeout=1.0):  # Wait 1 second for message
                    msg = self.parent_conn.recv()

                    # Handle different message types
                    if isinstance(msg, tuple):
                        msg_type = msg[0]

                        if msg_type == 'progress':
                            # ('progress', job_index, total_jobs) or ('progress', job_index, total_jobs, message)
                            self._handle_progress_message(msg)

                        elif msg_type == 'log':
                            # ('log', level, message)
                            _, level, message = msg
                            self.log_signal.emit(level, message)

                        elif msg_type == 'job_complete':
                            # ('job_complete', job_index, success, message)
                            _, job_index, success, message = msg
                            self.job_complete_signal.emit(job_index, success, message)

                        elif msg_type == 'complete':
                            # ('complete', success_count, error_count)
                            _, success_count, error_count = msg
                            # Store counts to emit after cleanup
                            self._success_count = success_count
                            self._error_count = error_count
                            break

                        elif msg_type == 'error':
                            # ('error', error_message)
                            _, error_message = msg
                            self.error_signal.emit(error_message)
                            self.log_signal.emit('error', error_message)
                            # Store error state to emit after cleanup
                            self._success_count = 0
                            self._error_count = len(self.jobs)
                            break

                else:
                    # Check if process is still alive when no message received
                    if not self.process.is_alive():
                        # Process died unexpectedly
                        error_msg = "Process terminated unexpectedly"
                        self.error_signal.emit(error_msg)
                        self.log_signal.emit('error', error_msg)
                        # Store error state to emit after cleanup
                        self._success_count = 0
                        self._error_count = len(self.jobs)
                        break

        except Exception as e:
            # Catch any unexpected errors in the message processing loop
            error_msg = f"Unexpected error in worker: {str(e)}"
            self.error_signal.emit(error_msg)
            self.log_signal.emit('error', error_msg)
            # Store error state to emit after cleanup
            self._success_count = 0
            self._error_count = len(self.jobs)

        finally:
            # Clean up connections and process
            if self.parent_conn:
                self.parent_conn.close()
            if self.process and self.process.is_alive():
                self.process.join(timeout=5)  # Wait up to 5 seconds
                if self.process.is_alive():
                    self.process.terminate()

        # Emit finished signal AFTER all cleanup is done, just before run() returns
        # This prevents premature deletion and ensures proper cleanup
        if hasattr(self, '_success_count'):
            self.finished.emit(self._success_count, self._error_count)
        else:
            # Fallback if we didn't set counts (shouldn't happen but be safe)
            self.finished.emit(0, len(self.jobs))

    def _handle_progress_message(self, msg: tuple):
        """
        Handle progress message and emit appropriate signal.

        Args:
            msg: Progress message tuple from process
        """
        # Handle different progress signal parameter counts
        param_count = self._get_progress_signal_params()

        if param_count == 2:
            # ('progress', job_index, total_jobs)
            _, job_index, total_jobs = msg
            self.progress_signal.emit(job_index, total_jobs)
        elif param_count == 3:
            # ('progress', job_index, total_jobs, message)
            _, job_index, total_jobs, message = msg
            self.progress_signal.emit(job_index, total_jobs, message)
        else:
            # Fallback: just emit what we have
            self.progress_signal.emit(*msg[1:])

    # Process Termination

    def terminate(self):
        """Override QThread.terminate() to also stop subprocesses."""
        self._terminate_all_processes()
        super().terminate()

    def kill(self):
        """Override QThread.kill() to also stop subprocesses."""
        self._terminate_all_processes()
        super().kill()

    def stop_processing(self):
        """Stop the processing and terminate all subprocesses."""
        self._terminate_all_processes()

    def _terminate_all_processes(self):
        """Terminate the main process and all its subprocesses."""
        if self.process and self.process.is_alive():
            # Terminate the main process - this should kill all child processes too
            self.process.terminate()
            self.process.join(timeout=5)  # Wait up to 5 seconds for graceful termination

            if self.process.is_alive():
                self.process.kill()
                self.process.join()
