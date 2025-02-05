import yaml
import subprocess
from pathlib import Path

# Utility to run commands
def execute_command(command: list) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{' '.join(command)}' failed with error: {e}")

def read_config_file(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        config_data = yaml.safe_load(file)
    return config_data

# Utility function to check for the existence of files with either .nii or .nii.gz extension
def file_exists_with_extensions(base_filename: str) -> Path:
    """ Check if a file exists with .nii or .nii.gz extension. """
    nii_file = Path(base_filename + ".nii")
    nii_gz_file = Path(base_filename + ".nii.gz")
    
    if nii_file.exists():
        return nii_file
    elif nii_gz_file.exists():
        return nii_gz_file
    else:
        return None
