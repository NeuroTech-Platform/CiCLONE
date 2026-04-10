"""
Parser for FreeSurfer color lookup table (FreeSurferColorLUT.txt).
"""

import os
from pathlib import Path
from typing import Dict, Optional

from ciclone.models.atlas_model import AtlasLabel


def _determine_hemisphere(name: str) -> str:
    """
    Determine hemisphere from FreeSurfer label name.

    Args:
        name: Label name from FreeSurferColorLUT.txt

    Returns:
        'L' for left hemisphere, 'R' for right hemisphere, '' for midline/bilateral
    """
    left_indicators = ['Left-', 'ctx-lh-', 'ctx_lh_', 'lh-', 'lh_', 'wm-lh-', 'wm_lh_']
    right_indicators = ['Right-', 'ctx-rh-', 'ctx_rh_', 'rh-', 'rh_', 'wm-rh-', 'wm_rh_']

    for indicator in left_indicators:
        if name.startswith(indicator) or f'-{indicator}' in name:
            return 'L'

    for indicator in right_indicators:
        if name.startswith(indicator) or f'-{indicator}' in name:
            return 'R'

    return ''


def _create_abbreviation(name: str) -> str:
    """
    Create a short abbreviation from a FreeSurfer label name.

    Args:
        name: Full label name

    Returns:
        Abbreviated name for compact display
    """
    # Common abbreviation mappings
    abbreviations = {
        'Hippocampus': 'Hipp',
        'Amygdala': 'Amyg',
        'Thalamus': 'Thal',
        'Caudate': 'Caud',
        'Putamen': 'Put',
        'Pallidum': 'Pall',
        'Accumbens': 'Acc',
        'VentralDC': 'VDC',
        'Cerebellum': 'Cbl',
        'Brain-Stem': 'BStem',
        'Cerebral-White-Matter': 'WM',
        'Cerebral-Cortex': 'Ctx',
        'Lateral-Ventricle': 'LatVent',
        'Inf-Lat-Vent': 'InfLatVent',
        '3rd-Ventricle': '3rdVent',
        '4th-Ventricle': '4thVent',
        'CSF': 'CSF',
        'choroid-plexus': 'ChPlx',
        'Optic-Chiasm': 'OptCh',
        'CC_Posterior': 'CC-Post',
        'CC_Mid_Posterior': 'CC-MidP',
        'CC_Central': 'CC-Cent',
        'CC_Mid_Anterior': 'CC-MidA',
        'CC_Anterior': 'CC-Ant',
        # Cortical regions (common ones)
        'superiorfrontal': 'SupFr',
        'rostralmiddlefrontal': 'RosMidFr',
        'caudalmiddlefrontal': 'CauMidFr',
        'parsopercularis': 'ParsOp',
        'parstriangularis': 'ParsTri',
        'parsorbitalis': 'ParsOrb',
        'lateralorbitofrontal': 'LatOrbFr',
        'medialorbitofrontal': 'MedOrbFr',
        'precentral': 'PreC',
        'postcentral': 'PostC',
        'superiorparietal': 'SupPar',
        'inferiorparietal': 'InfPar',
        'supramarginal': 'SupraMarg',
        'precuneus': 'PreCun',
        'cuneus': 'Cun',
        'pericalcarine': 'PeriCalc',
        'lateraloccipital': 'LatOcc',
        'lingual': 'Ling',
        'fusiform': 'Fus',
        'parahippocampal': 'ParaHipp',
        'entorhinal': 'Ent',
        'temporalpole': 'TempPole',
        'inferiortemporal': 'InfTemp',
        'middletemporal': 'MidTemp',
        'superiortemporal': 'SupTemp',
        'transversetemporal': 'TransTemp',
        'bankssts': 'BanksSTS',
        'insula': 'Ins',
        'isthmuscingulate': 'IsthCing',
        'posteriorcingulate': 'PostCing',
        'caudalanteriorcingulate': 'CauAntCing',
        'rostralanteriorcingulate': 'RosAntCing',
        'frontalpole': 'FrPole',
    }

    # Check for direct matches in the name
    for full, abbrev in abbreviations.items():
        if full.lower() in name.lower():
            return abbrev

    # For cortical labels, try to extract region name
    for prefix in ['ctx-lh-', 'ctx-rh-', 'ctx_lh_', 'ctx_rh_']:
        if name.startswith(prefix):
            region = name[len(prefix):]
            if region.lower() in [k.lower() for k in abbreviations.keys()]:
                for k, v in abbreviations.items():
                    if k.lower() == region.lower():
                        return v
            # If not found, use first 6 chars
            return region[:6].capitalize()

    # For other labels, use first word or truncate
    parts = name.replace('-', ' ').replace('_', ' ').split()
    if len(parts) > 1:
        # Take first letter of each word
        abbrev = ''.join(p[0].upper() for p in parts[:4])
        return abbrev

    return name[:6]


def parse_freesurfer_color_lut(lut_path: Path) -> Dict[int, AtlasLabel]:
    """
    Parse FreeSurfer color lookup table file.

    The file format is:
    # Comment lines start with #
    # Label_ID  Label_Name  R  G  B  A
    0           Unknown     0  0  0  0
    1           Left-Cerebral-Exterior  70  130  180  0
    ...

    Args:
        lut_path: Path to FreeSurferColorLUT.txt

    Returns:
        Dictionary mapping label IDs to AtlasLabel objects

    Raises:
        FileNotFoundError: If the LUT file doesn't exist
        ValueError: If the file format is invalid
    """
    if not lut_path.exists():
        raise FileNotFoundError(f"FreeSurfer color LUT not found: {lut_path}")

    labels: Dict[int, AtlasLabel] = {}

    with open(lut_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse the line
            parts = line.split()
            if len(parts) < 5:
                continue  # Skip malformed lines

            try:
                label_id = int(parts[0])
                name = parts[1]
                r = int(parts[2])
                g = int(parts[3])
                b = int(parts[4])

                # Determine hemisphere and create abbreviation
                hemisphere = _determine_hemisphere(name)
                abbreviation = _create_abbreviation(name)

                labels[label_id] = AtlasLabel(
                    label_id=label_id,
                    name=name,
                    abbreviation=abbreviation,
                    hemisphere=hemisphere,
                    rgb_color=(r, g, b)
                )

            except (ValueError, IndexError):
                # Skip lines that can't be parsed
                continue

    return labels


def get_default_color_lut_path() -> Optional[Path]:
    """
    Get the default path to FreeSurferColorLUT.txt.

    Searches in order:
    1. $FREESURFER_HOME/FreeSurferColorLUT.txt
    2. Bundled fallback in package data

    Returns:
        Path to the color LUT file, or None if not found
    """
    # Try FREESURFER_HOME first
    fs_home = os.environ.get('FREESURFER_HOME')
    if fs_home:
        lut_path = Path(fs_home) / "FreeSurferColorLUT.txt"
        if lut_path.exists():
            return lut_path

    # Fallback to bundled copy (if we create one)
    bundled_path = Path(__file__).parent.parent.parent / "config" / "data" / "FreeSurferColorLUT.txt"
    if bundled_path.exists():
        return bundled_path

    return None
