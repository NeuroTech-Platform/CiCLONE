import os
import argparse
from pathlib import Path
from clone.operations import crop_image, move_image, coregister_images, subtract_image, threshold_image, apply_transformation2image, extract_brain, mask_image
from clone.utility import read_config_file
from clone.subject import Subject

def run_operation(operation, subject: Subject):    
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
    elif operation['type'] == 'mask':
        mask_image(*files)

def run_stage(stage, subject):
    print(f"Running stage: {stage['name']}")
    for operation in stage['operations']:
        run_operation(operation, subject)

def main():
    argsparser = argparse.ArgumentParser(description='Process some medical imaging data.')
    argsparser.add_argument('--subjects', nargs='+', help='List of subjects.')
    argsparser.add_argument('--create-folder', action='store_true', help='Create folder for the subject(s) provided in the list.')
    argsparser.add_argument('--stage', help='Name of the stage to run. If not provided, all stages will be run.')

    args = argsparser.parse_args()
    config_data = read_config_file("config/config.yaml")

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

    if args.subjects:
        for subject_name in args.subjects:
            subject_folder = output_directory_path / subject_name
            subject = Subject(subject_folder)

            stages = config_data['stages']
            if args.stage:
                stage = next((stage for stage in stages if stage['name'] == args.stage), None)
                if stage:
                    run_stage(stage, subject)
                else:
                    print(f"Stage {args.stage} not found.")
            else:
                for stage in stages:
                    run_stage(stage, subject)

if __name__ == "__main__":
    main()
