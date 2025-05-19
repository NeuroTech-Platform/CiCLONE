import os
import shutil

from ciclone.core.stages import run_stage
from ciclone.core.subject import Subject

def processImagesAnalysis(conn, output_directory: str, subject_list: list, stages: list):
    # Check if output directory exists
    if not os.path.exists(output_directory):
        conn.send({"type": "log", "level": "error", "message": f"Output directory {output_directory} does not exist."})
        conn.send({"type": "progress", "value": -1})  # Indicate error
        return
    
    total_steps = len(subject_list) * len(stages)
    completed_steps = 0
    
    for subject_name in subject_list:
        subject_folder = os.path.join(output_directory, subject_name)
        if not os.path.exists(subject_folder):
            conn.send({"type": "log", "level": "error", "message": f"Subject {subject_name} does not exist."})
            conn.send({"type": "progress", "value": -1})  # Indicate error
            return

        conn.send({"type": "log", "level": "info", "message": f"Processing subject {subject_name}..."})
        subject = Subject(subject_folder)
        subject.clear_processed_tmp()
        
        for stage in stages:
            conn.send({"type": "log", "level": "info", "message": f"Running stage {stage['name']} for subject {subject_name}..."})
            run_stage(stage, subject)
            completed_steps += 1
            progress_percent = int((completed_steps / total_steps) * 100)
            
            conn.send({"type": "log", "level": "success", "message": f"{subject_name}: Finished running stage {stage['name']}"})
            conn.send({"type": "progress", "value": progress_percent})

    # Send completion signal
    conn.send({"type": "log", "level": "success", "message": "All processing completed successfully."})
    conn.send({"type": "progress", "value": 100})  # Indicate success