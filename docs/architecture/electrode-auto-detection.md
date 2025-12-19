# Electrode Auto-Detection System

## Overview

This document describes the automatic electrode detection system for SEEG (Stereoelectroencephalography) electrode localization in medical images. The system detects electrode contacts from CT or processed CT images and groups them into individual electrodes.

**Key Result**: 91% electrode detection rate (10/11 electrodes) on test data with 100% contact-level detection.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Input Data](#input-data)
3. [Electrode Geometry Priors](#electrode-geometry-priors)
4. [Algorithm Overview](#algorithm-overview)
5. [Detailed Algorithm Steps](#detailed-algorithm-steps)
6. [Key Parameters](#key-parameters)
7. [Approaches Tried and Results](#approaches-tried-and-results)
8. [Known Limitations](#known-limitations)
9. [Code Locations](#code-locations)
10. [Testing and Validation](#testing-and-validation)

---

## Problem Statement

### The Manual Process
Clinicians manually mark electrode positions by:
1. Identifying the **entry point** (where electrode enters brain)
2. Identifying the **tip/output point** (deepest point)
3. Specifying the electrode type (which defines contact count and spacing)
4. The system then interpolates contact positions along the electrode axis

### The Goal
Automate the detection of:
- Individual electrode **contacts** (the recording sites)
- **Electrode groupings** (which contacts belong to which electrode)
- **Tip and entry points** for each electrode

---

## Input Data

### Recommended Input: Pre-processed Masked CT
**File pattern**: `r_<SUBJECT>_seeg_masked.nii.gz`

This is a CT scan that has been processed to isolate the electrodes:
- Background is mostly zero/negative
- Electrode contacts appear as bright regions (intensity 1500-4000)
- Much less bone artifact than raw CT
- Typically ~0.2% non-zero voxels (very sparse)

**Example characteristics**:
```
Image shape: (448, 512, 448)
Voxel size: 0.55mm isotropic
Non-zero voxels: ~0.2%
Contact intensities: 1500-4000 (varies by contact)
```

### Alternative Input: Raw CT
**File pattern**: `<SUBJECT>_CT_Electrodes_C.nii.gz`

Raw CT with electrodes visible:
- Contains bone, soft tissue, and electrodes
- Electrodes appear bright (>1600 HU) but so does bone
- ~45% non-zero voxels (dense)
- More challenging to process

---

## Electrode Geometry Priors

### From Electrode Definition Files
Location: `ciclone/config/electrodes/*.elecdef`

These pickle files define electrode geometry. Key information extracted:

| Electrode Type | Contacts | Spacing | Total Length |
|----------------|----------|---------|--------------|
| Dixi-D08-05AM  | 5        | 3.5mm   | 14.0mm       |
| Dixi-D08-08AM  | 8        | 3.5mm   | 24.5mm       |
| Dixi-D08-10AM  | 10       | 3.5mm   | 31.5mm       |
| Dixi-D08-12AM  | 12       | 3.5mm   | 38.5mm       |
| Dixi-D08-15AM  | 15       | 3.5mm   | 49.0mm       |
| Dixi-D08-15BM  | 15       | 4.3mm   | 60.0mm       |
| Dixi-D08-15CM  | 15       | 4.9mm   | 68.0mm       |
| Dixi-D08-18AM  | 18       | 3.5mm   | 59.5mm       |
| Dixi-D08-18CM  | 18       | 4.6mm   | 78.5mm       |

**Key Insight**: Contact spacing is the critical geometric prior:
- **Standard spacing**: 3.5mm (AM variants)
- **Medium spacing**: 4.3mm (BM variants)
- **Wide spacing**: 4.6-4.9mm (CM variants)
- **Very wide**: Up to 6.5mm observed in practice

---

## Algorithm Overview

The algorithm has two main stages:

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 1: CONTACT DETECTION               │
│                                                             │
│   Input Image → Local Maxima Filter → Threshold → Centroids │
│                                                             │
│   Result: Cloud of candidate contact positions              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 2: ELECTRODE GROUPING              │
│                                                             │
│   Centroids → Spacing Adjacency → Linear Chains → Electrodes│
│                                                             │
│   Result: Grouped electrodes with tip/entry points          │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Algorithm Steps

### Stage 1: Contact Detection via Local Maxima

**Why local maxima?** 
- Electrode contacts appear as bright spots in CT
- Each contact creates a local intensity maximum
- More robust than connected component analysis when contacts merge

**Algorithm**:
```python
from scipy.ndimage import maximum_filter, label, center_of_mass

# Parameters
threshold = 1400          # Intensity threshold
neighborhood_size = 5     # ~2mm at 0.5mm voxel size

# Find local maxima
local_max = maximum_filter(volume_data, size=neighborhood_size)
local_maxima_mask = (volume_data == local_max) & (volume_data > threshold)

# Extract centroids
labeled_maxima, num_maxima = label(local_maxima_mask)
centroids = center_of_mass(local_maxima_mask, labeled_maxima, range(1, num_maxima + 1))
```

**Result**: ~700 candidate contact positions (includes noise/duplicates)

**Validation**: 100% of ground truth contacts have a detected local maximum within 8 voxels.

### Stage 2: Spacing-Aware Electrode Grouping

**Why spacing-aware?**
- Traditional clustering (HDBSCAN/DBSCAN) doesn't understand linear electrode structure
- Electrodes have KNOWN contact spacing (~3.5mm)
- Contacts along an electrode are connected by this spacing

**Algorithm**:

1. **Build spacing adjacency graph**:
```python
from scipy.spatial.distance import cdist

# Convert spacing to voxels
voxel_size_mm = 0.55
min_spacing_voxels = 2.0 / voxel_size_mm  # ~3.6 voxels
max_spacing_voxels = 5.0 / voxel_size_mm  # ~9.0 voxels

# Build adjacency: connect contacts at correct spacing
distances = cdist(centroids, centroids)
adjacency = (distances >= min_spacing_voxels) & (distances <= max_spacing_voxels)
```

2. **Find connected components (chains)**:
```python
# BFS to find connected components
visited = np.zeros(n, dtype=bool)
chains = []

for start in range(n):
    if visited[start]:
        continue
    
    component = []
    queue = [start]
    while queue:
        node = queue.pop(0)
        if visited[node]:
            continue
        visited[node] = True
        component.append(node)
        
        # Add neighbors at correct spacing
        for neighbor in np.where(adjacency[node])[0]:
            if not visited[neighbor]:
                queue.append(neighbor)
    
    chains.append(component)
```

3. **Filter for linearity**:
```python
from sklearn.decomposition import PCA

# Electrodes are linear - filter out non-linear clusters
for chain in chains:
    points = centroids[chain]
    pca = PCA(n_components=3)
    pca.fit(points)
    linearity = pca.explained_variance_ratio_[0]  # First PC explains variance
    
    if linearity >= 0.80:  # At least 80% variance in one direction
        valid_chains.append(chain)
```

4. **Multi-spacing detection**:
```python
# Different electrode types have different spacings
# Run detection with multiple spacing ranges and combine results
spacing_ranges = [
    (2.0, 5.0),   # Standard 3.5mm electrodes
    (3.5, 6.0),   # Medium spacing variants
    (5.0, 8.0),   # Wide spacing variants (6.5mm)
]

all_chains = []
for min_mm, max_mm in spacing_ranges:
    chains = find_chains_with_spacing(centroids, min_mm, max_mm)
    all_chains.extend(chains)

# Remove duplicates (overlapping centers)
unique_chains = deduplicate_chains(all_chains)
```

5. **Extract tip/entry points**:
```python
from sklearn.decomposition import PCA

def fit_electrode_axis(points):
    """Get tip and entry points from electrode contacts."""
    pca = PCA(n_components=1)
    pca.fit(points)
    
    # Project points onto principal axis
    center = points.mean(axis=0)
    direction = pca.components_[0]
    projections = np.dot(points - center, direction)
    
    # Tip = most negative projection, Entry = most positive
    tip = points[np.argmin(projections)]
    entry = points[np.argmax(projections)]
    
    return tip, entry
```

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `threshold` | 1400 | Minimum intensity for local maxima |
| `local_maxima_neighborhood` | 5 | Size of maximum filter (voxels) |
| `min_contacts_per_electrode` | 4 | Minimum contacts to form electrode |
| `linearity_threshold` | 0.80 | PCA variance ratio for linearity |
| `spacing_tolerance_mm` | 1.5 | Tolerance around expected spacing |
| `voxel_size_mm` | 0.55 | Voxel size (should be from image header) |

### Spacing Ranges (in mm)
- **Standard**: 2.0 - 5.0mm (covers 3.5mm ± 1.5mm)
- **Medium**: 3.5 - 6.0mm (covers 4.3-4.9mm variants)
- **Wide**: 5.0 - 8.0mm (covers unusual 6.5mm+ spacing)

---

## Approaches Tried and Results

### What We Tried

| Approach | Result | Why It Failed/Succeeded |
|----------|--------|------------------------|
| Connected components + HDBSCAN | 36% | Clustering doesn't understand linear structure |
| Local maxima + HDBSCAN | 63% | Better, but still over-segments |
| Local maxima + Hierarchical clustering | 36% | Ward linkage groups by proximity, not linearity |
| RANSAC line fitting | 45% | Greedy approach misses some electrodes |
| **Local maxima + spacing-aware chaining** | **91%** | Leverages known electrode geometry |
| Two-pass merge of collinear clusters | 45% | Over-aggressive merging |

### Why Spacing-Aware Chaining Works Best

1. **Exploits domain knowledge**: We KNOW electrodes have regular spacing
2. **Linear-aware**: Only groups contacts that form a line
3. **Multi-scale**: Different spacing ranges catch different electrode types
4. **Robust**: Local maxima are more robust than connected components

---

## Known Limitations

### 1. Low-Intensity Contacts
Some contacts have very low intensity (< 200) due to:
- Partial volume effects
- Image artifacts
- Position relative to skull

**Impact**: These contacts may not be detected, causing electrode fragmentation.

### 2. Irregular Spacing
Some electrodes show irregular spacing between local maxima:
- Ground truth contact at position A
- Nearest local maximum may be offset by 2-4 voxels
- This creates apparent spacing variation (2.9mm to 7.4mm observed)

**Impact**: Contacts may not chain together properly.

### 3. Over-Detection
The algorithm detects more clusters than actual electrodes:
- 56 clusters detected for 11 ground truth electrodes
- Most extra clusters are small fragments

**Mitigation**: Filter by size, confidence, and linearity.

### 4. The Unmatchable Electrode (C)
In our test case, electrode C was not matched because:
- 5 of 15 contacts had intensity < 200
- Apparent spacing was highly irregular (2.9-7.4mm)
- Fragments didn't meet minimum contact threshold

**This represents the ~9% failure case.**

---

## Code Locations

### Main Detection Code
```
ciclone/services/detection/
├── __init__.py                    # Exports public API
├── base_detector.py               # Abstract base class
├── detected_electrode.py          # DetectedElectrode dataclass
├── ct_detector.py                 # Main CT detection (spacing-aware)
├── electrode_clustering.py        # Clustering utilities
├── detection_service.py           # High-level service interface
├── sam_detector.py                # Optional SAM-based detection
└── model_loader.py                # SAM model management
```

### Key Functions in `ct_detector.py`

```python
class CTElectrodeDetector:
    def detect(volume_data, **kwargs) -> List[DetectedElectrode]:
        """Main entry point - uses spacing-aware detection."""
    
    def _detect_spacing_aware(volume_data, params) -> List[DetectedElectrode]:
        """New algorithm: local maxima + spacing-aware chaining."""
    
    def _find_spacing_chains(centroids, min_spacing, max_spacing, ...) -> List[Dict]:
        """Find linear chains of contacts at specified spacing."""
    
    def _detect_classic(volume_data, params) -> List[DetectedElectrode]:
        """Fallback: connected components + HDBSCAN."""
```

### Electrode Definitions
```
ciclone/config/electrodes/
├── Dixi-D08-05AM.elecdef
├── Dixi-D08-08AM.elecdef
├── ... (9 electrode types total)
```

### UI Integration
```
ciclone/ui/ImagesViewer.py
    - AutoDetectPushButton: UI button
    - on_auto_detect_clicked(): Handler

ciclone/controllers/electrode_controller.py
    - auto_detect_electrodes(): Controller method
    - _import_detected_electrode(): Import detected electrode
```

---

## Testing and Validation

### Test Data Location
```
/Users/fl6985/Desktop/DbCiCLONE/
├── sub_015/
│   └── pipeline_output/
│       ├── r_sub_015_seeg_masked.nii.gz    # Input image
│       └── sub_015_coordinates.json         # Ground truth
├── sub_027/
└── sub_032/
```

### Ground Truth Format (Slicer JSON)
```json
{
  "markups": [{
    "controlPoints": [
      {"label": "A1", "position": [x, y, z]},
      {"label": "A2", "position": [x, y, z]},
      ...
    ]
  }]
}
```

### Running Tests
```bash
# Unit tests
poetry run python -m pytest tests/test_detection_service.py -v

# Test on real data
poetry run python -c "
from ciclone.services.detection import CTElectrodeDetector
import nibabel as nib

img = nib.load('path/to/r_subject_seeg_masked.nii.gz')
detector = CTElectrodeDetector()
electrodes = detector.detect(img.get_fdata(), voxel_size_mm=0.55)
print(f'Detected {len(electrodes)} electrodes')
"
```

### Validation Metrics
- **Electrode match rate**: % of ground truth electrodes with a detected match
- **Contact detection rate**: % of ground truth contacts with nearby local maxima
- **Contact localization error**: Distance (mm) between detected and ground truth contacts

---

## Recreating This Solution

If starting from scratch, follow these steps:

1. **Understand the input**: Pre-processed CT with isolated electrodes works best

2. **Use local maxima, not connected components**:
   - `scipy.ndimage.maximum_filter` with `size=5`
   - Threshold around 1400 for masked CT

3. **Use spacing-aware chaining, not generic clustering**:
   - Build adjacency matrix based on expected 3.5mm spacing (± 1.5mm tolerance)
   - Find connected components in the adjacency graph
   - Filter for linearity using PCA (>80% variance in first component)

4. **Support multiple electrode types**:
   - Run with multiple spacing ranges: (2-5mm), (3.5-6mm), (5-8mm)
   - Deduplicate overlapping detections

5. **Known failure modes**:
   - Low-intensity contacts won't be detected
   - Unusual electrode types (non-Dixi) may have different spacing

---

## Future Improvements

1. **Adaptive thresholding per electrode**: Lower threshold in regions with detected electrodes
2. **Template matching**: Use known electrode geometry as template
3. **Deep learning**: Train a model on manually labeled data
4. **Interactive refinement**: Let user approve/reject/edit detections
5. **Multi-modal fusion**: Combine CT with MRI for better localization

---

*Document created: December 2024*
*Based on implementation in CiCLONE electrode detection module*
