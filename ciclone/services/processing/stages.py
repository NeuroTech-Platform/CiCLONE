import os
from ciclone.services.processing.operations import (
    crop_image,
    move_image,
    copy_image,
    coregister_images,
    subtract_image,
    threshold_image,
    apply_transformation2image,
    apply_nudgetransformation2image,
    extract_brain,
    mask_image,
    cortical_reconstruction,
    transform_coordinates,
    register_ct_to_mni,
    register_mri_to_mni,
    open_fsleyes,
    reorient_to_standard
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
        
        # All operations now use unified parameter format
        params = {}
        for param_name, param_value in operation['parameters'].items():
            # Replace template variables in parameter values
            if isinstance(param_value, str):
                param_value = param_value.replace("${name}", subject.get_subject_name())
                param_value = param_value.replace("${subj_dir}", str(subject.folder_path))
                
                # If this looks like a file path and doesn't start with /, try to resolve it
                if not param_value.startswith('/') and not param_value.startswith('${'):
                    # Check if this parameter is a file parameter
                    # We need to determine if we should resolve the path
                    if '.' in param_value or '_' in param_value:  # Heuristic for file names
                        resolved_file = subject.get_file(param_value, search_dir)
                        if resolved_file:
                            param_value = resolved_file
            
            params[param_name] = param_value
        
        # Get the function to call
        func = get_operation_function(operation['type'])
        if func:
            func(**params)
        else:
            print(f"Unknown operation type: {operation['type']}")

    finally:
        # Always return to the original directory
        os.chdir(original_dir)


def get_operation_function(operation_type: str):
    """Get the operation function based on operation type."""
    operation_map = {
        'crop': crop_image,
        'move': move_image,
        'copy': copy_image,
        'coregister': coregister_images,
        'subtract': subtract_image,
        'threshold': threshold_image,
        'apply_transformation': apply_transformation2image,
        'apply_nudgetransformation': apply_nudgetransformation2image,
        'extract_brain': extract_brain,
        'mask': mask_image,
        'reconstruct': cortical_reconstruction,
        'register_ct_to_mni': register_ct_to_mni,
        'register_mri_to_mni': register_mri_to_mni,
        'open_fsleyes': open_fsleyes,
        'reorient_to_standard': reorient_to_standard
    }
    return operation_map.get(operation_type)


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
        
        # 3. Run the stage operations
        print(f"🚀 Executing stage: {stage_name}")
        for i, operation in enumerate(stage['operations'], 1):
            print(f"   Operation {i}/{len(stage['operations'])}: {operation['type']}")
            run_operation(operation, subject)
        
        print(f"✅ Stage '{stage_name}' completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Stage '{stage_name}' failed: {e}")        
        return False
