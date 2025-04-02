import os
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
