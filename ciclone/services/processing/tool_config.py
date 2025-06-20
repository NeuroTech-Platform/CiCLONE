import os
import subprocess
import re
from pathlib import Path


class ToolConfig:
    """Configuration manager for neuroimaging toolboxes (FSL, FreeSurfer, etc.)."""
    
    def __init__(self):
        self.fsl_bin_dir = None
        self.freesurfer_bin_dir = None
        self._initialized = False
    
    def initialize(self):
        """Initialize tool paths based on environment validation."""
        if self._initialized:
            return
        
        # Configure FSL
        if self._check_fsl_environment():
            self.fsl_bin_dir = os.path.join(os.environ['FSLDIR'], 'bin')
        
        # Configure FreeSurfer
        if self._check_freesurfer_environment():
            self.freesurfer_bin_dir = os.path.join(os.environ['FREESURFER_HOME'], 'bin')
        
        self._initialized = True
    
    def get_fsl_tool_path(self, tool_name: str) -> str:
        """
        Get the full path for an FSL tool.
        
        Args:
            tool_name: Name of the FSL tool (e.g., 'flirt', 'fslmaths')
        
        Returns:
            Full path to tool or just tool name if FSL not configured
        """
        self.initialize()
        if self.fsl_bin_dir:
            return os.path.join(self.fsl_bin_dir, tool_name)
        return tool_name
    
    def get_freesurfer_tool_path(self, tool_name: str) -> str:
        """
        Get the full path for a FreeSurfer tool.
        
        Args:
            tool_name: Name of the FreeSurfer tool (e.g., 'recon-all', 'mri_convert')
        
        Returns:
            Full path to tool or just tool name if FreeSurfer not configured
        """
        self.initialize()
        if self.freesurfer_bin_dir:
            return os.path.join(self.freesurfer_bin_dir, tool_name)
        return tool_name
    
    def _check_fsl_environment(self) -> bool:
        """Check if FSL is properly configured."""
        fsl_dir = os.environ.get('FSLDIR')
        if not fsl_dir:
            return False
        
        fsl_path = Path(fsl_dir)
        if not fsl_path.exists():
            return False
        
        # Check if bin directory exists
        bin_dir = fsl_path / "bin"
        if not bin_dir.exists():
            return False
        
        return True
    
    def _check_freesurfer_environment(self) -> bool:
        """Check if FreeSurfer is properly configured."""
        fs_home = os.environ.get('FREESURFER_HOME')
        if not fs_home:
            return False
        
        fs_path = Path(fs_home)
        if not fs_path.exists():
            return False
        
        # Check if bin directory exists
        bin_dir = fs_path / "bin"
        if not bin_dir.exists():
            return False
        
        return True
    
    def _source_setup_script(self, script_path: Path) -> bool:
        """Source a setup script and update environment variables."""
        try:
            command = f". {script_path} && env"
            result = subprocess.run(['bash', '-c', command], 
                                  capture_output=True, text=True, check=True)
            
            # Update environment with relevant variables
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key in ['FSLDIR', 'FREESURFER_HOME', 'SUBJECTS_DIR', 'PATH', 'LD_LIBRARY_PATH']:
                        os.environ[key] = value
            return True
        except subprocess.CalledProcessError:
            return False
    
    def setup_fsl_environment(self) -> bool:
        """Attempt to setup FSL environment."""
        common_paths = ["/usr/local/fsl", "/opt/fsl", "/usr/share/fsl"]
        
        for fsl_path in common_paths:
            setup_script = Path(fsl_path) / "etc" / "fslconf" / "fsl.sh"
            if setup_script.exists() and self._source_setup_script(setup_script):
                if self._check_fsl_environment():
                    return True
        return False
    
    def setup_freesurfer_environment(self) -> bool:
        """Attempt to setup FreeSurfer environment."""
        fs_home = os.environ.get('FREESURFER_HOME')
        
        if fs_home:
            # Use existing FREESURFER_HOME
            setup_script = Path(fs_home) / "SetUpFreeSurfer.sh"
            if setup_script.exists() and self._source_setup_script(setup_script):
                return self._check_freesurfer_environment()
        else:
            # Search common installation paths
            base_paths = ["/usr/local/freesurfer", "/opt/freesurfer", "/Applications/freesurfer"]
            
            for base_path in base_paths:
                base_dir = Path(base_path)
                if not base_dir.exists():
                    continue
                    
                # Look for versioned directories (format: X.Y.Z)
                version_pattern = re.compile(r'^\d+\.\d+(\.\d+)?$')
                
                for item in base_dir.iterdir():
                    if item.is_dir() and version_pattern.match(item.name):
                        setup_script = item / "SetUpFreeSurfer.sh"
                        if setup_script.exists() and self._source_setup_script(setup_script):
                            if self._check_freesurfer_environment():
                                return True
        
        return False
    
    def validate_environment(self) -> tuple[bool, list[str]]:
        """
        Validate FSL and FreeSurfer environments.
        Attempt automatic setup if not configured.
        
        Returns:
            Tuple of (all_ok, error_messages)
        """
        errors = []
        
        # Check and setup FSL
        if not self._check_fsl_environment():
            print("FSL not configured, attempting setup...")
            if self.setup_fsl_environment():
                print("FSL setup successful")
            else:
                errors.append("FSL: Not properly configured")
        else:
            print(f"FSL: Configured at {os.environ.get('FSLDIR')}")
        
        # Check and setup FreeSurfer
        if not self._check_freesurfer_environment():
            print("FreeSurfer not configured, attempting setup...")
            if self.setup_freesurfer_environment():
                print("FreeSurfer setup successful")
            else:
                errors.append("FreeSurfer: Not properly configured")
        else:
            print(f"FreeSurfer: Configured at {os.environ.get('FREESURFER_HOME')}")
        
        return (len(errors) == 0), errors


# Global instance
tool_config = ToolConfig() 