from pathlib import Path
import shutil
from typing import Optional


class SubjectFileService:
    """Service for handling Subject file operations."""
    
    @staticmethod
    def create_subject_directories(subject_path: Path) -> None:
        """Create all required directories for a subject."""
        folder_path = Path(subject_path)
        documents = folder_path / 'documents'
        postop_ct = folder_path / 'images' / 'postop' / 'ct'
        postop_mri = folder_path / 'images' / 'postop' / 'mri'
        preop_ct = folder_path / 'images' / 'preop' / 'ct'
        preop_mri = folder_path / 'images' / 'preop' / 'mri'
        processed_tmp = folder_path / 'processed_tmp'
        pipeline_output = folder_path / 'pipeline_output'
        
        # Create all directories
        folder_path.mkdir(parents=True, exist_ok=True)
        documents.mkdir(parents=True, exist_ok=True)
        postop_ct.mkdir(parents=True, exist_ok=True)
        postop_mri.mkdir(parents=True, exist_ok=True)
        preop_ct.mkdir(parents=True, exist_ok=True)
        preop_mri.mkdir(parents=True, exist_ok=True)
        processed_tmp.mkdir(parents=True, exist_ok=True)
        pipeline_output.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def clear_processed_tmp(subject_path: Path) -> None:
        """Clear all files in the processed_tmp directory."""
        processed_tmp = subject_path / 'processed_tmp'
        
        if processed_tmp.exists():
            # Check if directory has any contents
            if any(processed_tmp.iterdir()):
                shutil.rmtree(processed_tmp)
                processed_tmp.mkdir(parents=True, exist_ok=True)
                print(f"Cleared processed_tmp directory for subject {subject_path.stem}")
        else:
            print(f"Processed tmp directory for subject {subject_path.stem} does not exist")
    
    @staticmethod
    def get_mni_transformation_matrix(subject_path: Path) -> Optional[Path]:
        """Get the MNI transformation matrix from pipeline_output."""
        pipeline_output = subject_path / 'pipeline_output'
        
        if not pipeline_output.exists():
            return None
        
        subject_name = subject_path.stem
        mat_file = pipeline_output / f'MNI_{subject_name}_ref.mat'
        return mat_file if mat_file.exists() else None