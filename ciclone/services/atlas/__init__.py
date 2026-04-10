"""
Atlas services for FreeSurfer-based electrode labeling.
"""

from ciclone.services.atlas.atlas_lookup_service import AtlasLookupService
from ciclone.services.atlas.color_lut_parser import parse_freesurfer_color_lut

__all__ = ['AtlasLookupService', 'parse_freesurfer_color_lut']
