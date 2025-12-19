"""
Model management utilities for SAM-based detection.

Handles model download, caching, and configuration.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import warnings


def get_default_model_dir() -> Path:
    """Get the default directory for storing model checkpoints."""
    # Use XDG_CACHE_HOME or fallback to ~/.cache
    cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    model_dir = Path(cache_home) / "ciclone" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def get_model_path(model_type: str) -> Optional[Path]:
    """
    Get the path to a model checkpoint.
    
    Args:
        model_type: Model variant (vit_b, vit_l, vit_h, medsam, mobilesam)
        
    Returns:
        Path to checkpoint file, or None if not found
    """
    model_dir = get_default_model_dir()
    
    # Common checkpoint filenames
    checkpoint_names = {
        "vit_b": "sam_vit_b_01ec64.pth",
        "vit_l": "sam_vit_l_0b3195.pth",
        "vit_h": "sam_vit_h_4b8939.pth",
        "medsam": "medsam_vit_b.pth",
        "mobilesam": "mobile_sam.pt",
    }
    
    if model_type not in checkpoint_names:
        return None
    
    checkpoint_path = model_dir / checkpoint_names[model_type]
    
    if checkpoint_path.exists():
        return checkpoint_path
    
    return None


def download_model(
    model_type: str,
    destination: Optional[Path] = None,
    show_progress: bool = True
) -> Optional[Path]:
    """
    Download a SAM model checkpoint.
    
    Args:
        model_type: Model variant to download
        destination: Download destination (default: cache dir)
        show_progress: Show download progress
        
    Returns:
        Path to downloaded checkpoint, or None if failed
    """
    try:
        import urllib.request
        from tqdm import tqdm
    except ImportError:
        warnings.warn("tqdm not available for progress display")
        show_progress = False
    
    model_urls = {
        "vit_b": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "vit_l": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
        "vit_h": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
    }
    
    if model_type not in model_urls:
        warnings.warn(
            f"No download URL for {model_type}. "
            "Please download manually and provide checkpoint_path."
        )
        return None
    
    url = model_urls[model_type]
    
    if destination is None:
        destination = get_default_model_dir()
    
    filename = url.split("/")[-1]
    filepath = destination / filename
    
    if filepath.exists():
        return filepath
    
    try:
        print(f"Downloading {model_type} model from {url}...")
        
        if show_progress:
            # Download with progress bar
            class DownloadProgressBar(tqdm):
                def update_to(self, b=1, bsize=1, tsize=None):
                    if tsize is not None:
                        self.total = tsize
                    self.update(b * bsize - self.n)
            
            with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=filename) as t:
                urllib.request.urlretrieve(url, filepath, reporthook=t.update_to)
        else:
            urllib.request.urlretrieve(url, filepath)
        
        print(f"Model saved to {filepath}")
        return filepath
        
    except Exception as e:
        warnings.warn(f"Failed to download model: {e}")
        return None


def get_model_info(model_type: str) -> Dict[str, Any]:
    """Get information about a model variant."""
    from ciclone.services.detection.sam_detector import SAMElectrodeDetector
    
    info = SAMElectrodeDetector.MODEL_INFO.get(model_type, {})
    
    # Check if model is available locally
    local_path = get_model_path(model_type)
    info["is_downloaded"] = local_path is not None
    info["local_path"] = str(local_path) if local_path else None
    
    return info


def list_downloaded_models() -> Dict[str, Path]:
    """List all downloaded model checkpoints."""
    model_dir = get_default_model_dir()
    
    models = {}
    for checkpoint in model_dir.glob("*.pth"):
        # Infer model type from filename
        name = checkpoint.stem
        if "vit_b" in name:
            models["vit_b"] = checkpoint
        elif "vit_l" in name:
            models["vit_l"] = checkpoint
        elif "vit_h" in name:
            models["vit_h"] = checkpoint
        elif "medsam" in name:
            models["medsam"] = checkpoint
    
    for checkpoint in model_dir.glob("*.pt"):
        name = checkpoint.stem
        if "mobile" in name.lower():
            models["mobilesam"] = checkpoint
    
    return models
