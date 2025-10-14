# subject_data = {
#     "name": "string",
#     "schema": "string",
#     "images": [  # List of image dictionaries
#         {
#             "file_path": "string",
#             "session": "Pre|Post",
#             "modality": "CT|MRI|PET",
#             "register_to": "optional_string"
#         }
#     ]
#     # Legacy fields (still supported for backward compatibility):
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
from typing import Optional, List, Dict, Tuple
from ciclone.domain.subject import Subject
from ciclone.services.io.subject_file_service import SubjectFileService
from ciclone.services.naming_service import NamingService
from ciclone.services.io.schema_processor import SchemaProcessor
from ciclone.models.image_entry import ImageEntry
from ciclone.models.import_job import ImportJob
from ciclone.services.registration_target_resolver import RegistrationTargetResolver

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
    def import_subject(output_directory, subject_data, naming_service: Optional[NamingService] = None) -> Tuple[Subject, List[ImportJob]]:
        """
        Import subject data according to the schema and create appropriate directory structure.

        Supports both new image list format and legacy field format for backward compatibility.
        Creates import jobs for all images (crop + optional registration as unified operations).

        Args:
            output_directory (str): Base directory where subject folders will be created.
            subject_data (dict): Dictionary containing subject data with the following keys:
                - name: Subject name
                - schema: Schema path (optional)
                - images: List of image dictionaries (new format) with keys:
                    - file_path: Path to image file
                    - session: "Pre" or "Post"
                    - modality: "CT", "MRI", or "PET"
                    - register_to: Optional registration target
                - Legacy fields (still supported):
                    - pre_ct, pre_mri, post_ct, post_mri

            naming_service (Optional[NamingService]): Service for file naming conventions.
                                                      If None, uses default naming.

        Returns:
            Tuple[Subject, List[ImportJob]]: The created Subject instance and list of import jobs
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

        # List to collect import jobs
        import_jobs = []

        # Check if we have the new images list format
        if "images" in subject_data and subject_data["images"]:
            # New format: import from images list and create import jobs
            import_jobs = SubjectImporter._import_images_from_list(
                subject_data["images"],
                subject,
                subject_name,
                naming_service
            )
        else:
            # Legacy format: import from individual fields (no import jobs for legacy format)
            SubjectImporter._import_file(subject_data.get("pre_ct"), subject.preop_ct, subject_name, "pre_ct", naming_service)
            SubjectImporter._import_file(subject_data.get("pre_mri"), subject.preop_mri, subject_name, "pre_mri", naming_service)
            SubjectImporter._import_file(subject_data.get("post_ct"), subject.postop_ct, subject_name, "post_ct", naming_service)
            SubjectImporter._import_file(subject_data.get("post_mri"), subject.postop_mri, subject_name, "post_mri", naming_service)

        return subject, import_jobs
    
    @staticmethod
    def _get_unique_filename(destination_dir: Path, base_filename: str) -> str:
        """
        Generate a unique filename by adding (N) suffix if file already exists.

        Args:
            destination_dir (Path): Destination directory
            base_filename (str): Base filename (including extension)

        Returns:
            str: Unique filename that doesn't conflict with existing files
        """
        destination_path = destination_dir / base_filename

        # If file doesn't exist, use the base filename
        if not destination_path.exists():
            return base_filename

        # Extract name and extension
        if base_filename.endswith('.nii.gz'):
            name_part = base_filename[:-7]  # Remove '.nii.gz'
            extension = '.nii.gz'
        else:
            name_part, extension = os.path.splitext(base_filename)

        # Find the next available number
        counter = 1
        while True:
            new_filename = f"{name_part} ({counter}){extension}"
            new_path = destination_dir / new_filename
            if not new_path.exists():
                return new_filename
            counter += 1

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

        # Get unique filename to avoid conflicts
        unique_filename = SubjectImporter._get_unique_filename(destination_dir, new_filename)

        # Copy file to destination with unique name
        destination_path = destination_dir / unique_filename
        shutil.copy2(source_path, destination_path)

        # Log differently if filename was changed due to conflict
        if unique_filename != new_filename:
            print(f"Imported {source_path} to {destination_path} (renamed to avoid conflict)")
        else:
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

    @staticmethod
    def _import_images_from_list(images_data: List[Dict], subject: Subject, subject_name: str, naming_service: NamingService) -> List[ImportJob]:
        """
        Import images from the new images list format and create import jobs.

        All images are automatically cropped using FSL robustfov. Images with registration
        targets will be registered after cropping. Each ImportJob represents the complete
        workflow for a single image (crop + optional registration).

        Args:
            images_data: List of image dictionaries from subject_data["images"]
            subject: Subject instance with directory structure
            subject_name: Name of the subject
            naming_service: Service for file naming conventions

        Returns:
            List[ImportJob]: List of unified import jobs
        """
        # Counter for multiple images of the same session/modality
        counters = {}
        # Track image info for import job creation
        image_info_list = []
        import_jobs = []

        # Phase 1: Collect image information and generate output paths
        for img_data in images_data:
            # Convert dict to ImageEntry if needed
            if isinstance(img_data, dict):
                image_entry = ImageEntry.from_dict(img_data)
            else:
                image_entry = img_data

            # Determine destination directory based on session and modality
            session_dir = subject.preop_ct.parent if image_entry.session == "Pre" else subject.postop_ct.parent
            modality_dir = session_dir / image_entry.modality.lower()

            # Ensure directory exists
            modality_dir.mkdir(parents=True, exist_ok=True)

            # Track multiple images of same type
            counter_key = f"{image_entry.session}_{image_entry.modality}"
            if counter_key not in counters:
                counters[counter_key] = 0
            else:
                counters[counter_key] += 1

            # Create identifier for this image
            count_same_type = counters[counter_key] + 1  # +1 because counter is 0-indexed
            identifier = f"[{image_entry.session}] {image_entry.modality}"
            if count_same_type > 1:
                identifier += f" #{count_same_type}"

            # Generate output filename based on modality and naming conventions
            session, modality = image_entry.session, image_entry.modality
            source_path = Path(image_entry.file_path)

            if session == "Pre" and modality == "MRI":
                mri_modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
                base_name = naming_service.get_pre_mri_filename(subject_name, mri_modality)
            elif session == "Post" and modality == "MRI":
                mri_modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
                base_name = naming_service.get_post_mri_filename(subject_name, mri_modality)
            elif session == "Pre" and modality == "CT":
                base_name = naming_service.get_pre_ct_filename(subject_name)
            elif session == "Post" and modality == "CT":
                base_name = naming_service.get_post_ct_filename(subject_name)
            elif modality == "PET":
                base_name = f"{subject_name}_{session}_{modality}"
            else:
                # Fallback to generic naming
                base_name = f"{subject_name}_{session}_{modality}"

            output_filename = f"{base_name}.nii.gz"
            output_path = modality_dir / output_filename

            # Store image info
            image_info_list.append({
                'source_path': str(source_path),
                'output_path': str(output_path),
                'identifier': identifier,
                'image_entry': image_entry,
                'destination_dir': modality_dir,
                'subject_name': subject_name
            })

        # Phase 2: Create ImportJob objects and separate into two groups
        # Group 1: Images WITHOUT registration (process first)
        # Group 2: Images WITH registration (process after their targets exist)
        import tempfile
        temp_dir = Path(tempfile.gettempdir())

        jobs_without_registration = []
        jobs_with_registration = []

        for img_info in image_info_list:
            image_entry = img_info['image_entry']
            identifier = img_info['identifier']
            will_be_registered = image_entry.register_to and image_entry.register_to != "None"

            if will_be_registered:
                # This image needs registration - will be processed AFTER non-registration images
                # Generate temp crop path for the cropped intermediate file
                temp_filename = f"crop_temp_{subject_name}_{identifier.replace(' ', '_').replace('[', '').replace(']', '')}_{os.getpid()}.nii.gz"
                temp_crop_path = str(temp_dir / temp_filename)

                # Resolve registration target from the output paths we're going to create
                # (these will exist by the time registration jobs run)
                target_identifier = image_entry.register_to
                registration_target_path = RegistrationTargetResolver.resolve_target(
                    subject,
                    target_identifier,
                    [{'file_path': info['output_path'], 'session': info['image_entry'].session,
                      'modality': info['image_entry'].modality, 'register_to': None}
                     for info in image_info_list]
                )

                if not registration_target_path:
                    print(f"Warning: Could not resolve registration target '{target_identifier}' for {identifier}")
                    print(f"  Target '{target_identifier}' may not be in current batch or existing files")
                    # Skip registration if target can't be resolved
                    will_be_registered = False
                    registration_target_identifier = None
                    temp_crop_path = None
                else:
                    registration_target_identifier = target_identifier
                    print(f"Will coregister {identifier} to {target_identifier} (target: {registration_target_path})")

            else:
                # No registration needed
                temp_crop_path = None
                registration_target_path = None
                registration_target_identifier = None
                print(f"Will import {identifier} (crop only)")

            # Create unified ImportJob
            import_job = ImportJob(
                subject_name=subject_name,
                source_image_path=img_info['source_path'],
                output_path=img_info['output_path'],
                image_identifier=img_info['identifier'],
                needs_crop=True,  # Always crop in import workflow
                registration_target_path=registration_target_path if will_be_registered else None,
                registration_target_identifier=registration_target_identifier,
                temp_crop_path=temp_crop_path
            )

            # Sort into appropriate list
            if will_be_registered:
                jobs_with_registration.append(import_job)
            else:
                jobs_without_registration.append(import_job)

        # Phase 3: Combine jobs in correct order
        # Process non-registration jobs FIRST, then registration jobs
        # This ensures registration targets exist before they're needed
        import_jobs = jobs_without_registration + jobs_with_registration

        if jobs_without_registration and jobs_with_registration:
            print(f"Import order: {len(jobs_without_registration)} crop-only jobs, then {len(jobs_with_registration)} coregistration jobs")

        return import_jobs

    @staticmethod
    def _import_image_entry(image_entry: ImageEntry, destination_dir: Path, subject_name: str,
                            file_type: str, naming_service: NamingService, index: int = 0) -> Optional[Path]:
        """
        Import a single image entry to the appropriate destination directory.

        Args:
            image_entry: ImageEntry object with image metadata
            destination_dir: Destination directory
            subject_name: Name of the subject
            file_type: Type identifier (e.g., "pre_ct", "post_mri")
            naming_service: Service for file naming conventions
            index: Index for multiple images of same type (0 for first)

        Returns:
            Optional[Path]: Path to the imported file, or None if import failed
        """
        source_path = Path(image_entry.file_path)
        if not source_path.exists():
            print(f"Warning: Source file {source_path} does not exist")
            return None

        # Determine file extension
        file_extension = source_path.suffix
        if source_path.name.endswith('.nii.gz'):
            file_extension = '.nii.gz'

        # Generate base filename based on modality and naming conventions
        session, modality = image_entry.session, image_entry.modality

        if session == "Pre" and modality == "CT":
            base_filename = f"{naming_service.get_pre_ct_filename(subject_name)}{file_extension}"
        elif session == "Post" and modality == "CT":
            base_filename = f"{naming_service.get_post_ct_filename(subject_name)}{file_extension}"
        elif session == "Pre" and modality == "MRI":
            # Detect MRI modality from filename and/or header
            mri_modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
            base_filename = f"{naming_service.get_pre_mri_filename(subject_name, mri_modality)}{file_extension}"
        elif session == "Post" and modality == "MRI":
            # Detect MRI modality from filename and/or header
            mri_modality = SubjectImporter._detect_mri_modality(source_path.name, str(source_path))
            base_filename = f"{naming_service.get_post_mri_filename(subject_name, mri_modality)}{file_extension}"
        elif modality == "PET":
            # Simple PET naming (no specific naming service method yet)
            base_filename = f"{subject_name}_{session}_{modality}{file_extension}"
        else:
            # Fallback to original filename
            base_filename = source_path.name

        # Get unique filename to avoid conflicts
        unique_filename = SubjectImporter._get_unique_filename(destination_dir, base_filename)

        # Copy file to destination with unique name
        destination_path = destination_dir / unique_filename
        shutil.copy2(source_path, destination_path)

        # Log the import
        if unique_filename != base_filename:
            print(f"Imported [{session}] {modality}: {source_path} → {destination_path} (renamed to avoid conflict)")
        else:
            print(f"Imported [{session}] {modality}: {source_path} → {destination_path}")

        return destination_path
