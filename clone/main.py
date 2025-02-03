import os
import argparse
from pathlib import Path
from clone.operations import (
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
    register_mri_to_mni
)
from clone.utility import read_config_file
from clone.subject import Subject

def run_operation(operation, subject: Subject):    
    # Store the original working directory
    original_dir = os.getcwd()
    
    try:
        if operation['workdir']:
            workdir = subject.get_folder(operation['workdir'])
            print(f"Changing directory to {workdir}")
            os.chdir(workdir)

        files = [subject.get_file(f.replace("${name}", subject.get_subject_name())) for f in operation['files'][:-1]] + \
                [operation['files'][-1].replace("${name}", subject.get_subject_name()).replace("${subj_dir}", str(subject.folder_path))]
        
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

    finally:
        # Always return to the original directory
        os.chdir(original_dir)

def run_stage(stage, subject):
    print(f"Running stage: {stage['name']}")
    for operation in stage['operations']:
        run_operation(operation, subject)

def main():
    argsparser = argparse.ArgumentParser(description='Process some medical imaging data.')
    argsparser.add_argument('--subjects', nargs='+', help='List of subjects.')
    argsparser.add_argument('--create-folder', action='store_true', help='Create folder for the subject(s) provided in the list.')
    argsparser.add_argument('--stages', nargs='+', help='Name of the stage to run. If not provided, all stages will be run.')
    argsparser.add_argument('--transform-coordinates', type=str, 
                           help='Path to the JSON file containing coordinates to transform')

    args = argsparser.parse_args()
    config_data = read_config_file("clone/config/config.yaml")

    output_directory_path = Path(config_data['output_directory'])
    if not output_directory_path.exists():
        print(f"Output directory {output_directory_path} does not exist.")
        return
    
    if args.create_folder:
        if args.subjects:
            for subject_name in args.subjects:
                subject_folder = output_directory_path / subject_name
                subject = Subject(subject_folder)
            return
        else:
            print("Please provide the list of subject names.")
            return

    # Handle transform coordinates independently
    if args.transform_coordinates:
        if not args.subjects:
            print("Please provide the subject name(s) for coordinate transformation.")
            return
            
        for subject_name in args.subjects:
            subject_folder = output_directory_path / subject_name
            transform_mat = subject_folder / 'processed_tmp' / f'MNI_{subject_name}_T1.mat'

            if not transform_mat.exists():
                print(f"Transformation matrix not found for subject {subject_name}")
                continue
            
            output_json = Path(args.transform_coordinates).parent / f'MNI_{Path(args.transform_coordinates).stem}.json'
            transform_coordinates(args.transform_coordinates, transform_mat, output_json)
            print(f"Transformed coordinates saved to {output_json}")
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
                        print(f"{subject_name}: Finished running stage {stage_name}")
                    else:
                        print(f"{subject_name}: [ERROR] Stage {stage_name} not found.")

                print(f"{subject_name}: Finished running all stages")
                print(f"{subject_name}: You can now mark your electrodes using 3D slicer.")
            else:
                for stage in stages:
                    run_stage(stage, subject)

if __name__ == "__main__":
    main()
