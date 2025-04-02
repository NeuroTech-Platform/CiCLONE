import os
import argparse
from pathlib import Path
import argcomplete
os.environ['_ARGCOMPLETE'] = '1'
os.environ['_ARGCOMPLETE_SUPPRESS_SPACE'] = '1'
from ciclone.operations import (
    crop_image,
    move_image,
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
from ciclone.utility import read_config_file
from ciclone.subject import Subject

def run_operation(operation, subject: Subject):    
    # Store the original working directory
    original_dir = os.getcwd()
    
    try:
        if operation['workdir']:
            workdir = subject.get_folder(operation['workdir'])
            print(f"Changing directory to {workdir}")
            os.chdir(workdir)

        if len(operation['files']) > 1:
            files = [subject.get_file(f.replace("${name}", subject.get_subject_name())) for f in operation['files'][:-1]] + \
                    [operation['files'][-1].replace("${name}", subject.get_subject_name()).replace("${subj_dir}", str(subject.folder_path))]
        else:
            files = [subject.get_file(f.replace("${name}", subject.get_subject_name())) for f in operation['files']]
        
        if operation['type'] == 'crop':
            crop_image(*files)
        elif operation['type'] == 'move':
            move_image(*files)    
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

def run_stage(stage, subject):
    print(f"")
    print(f"Running stage: {stage['name']}")
    for operation in stage['operations']:
        run_operation(operation, subject)

def update_output_directory(config_path, new_output_directory):
    import yaml

    with open(config_path, 'r') as file:
        config_data = yaml.safe_load(file)

    config_data['output_directory'] = new_output_directory

    with open(config_path, 'w') as file:
        yaml.safe_dump(config_data, file)

    print(f"Updated output directory to {new_output_directory}")

def main():
    argsparser = argparse.ArgumentParser(description='''CiClone : Cico Cardinale's Localization Of Neuro-electrodes\n\n
Quick Start Tutorial\n
Step 1: Set your output directory where subject(s) data will be stored
Step 2: Create folders for your subject(s) and put your subject(s) MRI's and CT's in the images folder that have been generated in step 1
Step 3: Run the processing pipeline (all stages or specific ones)
Step 4: Transform electrode coordinates to MNI space after having done the manual electrode marking in 3D slicer

Use ciclone -h to see all available commands''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    argsparser.add_argument('--update-output-directory', type=str, help='Update the output directory in the config file.')
    argsparser.add_argument('--create-folder', nargs='+', help='Create folder for the specified subject(s).')
    argsparser.add_argument('--subjects', nargs='+', help='List of subject(s) to process for each command.')
    argsparser.add_argument('--stages', nargs='+', help='Name of the stage(s) to run. If not provided, all stages will be run.')
    argsparser.add_argument('--transform-coordinates', type=str, help='Path to the 3D SlicerJSON file containing coordinates to transform')

    # Enable bash completion
    argcomplete.autocomplete(argsparser, always_complete_options=True)
    
    args = argsparser.parse_args()
    config_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "config/config.yaml"))
    print(f"Using config file: {config_path}")
    config_data = read_config_file(config_path)

    if args.update_output_directory:
        update_output_directory(config_path, args.update_output_directory)
        return

    output_directory_path = Path(config_data['output_directory'])
    if not output_directory_path.exists():
        print(f"[ERROR] Output directory {output_directory_path} does not exist.")
        return
    
    if args.create_folder:
        for subject_name in args.create_folder:
            subject_folder = output_directory_path / subject_name
            if not subject_folder.exists():
                subject_folder.mkdir(parents=True, exist_ok=True)
                print(f"[SUCCESS] Created folder for subject: {subject_name}")
            else:
                print(f"[INFO] Folder already exists for subject: {subject_name}")
        return

    # Handle transform coordinates independently
    if args.transform_coordinates:
        if not args.subjects:
            print("[ERROR] Please provide the subject name(s) for coordinate transformation.")
            return
            
        for subject_name in args.subjects:
            subject_folder = output_directory_path / subject_name
            transform_mat = subject_folder / 'processed_tmp' / f'MNI_{subject_name}_T1.mat'

            if not transform_mat.exists():
                print(f"[ERROR] Transformation matrix not found for subject {subject_name}")
                continue
            
            output_json = Path(args.transform_coordinates).parent / f'MNI_{Path(args.transform_coordinates).stem}.json'
            transform_coordinates(args.transform_coordinates, transform_mat, output_json)
            print(f"[SUCCESS] Transformed coordinates saved to {output_json}")
        return  # Exit after coordinate transformation

    # Handle stages only if transform_coordinates wasn't specified
    if args.subjects:
        for subject_name in args.subjects:
            subject_folder = output_directory_path / subject_name
            subject = Subject(subject_folder)

            stages = config_data['stages']
            if args.stages:
                for stage_name in args.stages:
                    stage = next((stage for stage in stages if stage['name'] == stage_name), None)
                    if stage:
                        run_stage(stage, subject)
                        print(f"{subject_name}: [SUCCESS] Finished running stage {stage_name}")
                    else:
                        print(f"{subject_name}: [ERROR] Stage {stage_name} not found.")

                print(f"{subject_name}: Finished running all stages")
                print(f"{subject_name}: You can now mark your electrodes using 3D slicer.")
            else:
                subject.clear_processed_tmp()
                for stage in stages:
                    run_stage(stage, subject)

if __name__ == "__main__":
    main()
