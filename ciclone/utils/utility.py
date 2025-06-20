import yaml
import subprocess
import shutil
from pathlib import Path

def execute_command(command: list, silent: bool = False) -> None:
    """Execute a shell command with error handling."""
    try:
        if silent:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{' '.join(command)}' failed with error: {e}")
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

def clean_before_stage(subject, stage_name: str, config_data: dict) -> None:
    """
    Clean files before running a stage based on automatic dependency cleaning.
    
    Args:
        subject: Subject instance
        stage_name: Name of the stage to clean for
        config_data: Already loaded configuration data
    """
    try:
        stages = config_data.get('stages', [])
        stage_outputs = config_data.get('stage_outputs', {})
        
        # Find the stage
        target_stage = None
        stage_index = None
        for i, stage in enumerate(stages):
            if stage.get('name') == stage_name:
                target_stage = stage
                stage_index = i
                break
        
        if not target_stage:
            print(f"Stage '{stage_name}' not found in configuration")
            return
        
        # Check if auto_clean is enabled for this stage
        if not target_stage.get('auto_clean', False):
            return
        
        # Collect patterns to clean: this stage + all downstream stages
        patterns_to_clean = []
        
        # Start from current stage and include all downstream stages
        for i in range(stage_index, len(stages)):
            downstream_stage_name = stages[i]['name']
            if downstream_stage_name in stage_outputs:
                patterns_to_clean.extend(stage_outputs[downstream_stage_name])
        
        if not patterns_to_clean:
            return
        
        processed_tmp = subject.processed_tmp
        print(f"Auto-cleaning before stage '{stage_name}' in subject {subject.get_subject_name()}")
        print(f"Cleaning patterns: {', '.join(patterns_to_clean)}")
        clean_by_patterns(processed_tmp, patterns_to_clean)
        
    except Exception as e:
        print(f"Error during auto-clean: {e}")


