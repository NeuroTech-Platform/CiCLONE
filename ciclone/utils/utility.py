import yaml
import subprocess
import shutil
from pathlib import Path

def execute_command(command: list, silent: bool = False) -> None:
    """Execute a shell command with error handling."""
    try:
        # Convert Path objects to strings
        str_command = [str(arg) for arg in command]
        if silent:
            subprocess.run(str_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(str_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{' '.join(str(arg) for arg in command)}' failed with error: {e}")
        raise

def read_config_file(file_path: str) -> dict:
    """Read and parse a YAML configuration file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def file_exists_with_extensions(base_filename: str) -> Path:
    """Check if a file exists with .nii or .nii.gz extension."""
    for ext in [".nii", ".nii.gz"]:
        file_path = Path(base_filename + ext)
        if file_path.exists():
            return file_path
    return None

# Stage-based cleaning system
def clean_by_patterns(processed_tmp_dir: Path, patterns: list[str]) -> None:
    """
    Clean files/directories matching the given patterns.
    
    Args:
        processed_tmp_dir: Path to processed_tmp directory
        patterns: List of glob patterns to match and remove
    """
    if not processed_tmp_dir.exists():
        print(f"Directory does not exist: {processed_tmp_dir}")
        return
    
    removed_count = 0
    for pattern in patterns:
        for path in processed_tmp_dir.glob(pattern):
            try:
                if path.is_file():
                    path.unlink()
                    print(f"Removed file: {path.name}")
                    removed_count += 1
                elif path.is_dir():
                    shutil.rmtree(path)
                    print(f"Removed directory: {path.name}")
                    removed_count += 1
            except Exception as e:
                print(f"Failed to remove {path}: {e}")
    
    if removed_count > 0:
        print(f"Cleaned {removed_count} items from {processed_tmp_dir.name}")

def clean_by_patterns_smart(processed_tmp_dir: Path, patterns: list[str], preserve_files: set[str]) -> None:
    """
    Smart cleanup that preserves required input files while cleaning outputs.
    
    Args:
        processed_tmp_dir: Path to processed_tmp directory
        patterns: List of glob patterns to match and remove
        preserve_files: Set of filenames to preserve (without full path)
    """
    if not processed_tmp_dir.exists():
        print(f"Directory does not exist: {processed_tmp_dir}")
        return
    
    removed_count = 0
    preserved_count = 0
    
    for pattern in patterns:
        for path in processed_tmp_dir.glob(pattern):
            try:
                # Check if this file should be preserved
                should_preserve = False
                for preserve_file in preserve_files:
                    if (path.name == preserve_file or 
                        path.stem == preserve_file or 
                        str(path.with_suffix('')) == str(processed_tmp_dir / preserve_file.split('.')[0])):
                        should_preserve = True
                        break
                
                if should_preserve:
                    print(f"Preserved (required input): {path.name}")
                    preserved_count += 1
                    continue
                
                # Safe to remove
                if path.is_file():
                    path.unlink()
                    print(f"Removed file: {path.name}")
                    removed_count += 1
                elif path.is_dir():
                    shutil.rmtree(path)
                    print(f"Removed directory: {path.name}")
                    removed_count += 1
                    
            except Exception as e:
                print(f"Failed to remove {path}: {e}")
    
    if removed_count > 0 or preserved_count > 0:
        print(f"Smart cleanup: {removed_count} items removed, {preserved_count} items preserved")

def extract_stage_dependencies_from_config(config_data: dict) -> dict:
    """Extract stage dependencies from config.
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        Dictionary mapping stage names to their dependencies
    """
    dependencies = {}
    stages = config_data.get('stages', [])
    for stage in stages:
        stage_name = stage.get('name')
        if stage_name:
            dependencies[stage_name] = stage.get('depends_on', [])
    
    return dependencies

def extract_stage_outputs_from_config(config_data: dict) -> dict:
    """Extract stage outputs from operations (auto-detects from parameters).
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        Dictionary mapping stage names to their outputs configuration
    """
    outputs = {}
    stages = config_data.get('stages', [])
    
    for stage in stages:
        stage_name = stage.get('name')
        if not stage_name:
            continue
            
        # Auto-detect outputs from operations
        detected_outputs = []
        cleanup_patterns = []
        
        for operation in stage.get('operations', []):
            # Extract from new parameter format
            params = operation.get('parameters', {})
            
            # Look for output parameters
            for param_name, param_value in params.items():
                if 'output' in param_name.lower() and param_value:
                    # Skip directory outputs
                    if 'dir' not in param_name.lower() and not param_value.startswith('${subj_dir}'):
                        detected_outputs.append(param_value)
                        
                        # Generate cleanup pattern if auto_clean is enabled
                        if stage.get('auto_clean', False):
                            # Create pattern to match output with extensions
                            pattern = param_value + '*'
                            cleanup_patterns.append(pattern)
        
        outputs[stage_name] = {
            'required_inputs': [],  # Stage inputs come from dependencies
            'outputs': detected_outputs,
            'cleanup_patterns': cleanup_patterns
        }
    
    return outputs

def find_all_dependents(stage_name: str, stage_dependencies: dict) -> list[str]:
    """
    Find all stages that depend on the given stage (recursively).
    
    Args:
        stage_name: Name of the stage to find dependents for
        stage_dependencies: Dictionary mapping stage names to their dependencies
        
    Returns:
        List of stage names that depend on the given stage
    """
    dependents = []
    
    # Find direct dependents
    for stage, deps in stage_dependencies.items():
        if stage_name in deps:
            dependents.append(stage)
    
    # Find indirect dependents (recursively)
    indirect_dependents = []
    for dependent in dependents:
        indirect_dependents.extend(find_all_dependents(dependent, stage_dependencies))
    
    # Combine and remove duplicates
    all_dependents = list(set(dependents + indirect_dependents))
    return all_dependents

def validate_stage_prerequisites(subject, stage_name: str, config_data: dict) -> tuple[bool, list[str]]:
    """
    Validate that all required inputs exist before running a stage.
    
    Args:
        subject: Subject instance
        stage_name: Name of the stage to validate
        config_data: Already loaded configuration data
        
    Returns:
        Tuple of (is_valid, missing_files)
    """
    stage_outputs = extract_stage_outputs_from_config(config_data)
    stage_config = stage_outputs.get(stage_name, {})
    required_inputs = stage_config.get('required_inputs', [])
    
    missing_files = []
    for required_file in required_inputs:
        # Substitute variables like ${name}
        actual_filename = required_file.replace("${name}", subject.get_subject_name())
        file_path = subject.processed_tmp / actual_filename
        
        # Check if file exists with .nii or .nii.gz extension
        if not file_exists_with_extensions(str(file_path.with_suffix(''))):
            missing_files.append(actual_filename)
    
    return len(missing_files) == 0, missing_files

def clean_dependent_stages(subject, stage_name: str, config_data: dict, single_stage_mode: bool = False) -> None:
    """
    Clean all stages that depend on the outputs of the given stage.
    This is the new intelligent cleanup system that replaces the old linear approach.
    IMPORTANT: Only cleans dependent stages, NOT the current stage's inputs.
    
    Args:
        subject: Subject instance
        stage_name: Name of the stage being rerun
        config_data: Already loaded configuration data
        single_stage_mode: If True, only clean current stage outputs, skip dependents
    """
    try:
        stage_dependencies = extract_stage_dependencies_from_config(config_data)
        stage_outputs = extract_stage_outputs_from_config(config_data)
        
        # Find all stages that depend on this stage
        dependent_stages = find_all_dependents(stage_name, stage_dependencies)
        
        # CRITICAL FIX: In single stage mode, don't clean dependents
        # In pipeline mode, clean dependents + current stage outputs
        if single_stage_mode:
            stages_to_clean = []  # Don't clean dependents in single stage mode
        else:
            stages_to_clean = dependent_stages  # Clean dependents in pipeline mode
        
        # Get current stage configuration
        current_stage_config = stage_outputs.get(stage_name, {})
        current_stage_inputs = set(current_stage_config.get('required_inputs', []))
        
        # Substitute variables in current stage inputs for comparison
        current_stage_input_files = set()
        for input_file in current_stage_inputs:
            substituted_input = input_file.replace("${name}", subject.get_subject_name())
            current_stage_input_files.add(substituted_input)
            # Also add variations with .nii and .nii.gz extensions
            current_stage_input_files.add(substituted_input + ".nii")
            current_stage_input_files.add(substituted_input + ".nii.gz")
        
        # Collect cleanup patterns for dependent stages only
        patterns_to_clean = []
        for stage in stages_to_clean:
            stage_config = stage_outputs.get(stage, {})
            cleanup_patterns = stage_config.get('cleanup_patterns', [])
            if cleanup_patterns:
                patterns_to_clean.extend(cleanup_patterns)
        
        # FIXED: Always clean current stage outputs (both single and pipeline mode)
        current_cleanup_patterns = current_stage_config.get('cleanup_patterns', [])
        for pattern in current_cleanup_patterns:
            patterns_to_clean.append(pattern)
        
        if not patterns_to_clean:
            print(f"No cleanup patterns found for stage '{stage_name}' and its dependents")
            return
        
        # Substitute variables in patterns
        substituted_patterns = []
        for pattern in patterns_to_clean:
            substituted_pattern = pattern.replace("${name}", subject.get_subject_name())
            substituted_patterns.append(substituted_pattern)
        
        processed_tmp = subject.processed_tmp
        mode_desc = "single stage" if single_stage_mode else "pipeline"
        print(f"Intelligent cleanup for stage '{stage_name}' in subject {subject.get_subject_name()} ({mode_desc} mode)")
        dependents_desc = ', '.join(stages_to_clean) if stages_to_clean else f"none ({'single stage mode' if single_stage_mode else 'no dependents'})"
        print(f"Cleaning dependents: {dependents_desc}")
        print(f"Preserving inputs: {', '.join(current_stage_input_files) if current_stage_input_files else 'none'}")
        print(f"Cleanup patterns: {', '.join(substituted_patterns)}")
        
        # Use smart cleanup that preserves required inputs
        # Handle patterns that target directories other than processed_tmp
        processed_tmp_patterns = []
        
        for pattern in substituted_patterns:
            if pattern.startswith('pipeline_output/'):
                # This targets pipeline_output directory, not processed_tmp
                pipeline_output_dir = subject.folder_path / 'pipeline_output'
                clean_pattern = pattern.replace('pipeline_output/', '')
                if pipeline_output_dir.exists():
                    clean_by_patterns(pipeline_output_dir, [clean_pattern])
            else:
                # This targets processed_tmp directory
                processed_tmp_patterns.append(pattern)
        
        # Clean patterns that target processed_tmp
        if processed_tmp_patterns:
            clean_by_patterns_smart(processed_tmp, processed_tmp_patterns, current_stage_input_files)
        
    except Exception as e:
        print(f"Error during intelligent cleanup: {e}")

def clean_before_stage(subject, stage_name: str, config_data: dict) -> None:
    """
    Clean files before running a stage using the new intelligent dependency system.
    This function maintains backward compatibility while using the improved cleanup logic.
    
    Args:
        subject: Subject instance
        stage_name: Name of the stage to clean for
        config_data: Already loaded configuration data
    """
    try:
        stages = config_data.get('stages', [])
        
        # Find the stage configuration
        target_stage = None
        for stage in stages:
            if stage.get('name') == stage_name:
                target_stage = stage
                break
        
        if not target_stage:
            print(f"Stage '{stage_name}' not found in configuration")
            return
        
        # Check if auto_clean is enabled for this stage
        if not target_stage.get('auto_clean', False):
            print(f"Auto-clean disabled for stage '{stage_name}'")
            return
        
        # Use the new intelligent cleanup system (default to pipeline mode for backward compatibility)
        clean_dependent_stages(subject, stage_name, config_data, single_stage_mode=False)
        
    except Exception as e:
        print(f"Error during auto-clean: {e}")

def print_cleanup_preview(stage_name: str, subject_name: str, config_data: dict) -> None:
    """
    Preview what files would be cleaned when running a specific stage.
    Useful for debugging and understanding the cleanup behavior.
    """
    try:
        stage_dependencies = extract_stage_dependencies_from_config(config_data)
        stage_outputs = extract_stage_outputs_from_config(config_data)
        
        # Find all stages that depend on this stage
        dependent_stages = find_all_dependents(stage_name, stage_dependencies)
        all_stages_to_clean = [stage_name] + dependent_stages
        
        # Collect cleanup patterns
        patterns_to_clean = []
        for stage in all_stages_to_clean:
            stage_config = stage_outputs.get(stage, {})
            cleanup_patterns = stage_config.get('cleanup_patterns', [])
            if cleanup_patterns:
                patterns_to_clean.extend(cleanup_patterns)
        
        # Substitute variables in patterns
        substituted_patterns = []
        for pattern in patterns_to_clean:
            substituted_pattern = pattern.replace("${name}", subject_name)
            substituted_patterns.append(substituted_pattern)
        
        print(f"🔍 Cleanup Preview for Stage: '{stage_name}' (Subject: {subject_name})")
        print(f"   Stages to clean: {', '.join(all_stages_to_clean)}")
        print(f"   File patterns: {', '.join(substituted_patterns)}")
        
    except Exception as e:
        print(f"Error generating cleanup preview: {e}")
