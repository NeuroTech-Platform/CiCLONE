from pathlib import Path
from clone.utility import execute_command

def crop_image(input_file: Path, output_filename: str) -> Path:
    input_file = Path(input_file)

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return

    print(f"Cropping {input_file} => {output_filename}")
    execute_command(["robustfov","-v","-i", input_file,"-r", output_filename])

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

def coregister_to_mni(input_file: Path, output_file_name: str) -> None:
    input_file = Path(input_file)
    ref_file = Path("/usr/local/fsl/data/standard/MNI152_T1_1mm.nii.gz")

    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return
    if not ref_file.exists():
        print(f"Reference file {ref_file} does not exist.")
        return

    print(f"Registering {input_file.stem} to {ref_file.stem} => {output_file_name}")
    execute_command([
        "/usr/local/fsl/bin/flirt",
        "-in", input_file,
        "-ref", ref_file,
        "-out", output_file_name,
        "-omat", output_file_name + ".mat",
        "-bins", "256",
        "-cost", "mutualinfo",
        "-searchrx", "-180", "180",
        "-searchry", "-180", "180",
        "-searchrz", "-180", "180",
        "-dof", "12",
        "-interp", "sinc",
        "-sincwidth", "7", 
        "-sincwindow", "hanning"
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
        "bet", input_file.stem, output_file.stem, "-f", "0.45", "-g", "0", "-m"
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
        "fslmaths", input_file.stem, "-mas", mask_file.stem, output_file_name
    ])

def cortical_reconstruction(input_file: Path, fs_output_dir: str):
    input_file = Path(input_file)
    if not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        return    
    fs_subject_dir = Path(fs_output_dir)

    print(f"Reconstructing {input_file.stem} using FreeSurfer => {fs_subject_dir.stem}")
    execute_command([
        "recon-all", "-sd", fs_subject_dir.parent, "-s", fs_subject_dir.stem, "-i", input_file, "-all"
    ])