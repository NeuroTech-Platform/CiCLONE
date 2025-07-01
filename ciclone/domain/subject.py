from pathlib import Path
import re
import shutil
from typing import Optional

class Subject:
    def __init__(self, folder_path):
        self.folder_path = Path(folder_path)
        self.documents = self.folder_path / 'documents'
        self.postop_ct = self.folder_path / 'images' / 'postop' / 'ct'
        self.postop_mri = self.folder_path / 'images' / 'postop' / 'mri'
        self.preop_ct = self.folder_path / 'images' / 'preop' / 'ct'
        self.preop_mri = self.folder_path / 'images' / 'preop' / 'mri'
        self.processed_tmp = self.folder_path / 'processed_tmp'
        self.pipeline_output = self.folder_path / 'pipeline_output'

        self.folder_path.mkdir(parents=True, exist_ok=True)
        self.documents.mkdir(parents=True, exist_ok=True)
        self.postop_ct.mkdir(parents=True, exist_ok=True)
        self.postop_mri.mkdir(parents=True, exist_ok=True)
        self.preop_ct.mkdir(parents=True, exist_ok=True)
        self.preop_mri.mkdir(parents=True, exist_ok=True)
        self.processed_tmp.mkdir(parents=True, exist_ok=True)
        self.pipeline_output.mkdir(parents=True, exist_ok=True)

    def get_subject_name(self):
        return self.folder_path.stem
    
    def get_file(self, suffix):
        if '.' in suffix:
            pattern = re.compile(rf'.*{suffix}$')
            files = [file for file in self.folder_path.rglob('*') if pattern.match(str(file))]
            return files[0] if files else None
        else:
            pattern = re.compile(rf'.*{suffix}\.nii(\.gz)?$')
            files = [file for file in self.folder_path.rglob('*') if pattern.match(str(file))]
            return files[0] if files else None
            
    def get_folder(self, suffix):
        pattern = re.compile(rf'.*{suffix}$')
        folders = [folder for folder in self.folder_path.rglob('*') if pattern.match(str(folder))]
        return folders[0] if folders else None
    
    def get_mni_transformation_matrix(self) -> Optional[Path]:
        """Get the MNI transformation matrix from pipeline_output."""
        if not self.pipeline_output.exists():
            return None
        
        subject_name = self.get_subject_name()
        mat_file = self.pipeline_output / f'MNI_{subject_name}_ref_brain.mat'
        return mat_file if mat_file.exists() else None
    
    def clear_processed_tmp(self):
        """Clear all files in the processed_tmp directory"""
        if self.processed_tmp.exists():
            # Check if directory has any contents
            if any(self.processed_tmp.iterdir()):
                shutil.rmtree(self.processed_tmp)
                self.processed_tmp.mkdir(parents=True, exist_ok=True)
                print(f"Cleared processed_tmp directory for subject {self.get_subject_name()}")
        else:
            print(f"Processed tmp directory for subject {self.get_subject_name()} does not exist")
