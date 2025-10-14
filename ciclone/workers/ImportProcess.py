"""
Import worker process for background image import operations.

This module provides the process function that executes image import operations
(crop + optional registration) in a separate process, enabling responsive UI
during long-running FSL operations.
"""

import signal
import sys
import traceback
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from multiprocessing.connection import Connection

from ciclone.services.processing.operations import crop_image, coregister_images


def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    sys.exit(0)


def processImports(conn: Connection, import_jobs: List[Dict[str, Any]]) -> None:
    """
    Process a list of import jobs sequentially.

    This function runs in a separate process and performs image import operations
    (FSL robustfov crop + optional FSL FLIRT registration) for each job in the list.
    Progress updates and logs are sent back to the parent process via pipe connection.

    Args:
        conn: Multiprocessing pipe connection for sending progress updates
        import_jobs: List of import job dictionaries (serialized ImportJob objects)

    Message Format:
        - ('progress', completed_ops, total_ops): Progress update
        - ('log', level, message): Log message (level: 'info', 'success', 'error', 'warning')
        - ('job_complete', job_index, success, message): Individual job completion
        - ('complete', success_count, error_count): All jobs finished
        - ('error', error_message): Fatal error occurred
    """
    # Set up signal handlers for clean termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    total_jobs = len(import_jobs)
    success_count = 0
    error_count = 0

    # Calculate total operations for progress tracking
    # Each job may have: crop (if needs_crop) + registration (if has target)
    total_operations = 0
    for job_dict in import_jobs:
        if job_dict.get('needs_crop', True):
            total_operations += 1
        if job_dict.get('registration_target_path'):
            total_operations += 1

    completed_operations = 0

    try:
        conn.send(('log', 'info', f'Starting import of {total_jobs} image(s)'))

        for job_index, job_dict in enumerate(import_jobs, start=1):
            try:
                # Extract job parameters
                subject_name = job_dict['subject_name']
                source_image_path = job_dict['source_image_path']
                output_path = job_dict['output_path']
                image_identifier = job_dict['image_identifier']
                needs_crop = job_dict.get('needs_crop', True)
                registration_target_path = job_dict.get('registration_target_path')
                registration_target_identifier = job_dict.get('registration_target_identifier')
                temp_crop_path = job_dict.get('temp_crop_path')  # Pre-assigned temp path from SubjectImporter

                # Validate source exists
                if not Path(source_image_path).exists():
                    error_msg = f"Source image not found: {source_image_path}"
                    conn.send(('log', 'error', error_msg))
                    conn.send(('job_complete', job_index, False, error_msg))
                    error_count += 1
                    continue

                # Log job start with details
                if registration_target_path:
                    conn.send(('log', 'info', f'[{job_index}/{total_jobs}] {image_identifier} (will coregister to {registration_target_identifier})'))
                else:
                    conn.send(('log', 'info', f'[{job_index}/{total_jobs}] {image_identifier} (crop only)'))

                # Determine working paths
                # Use temp_crop_path if provided (means this image will be registered)
                if needs_crop and temp_crop_path:
                    # Crop to designated temp path (will register afterward)
                    crop_output = temp_crop_path
                    working_image = crop_output
                    conn.send(('log', 'debug', f'  Crop output: {crop_output} (temp)'))
                elif needs_crop:
                    # Only crop, no temp path needed: output directly to final destination
                    crop_output = output_path
                    working_image = crop_output
                    conn.send(('log', 'debug', f'  Crop output: {crop_output} (final)'))
                else:
                    # No crop: use source directly
                    working_image = source_image_path
                    crop_output = None
                    conn.send(('log', 'debug', f'  No crop needed, using source directly'))

                # Phase 1: Crop if needed
                if needs_crop:
                    try:
                        conn.send(('log', 'info', f'  → Cropping {image_identifier}'))
                        crop_image(
                            input_file=Path(source_image_path),
                            output_filename=crop_output
                        )

                        # Verify crop output
                        if not Path(crop_output).exists():
                            error_msg = f"Crop failed - output not created: {crop_output}"
                            conn.send(('log', 'error', error_msg))
                            conn.send(('job_complete', job_index, False, error_msg))
                            error_count += 1
                            continue

                        completed_operations += 1
                        conn.send(('progress', completed_operations, total_operations))
                        conn.send(('log', 'success', f'  ✓ Cropped {image_identifier}'))

                    except Exception as e:
                        error_msg = f"Crop error for {image_identifier}: {str(e)}"
                        conn.send(('log', 'error', error_msg))
                        conn.send(('job_complete', job_index, False, error_msg))
                        error_count += 1
                        continue

                # Phase 2: Register if needed
                if registration_target_path:
                    try:
                        # Validate reference exists
                        conn.send(('log', 'debug', f'  Checking registration target: {registration_target_path}'))
                        if not Path(registration_target_path).exists():
                            error_msg = f"Registration target not found: {registration_target_path}"
                            conn.send(('log', 'error', error_msg))
                            conn.send(('log', 'error', f"  Expected at: {registration_target_path}"))
                            conn.send(('job_complete', job_index, False, error_msg))
                            error_count += 1
                            # Clean up temp crop file if exists
                            if crop_output and crop_output != output_path and Path(crop_output).exists():
                                Path(crop_output).unlink()
                            continue

                        conn.send(('log', 'info', f'  → Coregistering {image_identifier} → {registration_target_identifier}'))
                        conn.send(('log', 'debug', f'  Moving image: {working_image}'))
                        conn.send(('log', 'debug', f'  Reference: {registration_target_path}'))
                        conn.send(('log', 'debug', f'  Output: {output_path}'))

                        # Ensure output directory exists
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                        # Perform coregistration
                        coregister_images(
                            input_file=str(working_image),
                            ref_file=str(registration_target_path),
                            output_file_name=output_path
                        )

                        # Verify registration output
                        if not Path(output_path).exists():
                            error_msg = f"Registration failed - output not created: {output_path}"
                            conn.send(('log', 'error', error_msg))
                            conn.send(('job_complete', job_index, False, error_msg))
                            error_count += 1
                            # Clean up temp crop file if exists
                            if crop_output and crop_output != output_path and Path(crop_output).exists():
                                Path(crop_output).unlink()
                            continue

                        # Clean up temporary crop file
                        if crop_output and crop_output != output_path and Path(crop_output).exists():
                            Path(crop_output).unlink()

                        completed_operations += 1
                        conn.send(('progress', completed_operations, total_operations))
                        conn.send(('log', 'success', f'  ✓ Coregistered {image_identifier}'))

                    except Exception as e:
                        error_msg = f"Registration error for {image_identifier}: {str(e)}"
                        conn.send(('log', 'error', error_msg))
                        conn.send(('job_complete', job_index, False, error_msg))
                        error_count += 1
                        # Clean up temp crop file if exists
                        if crop_output and crop_output != output_path and Path(crop_output).exists():
                            Path(crop_output).unlink()
                        continue

                # Success
                if registration_target_path:
                    success_msg = f"Successfully imported and coregistered {image_identifier}"
                elif needs_crop:
                    success_msg = f"Successfully imported and cropped {image_identifier}"
                else:
                    success_msg = f"Successfully imported {image_identifier}"

                conn.send(('log', 'success', success_msg))
                conn.send(('job_complete', job_index, True, success_msg))
                success_count += 1

            except Exception as e:
                error_msg = f"Error importing {job_dict.get('image_identifier', 'unknown')}: {str(e)}"
                conn.send(('log', 'error', error_msg))
                conn.send(('log', 'error', traceback.format_exc()))
                conn.send(('job_complete', job_index, False, error_msg))
                error_count += 1

        # Send completion message
        completion_msg = f"Import complete: {success_count} succeeded, {error_count} failed"
        conn.send(('log', 'info', completion_msg))
        conn.send(('complete', success_count, error_count))

    except Exception as e:
        error_msg = f"Fatal error in import process: {str(e)}"
        conn.send(('error', error_msg))
        conn.send(('log', 'error', traceback.format_exc()))

    finally:
        conn.close()
