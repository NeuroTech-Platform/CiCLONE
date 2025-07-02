import os
import shutil
import signal
import multiprocessing

from ciclone.services.processing.stages import run_stage, run_stage_with_validation
from ciclone.domain.subject import Subject
from ciclone.utils.utility import clean_before_stage

def processImagesAnalysis(conn, output_directory: str, subject_list: list, config_data: dict):
    # Track cleanup state to prevent multiple cleanup messages
    cleanup_started = False
    
    # Set up signal handler for clean termination
    def signal_handler(signum, frame):
        nonlocal cleanup_started
        if not cleanup_started:
            cleanup_started = True
            print(f"[DEBUG] Signal {signum} received, starting cleanup...")
            conn.send({"type": "log", "level": "info", "message": "Processing interrupted, cleaning up..."})
            # Kill all child processes in this process group
            try:
                os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)
                print("[DEBUG] Sent SIGTERM to process group")
            except Exception as e:
                print(f"[DEBUG] Failed to kill process group: {e}")
        else:
            print(f"[DEBUG] Signal {signum} received, but cleanup already started")
        exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set this process as a process group leader
    try:
        os.setpgrp()
    except:
        pass
    
    # Check if output directory exists
    if not os.path.exists(output_directory):
        conn.send({"type": "log", "level": "error", "message": f"Output directory {output_directory} does not exist."})
        conn.send({"type": "progress", "value": -1})  # Indicate error
        return
    
    # Get stages from config data
    stages = config_data.get('stages', [])
    if not stages:
        conn.send({"type": "log", "level": "error", "message": "No stages found in configuration."})
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
        
        for stage in stages:
            # Use the enhanced stage runner with validation and intelligent cleanup
            conn.send({"type": "log", "level": "info", "message": f"Starting stage {stage['name']} for subject {subject_name}..."})
            
            try:
                # Use the new enhanced stage runner
                success = run_stage_with_validation(stage, subject, config_data)
                
                if success:
                    conn.send({"type": "log", "level": "info", "message": f"✅ Stage {stage['name']} completed successfully for {subject_name}"})
                else:
                    conn.send({"type": "log", "level": "error", "message": f"❌ Stage {stage['name']} failed for {subject_name}"})
                    # Continue with next subject instead of stopping entire pipeline
                    break
                    
            except Exception as e:
                conn.send({"type": "log", "level": "error", "message": f"❌ Stage {stage['name']} failed with exception for {subject_name}: {e}"})
                # Continue with next subject instead of stopping entire pipeline
                break
            
            completed_steps += 1
            progress_percent = int((completed_steps / total_steps) * 100)
            
            conn.send({"type": "log", "level": "success", "message": f"{subject_name}: Finished running stage {stage['name']}"})
            conn.send({"type": "progress", "value": progress_percent})

    # Send completion signal
    conn.send({"type": "log", "level": "success", "message": "All processing completed successfully."})
    conn.send({"type": "progress", "value": 100})  # Indicate success