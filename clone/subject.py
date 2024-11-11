from pathlib import Path
import re

class Subject:
    def __init__(self, folder_path):
        self.folder_path = Path(folder_path)
        self.postop_ct = self.folder_path / 'dcm' / 'postop' / 'ct'
        self.postop_mri = self.folder_path / 'dcm' / 'postop' / 'mri'
        self.preop_ct = self.folder_path / 'dcm' / 'preop' / 'ct'
        self.preop_mri = self.folder_path / 'dcm' / 'preop' / 'mri'
        self.processed_tmp = self.folder_path / 'processed_tmp'

        self.folder_path.mkdir(parents=True, exist_ok=True)
        self.postop_ct.mkdir(parents=True, exist_ok=True)
        self.postop_mri.mkdir(parents=True, exist_ok=True)
        self.preop_ct.mkdir(parents=True, exist_ok=True)
        self.preop_mri.mkdir(parents=True, exist_ok=True)
        self.processed_tmp.mkdir(parents=True, exist_ok=True)

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