import multiprocessing as mp

from PyQt6.QtCore import pyqtSignal, QThread

from .ImageProcessingProcess import processImagesAnalysis

class ImageProcessingWorker(QThread):
    update_progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str, str)  # level, message
    finished = pyqtSignal()

    def __init__(self, output_directory: str, subject_list: list, config_data: dict):
        super().__init__()
        self.output_directory = output_directory
        self.subject_list = subject_list
        self.config_data = config_data
        self.process = None
        self.parent_conn = None

    def run(self):
        self.parent_conn, child_conn = mp.Pipe()
        self.process = mp.Process(target=processImagesAnalysis, args=(child_conn, self.output_directory, self.subject_list, self.config_data))
        self.process.start()

        while True:
            msg = self.parent_conn.recv()  # Wait for message
            
            if msg["type"] == "progress":
                progress_value = msg["value"]
                if progress_value < 0:  # Error occurred
                    self.log_signal.emit("error", "Error in processing files")
                    break
                elif progress_value == 100:  # Processing completed
                    self.update_progress_signal.emit(100)
                    break
                else:
                    self.update_progress_signal.emit(progress_value)
            elif msg["type"] == "log":
                level = msg["level"]
                message = msg["message"]
                self.log_signal.emit(level, message)
                print(f"[{level.upper()}] {message}")
                
        if self.process and self.process.is_alive():
            self.process.join()  # Ensure the process has completed
        self.finished.emit()
    
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
            self.log_signal.emit("info", "Stopping all processes (FSL, FreeSurfer, etc.)...")
            
            # Terminate the main process - this should kill all child processes too
            self.process.terminate()
            self.process.join(timeout=5)  # Wait up to 5 seconds for graceful termination
            
            if self.process.is_alive():
                self.log_signal.emit("warning", "Force killing all processes...")
                self.process.kill()
                self.process.join()
            
            self.log_signal.emit("info", "All processes stopped.")
