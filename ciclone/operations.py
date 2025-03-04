from pathlib import Path
from ciclone.utility import execute_command
import json
import numpy as np
import os
import subprocess

def open_fsleyes(input_file: Path):
    input_file = Path(input_file)
    print(f"Opening {input_file} with fsleyes")
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Opening {input_file} with fsleyes")
    execute_command(["/usr/local/fsl/bin/fsleyes", input_file])

def crop_image(input_file: Path, output_filename: str) -> Path:
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Cropping {input_file} => {output_filename}")
    execute_command(["/usr/local/fsl/bin/robustfov","-v","-i", input_file,"-r", output_filename], silent=True)

def move_image(input_file: Path, output_file: str) -> None:
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Moving {input_file} => {output_file}")
    execute_command(["mv", input_file, output_file])

def coregister_images(input_file: Path, ref_file: Path, output_file_name: str) -> None:
    input_file = Path(input_file)
    ref_file = Path(ref_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return

    print(f"Registering {input_file.stem} to {ref_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/flirt",
        "-in", input_file.stem,
        "-ref", ref_file.stem,
        "-out", output_file_name,
        "-omat", output_file_name + ".mat",
        "-bins", "256",
        "-cost", "mutualinfo",
        "-searchrx", "-180", "180",
        "-searchry", "-180", "180",
        "-searchrz", "-180", "180",
        "-dof", "6",
        "-interp", "sinc",
        "-datatype", "int"
    ])

def subtract_image(input_file: Path, mask_file: Path, output_file_name: str) -> None:
    input_file = Path(input_file)
    mask_file = Path(mask_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not mask_file.exists():
        print(f"Mask file {mask_file} does not exist.")
        return

    print(f"Subtracting {input_file.stem} by {mask_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/fslmaths", input_file.stem, "-sub", mask_file.stem, output_file_name
    ])

def threshold_image(input_file: Path, output_file_name: str) -> None:
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Thresholding {input_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/fslmaths", input_file.stem, "-thr", "1600", output_file_name
    ])

def apply_transformation2image(input_file: Path, transformation_file: Path, ref_file:Path, output_file_name: str) -> None:
    input_file = Path(input_file)
    transformation_file = Path(transformation_file)
    ref_file = Path(ref_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not transformation_file.exists():
        print(f"Transformation file {transformation_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return
    
    print(f"Applying transformation {transformation_file.stem} to {input_file.stem} using for ref {ref_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/flirt", "-in", input_file.stem, "-applyxfm", "-init", transformation_file, 
        "-out", output_file_name, "-paddingsize", "0.0", "-interp", "sinc", 
        "-ref", ref_file.stem, "-bins", "256", "-cost", "mutualinfo", 
        "-searchrx", "-180", "180", "-searchry", "-180", "180", "-searchrz", "-180", "180", 
        "-dof", "6", "-interp", "sinc", "-datatype", "int"
    ])

def extract_brain(input_file: Path, output_file: Path):
    input_file = Path(input_file)
    output_file = Path(output_file)

    # Use BET to preserve screws and enhance visibility of relevant structures
    execute_command([
        "/usr/local/fsl/bin/bet", input_file.stem, output_file.stem, "-f", "0.45", "-g", "0", "-m"
    ])

def extract_brain2(input_file: Path, output_file: Path):
    input_file = Path(input_file)
    output_file = Path(output_file)

    # Use BET to preserve screws and enhance visibility of relevant structures
    execute_command([
        "/usr/local/fsl/bin/bet", input_file.stem, output_file.stem, "-f", "0.25", "-g", "0"
    ])

def mask_image(input_file: Path, mask_file: Path, output_file_name: str):
    input_file = Path(input_file)
    mask_file = Path(mask_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not mask_file.exists():
        print(f"Mask file {mask_file} does not exist.")
        return

    print(f"Masking {input_file.stem} by {mask_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/fslmaths", input_file.stem, "-mas", mask_file.stem, output_file_name
    ])

def cortical_reconstruction(input_file: Path, fs_output_dir: str):
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return    
    fs_subject_dir = Path(fs_output_dir)

    print(f"Reconstructing {input_file.stem} using FreeSurfer => {fs_subject_dir.stem}")
    execute_command([
        "recon-all", "-sd", str(fs_subject_dir.parent), "-s", str(fs_subject_dir.stem), "-i", str(input_file), "-all"
    ])

def transform_coordinates(input_json: Path, transformation_matrix: Path, output_json: str) -> None:
    """
    Transform electrode coordinates from subject space to MNI space
    using the transformation matrix from the registration pipeline.
    
    Note: This function assumes electrode coordinates are in image space
    and intentionally ignores translations from the transformation matrix
    since we only want to apply rotation and scaling components.
    """
    # Read the transformation matrix
    with open(transformation_matrix, 'r') as f:
        matrix_lines = f.readlines()
        matrix = np.array([[float(num) for num in line.strip().split()] for line in matrix_lines])

    # Zero out translations since electrodes are marked in image space
    # and we only want to apply rotation/scaling
    matrix[:3, 3] = 0

    # Read the JSON file with electrode coordinates
    with open(input_json, 'r') as f:
        data = json.load(f)

    # Transform each coordinate
    for markup in data.get('markups', []):
        for point in markup.get('controlPoints', []):
            # Get the coordinate and make it homogeneous (add 1 as 4th component)
            coord = np.array([
                point['position'][0], 
                point['position'][1], 
                point['position'][2],
                1.0
            ])
            
            # Apply transformation matrix (rotation and scaling only)
            mni_coord = matrix @ coord
            
            # Update the position (remove homogeneous component)
            point['position'] = [
                float(mni_coord[0]), 
                float(mni_coord[1]), 
                float(mni_coord[2])
            ]
            point['description'] = point.get('description', '') + ' (MNI)'

    # Save transformed coordinates
    with open(output_json, 'w') as f:
        json.dump(data, f, indent=2)

def register_mri_to_mni(input_file: Path, output_file_name: str) -> None:
    """
    Register a T1 MRI image to MNI space using FSL FLIRT. The registration is done in two stages:
    1. Rigid registration (6 DOF) to get a rough alignment
    2. Affine registration (12 DOF) initialized with the rigid transform for fine-tuning
    
    Args:
        input_file: Path to the input T1 MRI image
        output_file_name: Name of the output file (without extension). Will create:
            - {output_file_name}_rigid.mat: Rigid transformation matrix
            - {output_file_name}_rigid: Rigidly registered image
            - {output_file_name}.mat: Final affine transformation matrix  
            - {output_file_name}: Final registered image
    """
    input_file = Path(input_file)
    ref_file = Path(f"{os.environ.get('FSLDIR')}/data/standard/MNI152_T1_1mm.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return

    print(f"Registering {input_file.stem} to {ref_file.stem} => {output_file_name}")
    # First stage: rigid registration (6 DOF)
    execute_command([
        "/usr/local/fsl/bin/flirt",
        "-in", input_file.stem,
        "-ref", ref_file,
        "-omat", f"{output_file_name}_rigid.mat",
        "-out", f"{output_file_name}_rigid",
        "-dof", "6",                    # Rigid registration (rotation + translation)
        "-cost", "normmi",              # Normalized mutual information
        "-searchrx", "-180", "180",     # Full rotation search
        "-searchry", "-180", "180",
        "-searchrz", "-180", "180",
        "-bins", "256",
        "-interp", "spline"             # High quality interpolation
    ])

    # Second stage: affine registration (12 DOF) initialized with rigid result
    execute_command([
        "/usr/local/fsl/bin/flirt",
        "-in", input_file.stem,
        "-ref", ref_file,
        "-init", f"{output_file_name}_rigid.mat",  # Initialize with rigid transform
        "-omat", f"{output_file_name}.mat",
        "-out", output_file_name,
        "-dof", "12",                   # Affine registration
        "-cost", "normmi",
        "-bins", "256",
        "-interp", "spline"
    ])

def register_ct_to_mni(input_file: Path, output_file_name: str) -> None:
    """
    Register a CT image to MNI space using FSL FLIRT.
    
    This function performs affine registration (12 DOF) of a CT image to the MNI152 T1 1mm template,
    using normalized mutual information as the cost function and high quality sinc interpolation.
    The registration allows for full rotation search to handle any initial orientation.
    
    Args:
        input_file: Path to the input CT image
        output_file_name: Name of the output file (without extension). Will create:
            - {output_file_name}: Final registered image in MNI space
            - {output_file_name}.mat: Affine transformation matrix from native to MNI space
    """
    input_file = Path(input_file)
    ref_file = Path(f"{os.environ.get('FSLDIR')}/data/standard/MNI152_T1_1mm.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return
    
    print(f"Registering {input_file.name} to MNI space => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/flirt",
        "-in", input_file.name,
        "-ref", ref_file,
        "-out", output_file_name,
        "-omat", f"{output_file_name}.mat",
        "-cost", "normmi",
        "-dof", "12",
        "-searchrx", "-180", "180",  # Full rotation range
        "-searchry", "-180", "180",
        "-searchrz", "-180", "180",
        "-bins", "256",              # More bins for better intensity mapping
        "-interp", "sinc"            # Higher quality interpolation
    ])

def register_to_mni_ants(input_file: Path, output_file_name: str, normalize: bool = True) -> None:
    """
    Register a single image (T1 or CT) to MNI space using ANTs
    
    Args:
        input_file: Path to the input image (T1 or CT)
        output_file_name: Name of the output file
        normalize: Whether to normalize the image intensities before registration
    """
    input_file = Path(input_file)
    ref_file = Path(f"{os.environ.get('FSLDIR')}/data/standard/MNI152_T1_1mm.nii.gz")
    #ref_file = Path(f"MNI152_T1_1mm_brain_normalized.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return

    # Normalize image intensities if requested
    if normalize:
        norm_file_path = f"norm_{input_file.name}"
        print(f"Normalizing {input_file.name}")
        
        # Get the statistics values first using subprocess directly
        p2_value = subprocess.run(['fslstats', input_file.name, '-P', '2'], 
                                capture_output=True, text=True, check=True).stdout.strip()
        p98_value = subprocess.run(['fslstats', input_file.name, '-P', '98'], 
                                 capture_output=True, text=True, check=True).stdout.strip()
        
        # Use the values in the normalization command
        execute_command([
            "fslmaths",
            input_file.name,
            "-sub", p2_value,
            "-div", p98_value,
            norm_file_path
        ])
        input_file = Path(norm_file_path)

    print(f"Registering {input_file.stem} to {ref_file.stem} => {output_file_name}")
    execute_command([
        "antsRegistrationSyNQuick.sh",
        "-d", "3",
        "-f", ref_file,
        "-m", input_file,
        "-t", "r",
        "-t", "a",
        "-n", "12",
        "-o", output_file_name
    ])

    # execute_command([
    #     "antsRegistrationSyN.sh",
    #     "-d", "3",
    #     "-f", ref_file,
    #     "-m", input_file,
    #     "-t", "sr",
    #     "-n", "12",
    #     "-o", output_file_name,
    # ])

    # Convert ANTs matrix to FSL format
    execute_command([
        "ConvertTransformFile",
        "3",
        f"{output_file_name}0GenericAffine.mat",
        f"{output_file_name}matrix.txt",
        "--matrix"
    ])

    # Convert the transformation matrix to FSL format
    print(f"Converting transformation matrix to FSL format")
    ants_matrix_file = Path(f"{output_file_name}matrix.txt")
    fsl_matrix_file = Path(f"{output_file_name}fsl.mat")

    try:
        # Read the ANTs matrix
        with open(ants_matrix_file, 'r') as f:
            lines = f.readlines()

        # Parse the matrix values (skip header lines starting with #)
        matrix_lines = [line for line in lines if not line.startswith('#')]
        matrix = np.array([list(map(float, line.split())) for line in matrix_lines])

        # Create 4x4 matrix
        matrix_4x4 = np.eye(4)
        matrix_4x4[:3, :3] = matrix[:3, :3]  # Copy rotation/scaling part
        matrix_4x4[:3, 3] = matrix[:3, -1]   # Copy translation part

        # Convert to FSL format
        fsl_matrix = np.linalg.inv(matrix_4x4)

        # Save in FSL format
        np.savetxt(fsl_matrix_file, fsl_matrix, fmt='%g')
        print(f"FSL matrix saved to {fsl_matrix_file}")

    except Exception as e:
        print(f"Error converting matrix to FSL format: {e}")