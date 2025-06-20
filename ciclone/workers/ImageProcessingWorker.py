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

    def run(self):
        parent_conn, child_conn = mp.Pipe()
        process = mp.Process(target=processImagesAnalysis, args=(child_conn, self.output_directory, self.subject_list, self.config_data))
        process.start()

        while True:
            msg = parent_conn.recv()  # Wait for message
            
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
                
        process.join()  # Ensure the process has completed
        self.finished.emit()
