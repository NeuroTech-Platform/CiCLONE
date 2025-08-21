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
import re
from pathlib import Path
import nibabel as nib
import numpy as np
from typing import Optional
from ciclone.domain.subject import Subject
from ciclone.services.io.subject_file_service import SubjectFileService
from ciclone.services.naming_service import NamingService
from ciclone.services.io.schema_processor import SchemaProcessor

class SubjectImporter:
    @staticmethod
    def _detect_mri_modality_from_header(filepath):
        """
        Try to detect MRI modality from NIFTI header metadata.
        
        Args:
            filepath (str): Path to the NIFTI file
            
        Returns:
            str or None: Detected modality or None if unable to determine
        """
        try:
            # Load NIFTI file
            img = nib.load(filepath)
            header = img.header
            
            # Get description field which often contains sequence info
            descrip = header.get('descrip', b'')
            
            # Handle bytes or array
            if isinstance(descrip, bytes):
                descrip_str = descrip.decode('utf-8', errors='ignore').strip()
            elif isinstance(descrip, np.ndarray):
                descrip_str = descrip.tobytes().decode('utf-8', errors='ignore').strip().rstrip('\x00')
            else:
                descrip_str = str(descrip)
            
            descrip_lower = descrip_str.lower()
            
            # Check for modality patterns in description
            if any(x in descrip_lower for x in ['t1', 'mprage', 'spgr', r'ir\gr', '3d ir']):
                return 'T1'
            elif any(x in descrip_lower for x in ['t2', 'tse', 'fse']) and 'flair' not in descrip_lower:
                return 'T2'
            elif 'flair' in descrip_lower:
                return 'FLAIR'
            elif any(x in descrip_lower for x in ['dwi', 'diffusion', 'dti']):
                return 'DWI'
            elif any(x in descrip_lower for x in ['swi', 'susceptibility']):
                return 'SWI'
            elif any(x in descrip_lower for x in ['tof', 'time of flight']):
                return 'TOF'
            elif any(x in descrip_lower for x in ['pd', 'proton']):
                return 'PDW'
            elif any(x in descrip_lower for x in ['bold', 'functional', 'fmri']):
                return 'BOLD'
            elif any(x in descrip_lower for x in ['asl', 'arterial']):
                return 'ASL'
                
        except Exception as e:
            # If we can't read the header, return None
            print(f"Warning: Could not read NIFTI header from {filepath}: {e}")
            
        return None
    
    @staticmethod
    def _detect_mri_modality(filename, filepath=None):
        """
        Detect MRI modality from filename patterns and/or NIFTI header.
        
        Args:
            filename (str): The filename to analyze
            filepath (str, optional): Full path to the file for reading header
            
        Returns:
            str: Detected modality (T1, T2, FLAIR, DWI, etc.) or 'MRI' if unknown
        """
        filename_lower = filename.lower()
        
        # Define patterns for different MRI modalities
        modality_patterns = {
            'T1': [r't1', r't1w', r't1_weighted', r't1-weighted', r'mprage'],
            'T2': [r't2', r't2w', r't2_weighted', r't2-weighted'],
            'FLAIR': [r'flair', r't2_flair', r't2-flair'],
            'DWI': [r'dwi', r'diffusion', r'diff'],
            'DTI': [r'dti', r'tensor'],
            'SWI': [r'swi', r'susceptibility'],
            'TOF': [r'tof', r'time_of_flight', r'time-of-flight'],
            'PDW': [r'pd', r'pdw', r'proton_density', r'proton-density'],
            'BOLD': [r'bold', r'func', r'functional'],
            'ASL': [r'asl', r'arterial_spin', r'arterial-spin']
        }
        
        # First check filename patterns
        for modality, patterns in modality_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return modality
        
        # If no filename match and filepath provided, try to read header
        if filepath and os.path.exists(filepath):
            header_modality = SubjectImporter._detect_mri_modality_from_header(filepath)
            if header_modality:
                return header_modality
        
        # Default fallback
        return 'MRI'

    @staticmethod
    def import_subject(output_directory, subject_data, naming_service: Optional[NamingService] = None):
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
            naming_service (Optional[NamingService]): Service for file naming conventions.
                                                      If None, uses default naming.
                
        Returns:
            Subject: The created Subject instance
        """
        if not subject_data.get("name"):
            raise ValueError("Subject name must be provided")
        
        # Create or use provided naming service
        if naming_service is None:
            naming_service = NamingService()
        
        # Create subject folder
        subject_path = Path(output_directory) / subject_data["name"]
        SubjectFileService.create_subject_directories(subject_path)
        subject = Subject(subject_path)
        
        subject_name = subject_data["name"]
        
        # Import schema files if they exist (handle multiple files and PowerPoint conversion)
        SubjectImporter._import_schema_files(subject_data, subject.documents)
        
        # Import files if they exist with appropriate renaming
        SubjectImporter._import_file(subject_data.get("pre_ct"), subject.preop_ct, subject_name, "pre_ct", naming_service)
        SubjectImporter._import_file(subject_data.get("pre_mri"), subject.preop_mri, subject_name, "pre_mri", naming_service)
        SubjectImporter._import_file(subject_data.get("post_ct"), subject.postop_ct, subject_name, "post_ct", naming_service)
        SubjectImporter._import_file(subject_data.get("post_mri"), subject.postop_mri, subject_name, "post_mri", naming_service)
        
        return subject
    
    @staticmethod
    def _import_file(source_path, destination_dir, subject_name, file_type, naming_service: NamingService):
        """
        Import a file to the appropriate destination directory with custom naming.
        
        Args:
            source_path (str): Path to the source file
            destination_dir (Path): Destination directory
            subject_name (str): Name of the subject
            file_type (str): Type of file (pre_ct, post_ct, pre_mri, post_mri)
            naming_service (NamingService): Service for file naming conventions
        """
        if not source_path:
            return
        
        source_path = Path(source_path)
        if not source_path.exists():
            print(f"Warning: Source file {source_path} does not exist")
            return
        
        # Determine the new filename based on file type and naming conventions
        file_extension = source_path.suffix
        if source_path.name.endswith('.nii.gz'):
            file_extension = '.nii.gz'
        
        if file_type == "pre_ct":
            new_filename = f"{naming_service.get_pre_ct_filename(subject_name)}{file_extension}"
        elif file_type == "post_ct":
            new_filename = f"{naming_service.get_post_ct_filename(subject_name)}{file_extension}"
        elif file_type == "pre_mri":
            # Detect MRI modality from filename and/or header
            modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
            new_filename = f"{naming_service.get_pre_mri_filename(subject_name, modality)}{file_extension}"
        elif file_type == "post_mri":
            # Detect MRI modality from filename and/or header
            modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
            new_filename = f"{naming_service.get_post_mri_filename(subject_name, modality)}{file_extension}"
        else:
            # Fallback to original filename if type is unknown
            new_filename = source_path.name
        
        # Copy file to destination with new name
        destination_path = destination_dir / new_filename
        shutil.copy2(source_path, destination_path)
        print(f"Imported {source_path} to {destination_path}")

    @staticmethod
    def _import_schema_files(subject_data, subject_path):
        """
        Import schema files with support for multiple files and PowerPoint conversion.
        
        Args:
            subject_data (dict): Subject data containing schema information
            subject_path (Path): Path to the subject directory
        """
        # Get schema files from subject data
        schema_files = []
        
        # Check for both legacy schema field and new schema_files field
        if "schema_files" in subject_data and subject_data["schema_files"]:
            schema_files = subject_data["schema_files"]
        elif "schema" in subject_data and subject_data["schema"]:
            # Handle legacy comma-separated format
            schema_str = subject_data["schema"]
            schema_files = [path.strip() for path in schema_str.split(',') if path.strip()]
        
        if not schema_files:
            return
            
        try:
            # Process schema files (handles both images and PowerPoint conversion)
            success, processed_files, error_message = SchemaProcessor.process_schema_files(
                schema_files, str(subject_path), subject_data["name"]
            )
            
            if success:
                file_count = len(processed_files)
                print(f"Successfully processed {file_count} schema file(s) for subject '{subject_data['name']}'")
                
                if error_message:
                    print(f"Schema processing warnings: {error_message}")
            else:
                print(f"Schema processing failed: {error_message}")
                
        except Exception as e:
            print(f"Error processing schema files: {str(e)}")
