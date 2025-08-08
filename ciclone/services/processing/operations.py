from pathlib import Path
import shutil
from ciclone.utils.utility import execute_command
from ciclone.services.processing.tool_config import tool_config
import json
import numpy as np
import os
import subprocess



def open_fsleyes(input_file: Path):
    """
    Opens a NIFTI image file in FSLEyes viewer for visual inspection.
    
    This operation launches the FSLEyes application to display the specified
    medical image file. Used for manual quality control and visual inspection
    of processing results at various pipeline stages.
    
    Parameters:
        input_file: NIFTI image file to open in FSLEyes viewer
    
    Example:
        Input: ${name}_CT_Bone_R2S
    """
    input_file = Path(input_file)
    print(f"Opening {input_file} with fsleyes")
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Opening {input_file} with fsleyes")
    execute_command([tool_config.get_fsl_tool_path("fsleyes"), input_file])

def reorient_to_standard(input_file: Path, output_file: str) -> None:
    """
    Reorients a NIFTI image to standard neurological orientation using FSL.
    
    This operation uses FSL's fslreorient2std tool to reorient medical images
    to a standard coordinate system orientation. This ensures consistent
    orientation across different acquisition protocols and scanners.
    
    Parameters:
        input_file: Source NIFTI image to reorient
        output_file: Reoriented image in standard orientation
    
    Example:
        Input: ${name}_CT_Bone
        Output: ${name}_CT_Bone_R2S
    """
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Reorienting {input_file} => {output_file}")
    execute_command([tool_config.get_fsl_tool_path("fslreorient2std"), input_file, output_file])

def crop_image(input_file: Path, output_filename: str) -> Path:
    """
    Crops a NIFTI image to remove excess background using robust field of view detection.
    
    This operation uses FSL's robustfov tool to automatically detect and crop
    the image to the smallest bounding box that contains the main anatomical
    structures, removing unnecessary background areas and reducing file size.
    
    Parameters:
        input_file: Source NIFTI image to crop
        output_filename: Cropped image with reduced field of view
    
    Example:
        Input: ${name}_CT_Bone_R2S_N
        Output: ${name}_CT_Bone_C
    """
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Cropping {input_file} => {output_filename}")
    execute_command([tool_config.get_fsl_tool_path("robustfov"),"-v","-i", input_file,"-r", output_filename], silent=True)

def move_image(input_file: Path, output_file: str) -> None:
    """
    Moves a file from one location to another using system move command.
    
    This operation relocates a file from its current path to a new destination,
    removing it from the original location. Commonly used to organize processed
    files into appropriate directory structures during pipeline execution.
    
    Parameters:
        input_file: Source file to move
        output_file: Destination path for the moved file
    
    Example:
        Input: ${name}_CT_Bone_C
        Output: ${subj_dir}/processed_tmp
    """
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Moving {input_file} => {output_file}")
    execute_command(["mv", input_file, output_file])

def copy_image(input_file: Path, output_file: str) -> None:
    """
    Copies a file from one location to another, preserving the original.
    
    This operation creates a duplicate of the source file at the specified
    destination path while keeping the original file intact. Used for creating
    backups or duplicating files for different processing stages.
    
    Parameters:
        input_file: Source file to copy
        output_file: Destination path for the copied file
    
    Example:
        Input: ${name}_CT_Electrodes_C
        Output: ${subj_dir}/pipeline_output
    """
    if input_file is None:
        print("Input file is None, not doing anything.")
        return
    
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Copying {input_file} => {output_file}")
    execute_command(["cp", "-f", input_file, output_file])

def coregister_images(input_file: Path, ref_file: Path, output_file_name: str) -> None:
    """
    Coregisters two medical images using FSL FLIRT with mutual information.
    
    This operation aligns a moving image to a reference image using rigid body
    registration (6 degrees of freedom). Uses mutual information cost function
    and creates both the registered image and transformation matrix for further use.
    
    Parameters:
        input_file: Moving image to be registered to reference
        ref_file: Reference image that serves as registration target
        output_file_name: Registered image and transformation matrix (.mat)
    
    Example:
        Input: ${name}_CT_Electrodes_C
        Reference: ${name}_CT_Bone_C
        Output: b_${name}_postimplant_ct
    """
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
        tool_config.get_fsl_tool_path("flirt"),
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
    """
    Subtracts one image from another using FSL mathematical operations.
    
    This operation performs voxel-wise subtraction between two images using
    FSLmaths. Commonly used to isolate electrode artifacts by subtracting
    pre-operative from post-operative images.
    
    Parameters:
        input_file: Primary image (minuend)
        mask_file: Image to subtract (subtrahend)
        output_file_name: Result of subtraction operation
    
    Example:
        Input: b_${name}_postimplant_ct
        Mask: ${name}_CT_Bone_C
        Output: b_${name}_postimplant_ct_sub
    """
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
        tool_config.get_fsl_tool_path("fslmaths"), input_file.stem, "-sub", mask_file.stem, output_file_name
    ])

def threshold_image(input_file: Path, output_file_name: str) -> None:
    """
    Applies intensity thresholding to isolate high-density structures.
    
    This operation uses FSLmaths to threshold the image at value 1600,
    effectively isolating metallic electrode artifacts from surrounding
    tissue by removing voxels below the threshold intensity.
    
    Parameters:
        input_file: Source image to threshold
        output_file_name: Thresholded image with only high-intensity voxels
    
    Example:
        Input: b_${name}_postimplant_ct_sub
        Output: b_${name}_seeg
    """
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Thresholding {input_file.stem} => {output_file_name}")
    execute_command([
        tool_config.get_fsl_tool_path("fslmaths"), input_file.stem, "-thr", "1600", output_file_name
    ])

def apply_transformation2image(input_file: Path, transformation_file: Path, ref_file:Path, output_file_name: str) -> None:
    """
    Applies a pre-computed transformation matrix to transform an image.
    
    This operation uses FSL FLIRT to apply an existing transformation matrix
    to an image, warping it to match the coordinate space of a reference image.
    Uses high-quality sinc interpolation for accurate resampling.
    
    Parameters:
        input_file: Source image to transform
        transformation_file: FSL transformation matrix (.mat file)
        ref_file: Reference image defining target coordinate space
        output_file_name: Transformed image in reference space
    
    Example:
        Input: b_${name}_seeg
        Transformation: v_${name}_bone_mask.mat
        Reference: ${name}_CT_Electrodes_C
        Output: r_${name}_seeg
    """
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
        tool_config.get_fsl_tool_path("flirt"), "-in", input_file.stem, "-applyxfm", "-init", transformation_file, 
        "-out", output_file_name, "-paddingsize", "0.0", "-interp", "sinc", 
        "-ref", ref_file.stem, "-bins", "256", "-cost", "mutualinfo", 
        "-searchrx", "-180", "180", "-searchry", "-180", "180", "-searchrz", "-180", "180", 
        "-dof", "6", "-interp", "sinc", "-datatype", "int"
    ])

def apply_nudgetransformation2image(input_file: Path, transformation_file: Path | None, ref_file:Path, output_file_name: str) -> None:
    """
    Applies a manual nudge transformation or copies file if no transformation exists.
    
    This operation applies a user-defined manual adjustment transformation to an image.
    If no transformation file is provided, it simply copies the input file with a
    modified name to indicate the nudge step was completed.
    
    Parameters:
        input_file: Source image to transform
        transformation_file: Manual nudge transformation matrix (.mat file) or None
        ref_file: Reference image defining target coordinate space
        output_file_name: Transformed or copied image
    
    Example:
        Input: ${name}_CT_Bone_R2S
        Transformation: ${name}_CT_Bone_R2S.mat (or None)
        Reference: ${name}_CT_Bone_R2S
        Output: ${name}_CT_Bone_R2S_N
    """
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    ref_file = Path(ref_file)
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return
    
    if transformation_file is None:
        print(f"Transformation file is None, copying input file as output file")
        output_file = str(input_file).replace(".nii", "_N.nii")
        execute_command(["cp", "-f", input_file, output_file])
        return
        
    transformation_file = Path(transformation_file)

    print(f"Applying transformation {transformation_file.stem} to {input_file.stem} using for ref {ref_file.stem} => {output_file_name}")
    execute_command([
        tool_config.get_fsl_tool_path("flirt"), "-in", input_file.stem, "-applyxfm", "-init", transformation_file, 
        "-out", output_file_name, "-paddingsize", "0.0", "-interp", "sinc", 
        "-ref", ref_file.stem, "-bins", "256", "-cost", "mutualinfo", 
        "-searchrx", "-180", "180", "-searchry", "-180", "180", "-searchrz", "-180", "180", 
        "-dof", "6", "-interp", "sinc", "-datatype", "int"
    ])

def extract_brain(input_file: Path, output_file: Path, 
                 fractional_intensity: float = 0.45,
                 gradient_threshold: float = 0.0,
                 generate_mask: bool = True):
    """
    Extracts brain tissue using FSL BET with configurable parameters.
    
    This operation uses FSL's Brain Extraction Tool (BET) to remove skull and
    non-brain tissue. Parameters can be adjusted for different use cases:
    - Conservative (0.45 threshold) for preserving electrode artifacts
    - Aggressive (0.25 threshold) for cleaner brain extraction
    
    Parameters:
        input_file: Source image with skull (NIFTI file)
        output_file: Brain-extracted image output path
        fractional_intensity: Fractional intensity threshold (0-1)
                             0.45 = conservative (preserves electrodes)
                             0.25 = aggressive (cleaner extraction)
        gradient_threshold: Gradient threshold for edge detection (default 0.0)
        generate_mask: Whether to generate brain mask file (default True)
    
    Example:
        Conservative: extract_brain(input, output)  # uses defaults
        Aggressive: extract_brain(input, output, 0.25, 0.0, False)
    """
    input_file = Path(input_file)
    output_file = Path(output_file)

    # Build BET command with parameters
    cmd = [
        tool_config.get_fsl_tool_path("bet"), 
        input_file.stem, 
        output_file.stem, 
        "-f", str(fractional_intensity), 
        "-g", str(gradient_threshold)
    ]
    
    if generate_mask:
        cmd.append("-m")
    
    execute_command(cmd)


def mask_image(input_file: Path, mask_file: Path, output_file_name: str):
    """
    Applies a binary mask to an image using FSLmaths masking operation.
    
    This operation uses FSLmaths to apply a binary mask to an image,
    setting voxels to zero where the mask is zero and preserving values
    where the mask is non-zero. Used to restrict analysis to brain regions.
    
    Parameters:
        input_file: Source image to mask
        mask_file: Binary mask image
        output_file_name: Masked image with values only in mask regions
    
    Example:
        Input: r_${name}_seeg
        Mask: ${name}_stripped_mask
        Output: r_${name}_seeg_masked
    """
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
        tool_config.get_fsl_tool_path("fslmaths"), input_file.stem, "-mas", mask_file.stem, output_file_name
    ])

def cortical_reconstruction(input_file: Path, fs_output_dir: str):
    """
    Performs complete cortical surface reconstruction using FreeSurfer.
    
    This operation runs FreeSurfer's recon-all pipeline to generate cortical
    surface meshes, parcellations, and anatomical statistics from a T1-weighted
    MRI image. Creates comprehensive surface-based analysis data.
    
    Parameters:
        input_file: T1-weighted MRI image for reconstruction
        fs_output_dir: FreeSurfer subject directory for output data
    
    Example:
        Input: ${name}_T1_C
        Output: ${subj_dir}/processed_tmp/freesurfer_${name}
    """
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return    
    fs_subject_dir = Path(fs_output_dir)
    if fs_subject_dir.exists():
        print(f"Deleting existing FreeSurfer subject directory {fs_subject_dir}.")
        shutil.rmtree(fs_subject_dir)
        print(f"FreeSurfer subject directory {fs_subject_dir} deleted.")
        
    print(f"Reconstructing {input_file.stem} using FreeSurfer => {fs_subject_dir.stem}")
    execute_command([
        tool_config.get_freesurfer_tool_path("recon-all"), "-sd", str(fs_subject_dir.parent), "-s", str(fs_subject_dir.stem), "-i", str(input_file), "-all"
    ])

def transform_coordinates(input_json: Path, transformation_matrix: Path, output_json: str) -> None:
    """
    Transforms electrode coordinates from subject space to MNI space using transformation matrix.
    
    This operation applies the registration transformation matrix to electrode coordinates
    that were marked in subject image space, transforming them to MNI standard space.
    Intentionally ignores translations and applies only rotation/scaling components.
    
    Parameters:
        input_json: JSON file with electrode coordinates in subject space
        transformation_matrix: FSL transformation matrix (.mat file)
        output_json: JSON file with coordinates transformed to MNI space
    
    Example:
        Input: electrodes_${name}.json
        Matrix: MNI_${name}.mat
        Output: electrodes_${name}_mni.json
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
    Registers a T1 MRI brain image to MNI space using two-stage FSL FLIRT registration.
    
    This operation performs high-quality registration to MNI standard space using
    a two-stage approach: rigid registration (6 DOF) for rough alignment followed
    by affine registration (12 DOF) for fine-tuning. Uses MNI152_T1_2mm_brain template.
    
    Parameters:
        input_file: T1 brain image (brain-extracted) to register
        output_file_name: Base name for output files (creates multiple outputs)
    
    Example:
        Input: postT1_${name}_brain
        Output: MNI_${name} (plus _rigid and .mat files)
    """
    input_file = Path(input_file)
    ref_file = Path(f"{os.environ.get('FSLDIR')}/data/standard/MNI152_T1_2mm_brain.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return

    print(f"Registering {input_file.stem} to {ref_file.stem} => {output_file_name}")
    # First stage: rigid registration (6 DOF)
    execute_command([
        tool_config.get_fsl_tool_path("flirt"),
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
        tool_config.get_fsl_tool_path("flirt"),
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
    Registers a CT image to MNI space using FSL FLIRT with affine transformation.
    
    This operation performs affine registration (12 DOF) of a CT image to the MNI152 T1 2mm template
    using normalized mutual information cost function and high-quality sinc interpolation.
    Allows full rotation search to handle any initial orientation.
    
    Parameters:
        input_file: CT image to register to MNI space
        output_file_name: Base name for registered image and transformation matrix
    
    Example:
        Input: ${name}_CT_brain
        Output: MNI_${name}_CT (plus .mat file)
    """
    input_file = Path(input_file)
    ref_file = Path(f"{os.environ.get('FSLDIR')}/data/standard/MNI152_T1_2mm.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return
    
    print(f"Registering {input_file.name} to MNI space => {output_file_name}")
    execute_command([
        tool_config.get_fsl_tool_path("flirt"),
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
    Registers a T1 or CT image to MNI space using ANTs advanced normalization tools.
    
    This operation performs high-quality nonlinear registration to MNI standard space
    using ANTs (Advanced Normalization Tools). Includes optional intensity normalization
    and produces both registered images and transformation matrices.
    
    Parameters:
        input_file: Source T1 or CT image to register
        output_file_name: Base name for output files (creates multiple outputs)
        normalize: Whether to apply intensity normalization before registration
    
    Example:
        Input: ${name}_T1_brain
        Output: MNI_${name} (plus transformation files)
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