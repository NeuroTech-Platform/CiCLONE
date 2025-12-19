"""
Clustering and axis fitting utilities for electrode detection.
"""

from typing import List, Tuple, Optional
import numpy as np

# Try to import hdbscan, fall back to sklearn's DBSCAN if not available
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA


def cluster_contacts(
    centroids: np.ndarray,
    method: str = "auto",
    min_cluster_size: int = 3,
    min_samples: int = 2,
    eps: float = 15.0,
) -> np.ndarray:
    """
    Cluster contact centroids into electrode groups.
    
    Uses HDBSCAN if available (better for varying densities), 
    otherwise falls back to DBSCAN.
    
    Args:
        centroids: Array of shape (N, 3) containing contact centroids
        method: 'hdbscan', 'dbscan', or 'auto' (uses best available)
        min_cluster_size: Minimum number of contacts to form an electrode
        min_samples: Minimum samples for HDBSCAN/DBSCAN core points
        eps: Maximum distance between contacts for DBSCAN
        
    Returns:
        Array of cluster labels (-1 for noise)
    """
    if len(centroids) < min_cluster_size:
        return np.array([-1] * len(centroids))
    
    # Select clustering method
    if method == "auto":
        method = "hdbscan" if HDBSCAN_AVAILABLE else "dbscan"
    
    if method == "hdbscan" and HDBSCAN_AVAILABLE:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=eps / 2,  # More conservative for electrodes
            metric='euclidean'
        )
        labels = clusterer.fit_predict(centroids)
    else:
        # Fall back to DBSCAN
        clusterer = DBSCAN(
            eps=eps,
            min_samples=min_samples,
            metric='euclidean'
        )
        labels = clusterer.fit_predict(centroids)
    
    return labels


def fit_electrode_axis(
    points: np.ndarray,
    return_ordered: bool = True
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Optional[np.ndarray]]:
    """
    Fit a principal axis to a set of electrode contact points using PCA.
    
    Determines tip (deepest in brain, typically lowest z) and entry points.
    
    Args:
        points: Array of shape (N, 3) containing contact positions
        return_ordered: If True, return contacts ordered along axis
        
    Returns:
        Tuple of (tip_point, entry_point, ordered_contacts or None)
    """
    if len(points) < 2:
        # Single point - use as both tip and entry
        point = tuple(int(round(x)) for x in points[0])
        return point, point, points if return_ordered else None
    
    # Fit PCA to find principal axis
    pca = PCA(n_components=1)
    pca.fit(points)
    
    # Project points onto principal axis
    projections = pca.transform(points).flatten()
    
    # Order points along the axis
    order = np.argsort(projections)
    ordered_points = points[order]
    
    # Determine tip vs entry based on z-coordinate (tip is typically deeper/lower z)
    # In medical imaging, lower z often corresponds to inferior direction
    first_point = ordered_points[0]
    last_point = ordered_points[-1]
    
    # Use z-coordinate to determine which end is the tip
    # The tip (deepest in brain) is typically at lower z in standard orientations
    if first_point[2] <= last_point[2]:
        tip = tuple(int(round(x)) for x in first_point)
        entry = tuple(int(round(x)) for x in last_point)
    else:
        tip = tuple(int(round(x)) for x in last_point)
        entry = tuple(int(round(x)) for x in first_point)
        ordered_points = ordered_points[::-1]  # Reverse order
    
    if return_ordered:
        return tip, entry, ordered_points
    return tip, entry, None


def filter_linear_clusters(
    centroids: np.ndarray,
    labels: np.ndarray,
    linearity_threshold: float = 0.85
) -> np.ndarray:
    """
    Filter clusters to keep only those that are approximately linear (electrode-like).
    
    Uses PCA explained variance ratio to assess linearity.
    
    Args:
        centroids: Array of shape (N, 3) containing all centroids
        labels: Cluster labels for each centroid
        linearity_threshold: Minimum explained variance ratio for first component
        
    Returns:
        Filtered labels (non-linear clusters set to -1)
    """
    filtered_labels = labels.copy()
    unique_labels = set(labels) - {-1}
    
    for label in unique_labels:
        mask = labels == label
        cluster_points = centroids[mask]
        
        if len(cluster_points) < 3:
            # Can't assess linearity with fewer than 3 points
            continue
        
        # Fit PCA to assess linearity
        pca = PCA(n_components=min(3, len(cluster_points)))
        pca.fit(cluster_points)
        
        # Check if first component explains most variance (linear structure)
        linearity = pca.explained_variance_ratio_[0]
        
        if linearity < linearity_threshold:
            # Not linear enough - likely not an electrode
            filtered_labels[mask] = -1
    
    return filtered_labels


def estimate_inter_contact_distance(
    ordered_contacts: np.ndarray
) -> Tuple[float, float]:
    """
    Estimate the inter-contact distance for an electrode.
    
    Args:
        ordered_contacts: Contacts ordered along electrode axis
        
    Returns:
        Tuple of (mean_distance, std_distance)
    """
    if len(ordered_contacts) < 2:
        return 0.0, 0.0
    
    distances = []
    for i in range(len(ordered_contacts) - 1):
        dist = np.linalg.norm(ordered_contacts[i+1] - ordered_contacts[i])
        distances.append(dist)
    
    return float(np.mean(distances)), float(np.std(distances))


def suggest_electrode_name(
    tip: Tuple[int, int, int],
    volume_shape: Tuple[int, int, int],
    existing_names: List[str]
) -> str:
    """
    Suggest a name for a detected electrode based on its position.
    
    Uses anatomical position conventions (L/R for lateral, A/P for anterior).
    
    Args:
        tip: Tip position (x, y, z)
        volume_shape: Shape of the volume (for determining center)
        existing_names: List of already used names
        
    Returns:
        Suggested electrode name
    """
    center_x = volume_shape[0] / 2
    center_y = volume_shape[1] / 2
    
    # Determine hemisphere and position
    side = "R" if tip[0] > center_x else "L"
    position = "A" if tip[1] > center_y else "P"
    
    # Generate base name
    base_name = f"{side}{position}"
    
    # Add number if name already exists
    name = base_name
    counter = 1
    while name in existing_names:
        counter += 1
        name = f"{base_name}{counter}"
    
    return name
