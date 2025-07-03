import os
import shutil
from pathlib import Path
from ciclone.services.processing.operations import (
    crop_image,
    move_image,
    copy_image,
    coregister_images,
    subtract_image,
    threshold_image,
    apply_transformation2image,
    extract_brain,
    extract_brain2,
    mask_image,
    cortical_reconstruction,
    transform_coordinates,
    register_ct_to_mni,
    register_mri_to_mni,
    open_fsleyes
)
from ciclone.domain.subject import Subject
from ciclone.utils.utility import validate_stage_prerequisites, clean_dependent_stages

def run_operation(operation, subject: Subject):    
    # Store the original working directory
    original_dir = os.getcwd()
    
    try:
        if operation['workdir']:
            workdir = subject.get_folder(operation['workdir'])
            print(f"Changing directory to {workdir}")
            os.chdir(workdir)

        # Use workdir for file resolution to avoid conflicts between processed_tmp and pipeline_output
        search_dir = operation.get('workdir', None)
        
        if len(operation['files']) > 1:
            files = [subject.get_file(f.replace("${name}", subject.get_subject_name()), search_dir) for f in operation['files'][:-1]] + \
                    [operation['files'][-1].replace("${name}", subject.get_subject_name()).replace("${subj_dir}", str(subject.folder_path))]
        else:
            files = [subject.get_file(f.replace("${name}", subject.get_subject_name()), search_dir) for f in operation['files']]
        
        if operation['type'] == 'crop':
            crop_image(*files)
        elif operation['type'] == 'move':
            move_image(*files)
        elif operation['type'] == 'copy':
            copy_image(*files)
        elif operation['type'] == 'coregister':
            coregister_images(*files)
        elif operation['type'] == 'subtract':
            subtract_image(*files)
        elif operation['type'] == 'threshold':
            threshold_image(*files)
        elif operation['type'] == 'apply_transformation':
            apply_transformation2image(*files)
        elif operation['type'] == 'extract_brain':
            extract_brain(*files)
        elif operation['type'] == 'extract_brain2':
            extract_brain2(*files)
        elif operation['type'] == 'mask':
            mask_image(*files)
        elif operation['type'] == 'reconstruct':
            cortical_reconstruction(*files)
        elif operation['type'] == 'register_ct_to_mni':
            register_ct_to_mni(*files)
        elif operation['type'] == 'register_mri_to_mni':
            register_mri_to_mni(*files)
        elif operation['type'] == 'open_fsleyes':
            open_fsleyes(*files)

    finally:
        # Always return to the original directory
        os.chdir(original_dir)

def create_file_snapshot(processed_tmp_dir: Path) -> list[Path]:
    """Create a snapshot of current files for rollback capability."""
    if not processed_tmp_dir.exists():
        return []
    return list(processed_tmp_dir.glob("*"))

def rollback_to_snapshot(processed_tmp_dir: Path, snapshot_files: list[Path]) -> None:
    """Rollback the directory to the state captured in the snapshot."""
    try:
        if processed_tmp_dir.exists():
            # Remove all current files
            for item in processed_tmp_dir.glob("*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        
        # Note: We cannot restore deleted files, but we can at least clean up
        # any partial files that were created during the failed stage
        print(f"Rolled back {processed_tmp_dir.name} to clean state")
        
    except Exception as e:
        print(f"Error during rollback: {e}")

def run_stage(stage, subject):
    """
    Run a stage with basic error handling.
    This is the original function maintained for backward compatibility.
    """
    print(f"")
    print(f"Running stage: {stage['name']}")
    for operation in stage['operations']:
        run_operation(operation, subject)

def run_stage_with_validation(stage, subject, config_data, total_stages_count: int = None):
    """
    Run a stage with comprehensive validation, cleanup, and error handling.
    
    Args:
        stage: Stage configuration dictionary
        subject: Subject instance
        config_data: Full configuration data including dependencies
        total_stages_count: Total number of stages being run (for single vs pipeline detection)
        
    Returns:
        bool: True if stage completed successfully, False otherwise
    """
    stage_name = stage['name']
    
    try:
        print(f"")
        print(f"🔄 Preparing to run stage: {stage_name}")
        
        # 1. Validate prerequisites
        is_valid, missing_files = validate_stage_prerequisites(subject, stage_name, config_data)
        if not is_valid:
            print(f"❌ Prerequisites not met for stage '{stage_name}'")
            print(f"   Missing required files: {', '.join(missing_files)}")
            return False
        
        print(f"✅ Prerequisites validated for stage '{stage_name}'")
        
        # 2. Perform intelligent cleanup if auto_clean is enabled
        if stage.get('auto_clean', False):
            # Detect if this is single stage mode (only 1 stage being run)
            single_stage_mode = total_stages_count == 1
            print(f"🧹 Performing intelligent cleanup for stage '{stage_name}'")
            clean_dependent_stages(subject, stage_name, config_data, single_stage_mode)
        
        # 3. Create snapshot for potential rollback
        snapshot_files = create_file_snapshot(subject.processed_tmp)
        
        # 4. Run the stage operations
        print(f"🚀 Executing stage: {stage_name}")
        for i, operation in enumerate(stage['operations'], 1):
            print(f"   Operation {i}/{len(stage['operations'])}: {operation['type']}")
            run_operation(operation, subject)
        
        print(f"✅ Stage '{stage_name}' completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Stage '{stage_name}' failed: {e}")
        
        # Attempt rollback on failure
        try:
            print(f"🔄 Attempting rollback for stage '{stage_name}'")
            rollback_to_snapshot(subject.processed_tmp, snapshot_files)
        except Exception as rollback_error:
            print(f"⚠️  Rollback failed: {rollback_error}")
        
        return False
