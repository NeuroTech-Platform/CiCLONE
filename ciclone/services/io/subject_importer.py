# subject_data = {
#     "name": "string",
#     "schema": "string",
#     "pre_ct": "string",
#     "pre_mri": "string",
#     "post_ct": "string",
#     "post_mri": "string"
# }

import os
import shutil
from pathlib import Path
from ciclone.domain.subject import Subject

class SubjectImporter:
    @staticmethod
    def import_subject(output_directory, subject_data):
        """
        Import subject data according to the schema and create appropriate directory structure.
        
        Args:
            output_directory (str): Base directory where subject folders will be created.
            subject_data (dict): Dictionary containing subject data with the following keys:
                - name: Subject name
                - schema: Schema version (not used currently)
                - pre_ct: Path to preoperative CT file
                - pre_mri: Path to preoperative MRI file
                - post_ct: Path to postoperative CT file
                - post_mri: Path to postoperative MRI file
                
        Returns:
            Subject: The created Subject instance
        """
        if not subject_data.get("name"):
            raise ValueError("Subject name must be provided")
        
        # Create subject folder
        subject_path = Path(output_directory) / subject_data["name"]
        subject = Subject(subject_path)
        
        # Import files if they exist
        SubjectImporter._import_file(subject_data.get("pre_ct"), subject.preop_ct)
        SubjectImporter._import_file(subject_data.get("pre_mri"), subject.preop_mri)
        SubjectImporter._import_file(subject_data.get("post_ct"), subject.postop_ct)
        SubjectImporter._import_file(subject_data.get("post_mri"), subject.postop_mri)
        
        return subject
    
    @staticmethod
    def _import_file(source_path, destination_dir):
        """
        Import a file to the appropriate destination directory.
        
        Args:
            source_path (str): Path to the source file
            destination_dir (Path): Destination directory
        """
        if not source_path:
            return
        
        source_path = Path(source_path)
        if not source_path.exists():
            print(f"Warning: Source file {source_path} does not exist")
            return
        
        # Copy file to destination
        destination_path = destination_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        print(f"Imported {source_path} to {destination_path}")
