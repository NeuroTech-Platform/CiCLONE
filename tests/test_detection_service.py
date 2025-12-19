"""
Unit tests for electrode auto-detection services.

Tests cover:
- DetectedElectrode dataclass
- CTElectrodeDetector with synthetic data
- DetectionService modality detection
- Electrode clustering utilities
"""

import unittest
import numpy as np

from ciclone.services.detection import (
    DetectedElectrode,
    CTElectrodeDetector,
    DetectionService,
)
from ciclone.services.detection.electrode_clustering import (
    cluster_contacts,
    fit_electrode_axis,
    filter_linear_clusters,
    estimate_inter_contact_distance,
    suggest_electrode_name,
)


class TestDetectedElectrode(unittest.TestCase):
    """Tests for the DetectedElectrode dataclass."""
    
    def test_basic_creation(self):
        """Test creating a DetectedElectrode with minimum data."""
        electrode = DetectedElectrode(
            tip=(10, 20, 30),
            entry=(10, 20, 50)
        )
        
        self.assertEqual(electrode.tip, (10, 20, 30))
        self.assertEqual(electrode.entry, (10, 20, 50))
        self.assertEqual(electrode.num_contacts, 0)
        self.assertEqual(electrode.confidence, 1.0)
    
    def test_with_contacts(self):
        """Test creating a DetectedElectrode with contacts."""
        contacts = [
            (10.0, 20.0, 30.0),
            (10.0, 20.0, 35.0),
            (10.0, 20.0, 40.0),
            (10.0, 20.0, 45.0),
            (10.0, 20.0, 50.0),
        ]
        
        electrode = DetectedElectrode(
            tip=(10, 20, 30),
            entry=(10, 20, 50),
            contacts=contacts,
            confidence=0.85,
            suggested_name="LA",
            electrode_type="Dixi-D08-05AM"
        )
        
        self.assertEqual(electrode.num_contacts, 5)
        self.assertAlmostEqual(electrode.confidence, 0.85)
        self.assertEqual(electrode.suggested_name, "LA")
        self.assertEqual(electrode.electrode_type, "Dixi-D08-05AM")
    
    def test_length_calculation(self):
        """Test electrode length calculation."""
        electrode = DetectedElectrode(
            tip=(0, 0, 0),
            entry=(0, 0, 20)
        )
        
        self.assertAlmostEqual(electrode.length, 20.0)
    
    def test_length_diagonal(self):
        """Test electrode length for diagonal trajectory."""
        electrode = DetectedElectrode(
            tip=(0, 0, 0),
            entry=(10, 10, 10)
        )
        
        expected_length = np.sqrt(10**2 + 10**2 + 10**2)
        self.assertAlmostEqual(electrode.length, expected_length)
    
    def test_direction_vector(self):
        """Test direction vector calculation."""
        electrode = DetectedElectrode(
            tip=(0, 0, 0),
            entry=(0, 0, 10)
        )
        
        direction = electrode.direction_vector
        expected = np.array([0, 0, 1])
        np.testing.assert_array_almost_equal(direction, expected)
    
    def test_contacts_as_int(self):
        """Test conversion of contacts to integer coordinates."""
        contacts = [
            (10.4, 20.6, 30.1),
            (10.5, 20.5, 35.9),
        ]
        
        electrode = DetectedElectrode(
            tip=(10, 20, 30),
            entry=(10, 20, 36),
            contacts=contacts
        )
        
        int_contacts = electrode.get_contacts_as_int()
        self.assertEqual(int_contacts[0], (10, 21, 30))
        self.assertEqual(int_contacts[1], (10, 20, 36))  # 10.5 rounds to 10
    
    def test_repr(self):
        """Test string representation."""
        electrode = DetectedElectrode(
            tip=(10, 20, 30),
            entry=(10, 20, 50),
            contacts=[(10, 20, 30), (10, 20, 40), (10, 20, 50)],
            confidence=0.9,
            suggested_name="RA"
        )
        
        repr_str = repr(electrode)
        self.assertIn("RA", repr_str)
        self.assertIn("contacts=3", repr_str)
        self.assertIn("0.90", repr_str)


class TestElectrodeClustering(unittest.TestCase):
    """Tests for electrode clustering utilities."""
    
    def test_cluster_single_electrode(self):
        """Test clustering contacts that belong to a single electrode."""
        # Create a linear arrangement of contacts
        centroids = np.array([
            [50, 50, 10],
            [50, 50, 15],
            [50, 50, 20],
            [50, 50, 25],
            [50, 50, 30],
        ], dtype=float)
        
        labels = cluster_contacts(centroids, min_cluster_size=3, eps=10.0)
        
        # All contacts should be in the same cluster
        unique_labels = set(labels) - {-1}
        self.assertEqual(len(unique_labels), 1)
    
    def test_cluster_two_electrodes(self):
        """Test clustering contacts from two separate electrodes."""
        # First electrode: vertical
        electrode1 = np.array([
            [20, 50, 10],
            [20, 50, 15],
            [20, 50, 20],
            [20, 50, 25],
        ], dtype=float)
        
        # Second electrode: far from first
        electrode2 = np.array([
            [80, 50, 10],
            [80, 50, 15],
            [80, 50, 20],
            [80, 50, 25],
        ], dtype=float)
        
        centroids = np.vstack([electrode1, electrode2])
        
        labels = cluster_contacts(centroids, min_cluster_size=3, eps=10.0)
        
        # Should find two clusters
        unique_labels = set(labels) - {-1}
        self.assertEqual(len(unique_labels), 2)
        
        # Verify groupings
        electrode1_labels = labels[:4]
        electrode2_labels = labels[4:]
        
        # All contacts in each electrode should have same label
        self.assertEqual(len(set(electrode1_labels)), 1)
        self.assertEqual(len(set(electrode2_labels)), 1)
        
        # But different electrodes should have different labels
        self.assertNotEqual(electrode1_labels[0], electrode2_labels[0])
    
    def test_fit_electrode_axis_vertical(self):
        """Test axis fitting for a vertical electrode."""
        points = np.array([
            [50, 50, 10],
            [50, 50, 20],
            [50, 50, 30],
            [50, 50, 40],
        ], dtype=float)
        
        tip, entry, ordered = fit_electrode_axis(points, return_ordered=True)
        
        # Tip should be at lower z, entry at higher z
        self.assertEqual(tip[2], 10)
        self.assertEqual(entry[2], 40)
        
        # Ordered contacts should go from tip to entry
        self.assertEqual(ordered[0][2], 10)
        self.assertEqual(ordered[-1][2], 40)
    
    def test_fit_electrode_axis_diagonal(self):
        """Test axis fitting for a diagonal electrode."""
        points = np.array([
            [10, 10, 10],
            [20, 20, 20],
            [30, 30, 30],
            [40, 40, 40],
        ], dtype=float)
        
        tip, entry, ordered = fit_electrode_axis(points, return_ordered=True)
        
        # Tip should be at lower z (10), entry at higher z (40)
        self.assertLess(tip[2], entry[2])
        self.assertEqual(len(ordered), 4)
    
    def test_filter_linear_clusters(self):
        """Test filtering non-linear clusters."""
        # Linear cluster (should pass)
        linear = np.array([
            [10, 10, 10],
            [10, 10, 20],
            [10, 10, 30],
            [10, 10, 40],
        ], dtype=float)
        
        # Non-linear cluster (should be filtered)
        non_linear = np.array([
            [50, 50, 50],
            [60, 60, 50],
            [50, 60, 60],
            [60, 50, 60],
        ], dtype=float)
        
        centroids = np.vstack([linear, non_linear])
        labels = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        
        filtered = filter_linear_clusters(centroids, labels, linearity_threshold=0.9)
        
        # Linear cluster should remain (label 0)
        self.assertTrue(all(filtered[:4] == 0))
        
        # Non-linear cluster should be filtered (label -1)
        self.assertTrue(all(filtered[4:] == -1))
    
    def test_estimate_inter_contact_distance(self):
        """Test inter-contact distance estimation."""
        # Evenly spaced contacts
        contacts = np.array([
            [50, 50, 10],
            [50, 50, 20],
            [50, 50, 30],
            [50, 50, 40],
        ], dtype=float)
        
        mean_dist, std_dist = estimate_inter_contact_distance(contacts)
        
        # Mean should be 10, std should be ~0
        self.assertAlmostEqual(mean_dist, 10.0, places=1)
        self.assertLess(std_dist, 0.1)
    
    def test_suggest_electrode_name(self):
        """Test electrode name suggestion based on position."""
        volume_shape = (100, 100, 100)
        
        # Left anterior (x < 50, y > 50)
        name1 = suggest_electrode_name((30, 70, 50), volume_shape, [])
        self.assertEqual(name1[0], "L")  # Left hemisphere
        
        # Right posterior (x > 50, y < 50)
        name2 = suggest_electrode_name((70, 30, 50), volume_shape, [name1])
        self.assertEqual(name2[0], "R")  # Right hemisphere
        
        # Names should be unique
        self.assertNotEqual(name1, name2)
    
    def test_suggest_electrode_name_duplicates(self):
        """Test that duplicate names are numbered."""
        volume_shape = (100, 100, 100)
        existing = ["LA"]
        
        # Same position should generate numbered name
        name = suggest_electrode_name((30, 70, 50), volume_shape, existing)
        self.assertIn("LA", name)
        self.assertIn("2", name)


class TestCTElectrodeDetector(unittest.TestCase):
    """Tests for the CT electrode detector."""
    
    def setUp(self):
        """Create a synthetic CT volume with electrode-like structures."""
        self.detector = CTElectrodeDetector({
            "threshold": 1600,
            "min_contact_size": 3,
            "max_contact_size": 1000,
            "min_contacts_per_electrode": 3,
            "clustering_eps": 15.0,
            "linearity_threshold": 0.80,
        })
    
    def test_empty_volume(self):
        """Test detection on empty volume."""
        volume = np.zeros((100, 100, 100), dtype=np.float32)
        
        electrodes = self.detector.detect(volume)
        
        self.assertEqual(len(electrodes), 0)
    
    def test_single_electrode(self):
        """Test detection of a single synthetic electrode."""
        volume = self._create_synthetic_electrode_volume(
            num_electrodes=1,
            contacts_per_electrode=5
        )
        
        electrodes = self.detector.detect(volume)
        
        # Should detect one electrode
        self.assertEqual(len(electrodes), 1)
        
        # Should have approximately correct number of contacts
        # (may vary due to morphological operations)
        self.assertGreaterEqual(electrodes[0].num_contacts, 3)
    
    def test_multiple_electrodes(self):
        """Test detection of multiple synthetic electrodes."""
        volume = self._create_synthetic_electrode_volume(
            num_electrodes=3,
            contacts_per_electrode=5
        )
        
        electrodes = self.detector.detect(volume)
        
        # Should detect multiple electrodes
        self.assertGreaterEqual(len(electrodes), 2)
    
    def test_threshold_parameter(self):
        """Test that threshold parameter affects detection."""
        volume = self._create_synthetic_electrode_volume(
            num_electrodes=1,
            contacts_per_electrode=5,
            intensity=1700
        )
        
        # With high threshold, should detect
        detector_high = CTElectrodeDetector({"threshold": 1600})
        electrodes_high = detector_high.detect(volume)
        
        # With even higher threshold, might not detect
        detector_very_high = CTElectrodeDetector({"threshold": 2000})
        electrodes_very_high = detector_very_high.detect(volume)
        
        self.assertGreaterEqual(len(electrodes_high), len(electrodes_very_high))
    
    def test_detector_name(self):
        """Test detector name property."""
        name = self.detector.get_detector_name()
        self.assertIn("CT", name)
    
    def test_supported_modalities(self):
        """Test supported modalities."""
        modalities = self.detector.get_supported_modalities()
        self.assertIn("CT", modalities)
    
    def test_validate_volume(self):
        """Test volume validation."""
        # Valid 3D volume
        valid = np.zeros((100, 100, 100))
        self.assertTrue(self.detector.validate_volume(valid))
        
        # Invalid: None
        self.assertFalse(self.detector.validate_volume(None))
        
        # Invalid: 2D
        invalid_2d = np.zeros((100, 100))
        self.assertFalse(self.detector.validate_volume(invalid_2d))
        
        # Invalid: empty
        invalid_empty = np.array([])
        self.assertFalse(self.detector.validate_volume(invalid_empty))
    
    def _create_synthetic_electrode_volume(
        self,
        shape=(100, 100, 100),
        num_electrodes=1,
        contacts_per_electrode=5,
        contact_radius=2,
        contact_spacing=8,
        intensity=2000
    ):
        """Create a synthetic volume with electrode-like high-intensity structures."""
        volume = np.zeros(shape, dtype=np.float32)
        
        # Add some background noise
        volume += np.random.normal(0, 50, shape).astype(np.float32)
        
        # Add electrodes at different positions
        for e in range(num_electrodes):
            # Random starting position
            start_x = 20 + e * 25
            start_y = 50
            start_z = 20
            
            # Direction (mostly along z)
            dx, dy, dz = 0.1 * (e - num_electrodes/2), 0, 1
            
            # Add contacts
            for c in range(contacts_per_electrode):
                cx = int(start_x + c * contact_spacing * dx)
                cy = int(start_y + c * contact_spacing * dy)
                cz = int(start_z + c * contact_spacing * dz)
                
                # Create spherical contact
                for x in range(cx - contact_radius, cx + contact_radius + 1):
                    for y in range(cy - contact_radius, cy + contact_radius + 1):
                        for z in range(cz - contact_radius, cz + contact_radius + 1):
                            if (0 <= x < shape[0] and 0 <= y < shape[1] and 
                                0 <= z < shape[2]):
                                dist = np.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
                                if dist <= contact_radius:
                                    volume[x, y, z] = intensity
        
        return volume


class TestDetectionService(unittest.TestCase):
    """Tests for the unified detection service."""
    
    def test_service_creation(self):
        """Test creating a detection service."""
        service = DetectionService()
        self.assertIsNotNone(service)
    
    def test_detector_info(self):
        """Test getting detector information."""
        service = DetectionService()
        info = service.get_detector_info()
        
        # CT detector should always be available
        self.assertIn("ct_detector", info)
        self.assertTrue(info["ct_detector"]["available"])
    
    def test_modality_detection_ct(self):
        """Test CT modality detection from volume characteristics."""
        service = DetectionService()
        
        # CT-like volume (wide range, negative values)
        ct_volume = np.random.uniform(-1000, 3000, (50, 50, 50)).astype(np.float32)
        
        modality = service._detect_modality(ct_volume)
        self.assertEqual(modality, "CT")
    
    def test_modality_detection_mri(self):
        """Test MRI modality detection from volume characteristics."""
        service = DetectionService()
        
        # MRI-like volume (narrow range, positive values)
        mri_volume = np.random.uniform(0, 500, (50, 50, 50)).astype(np.float32)
        
        modality = service._detect_modality(mri_volume)
        self.assertEqual(modality, "MRI")
    
    def test_detect_empty(self):
        """Test detection on empty volume."""
        service = DetectionService()
        volume = np.zeros((50, 50, 50), dtype=np.float32)
        
        electrodes = service.detect(volume, modality="CT")
        
        self.assertEqual(len(electrodes), 0)
    
    def test_config_override(self):
        """Test configuration override."""
        config = {
            "ct_config": {
                "threshold": 1800,
                "min_contacts_per_electrode": 4,
            }
        }
        
        service = DetectionService(config)
        
        # Verify config was applied
        self.assertEqual(
            service._ct_detector.config["threshold"], 
            1800
        )
        self.assertEqual(
            service._ct_detector.config["min_contacts_per_electrode"], 
            4
        )


class TestSAMDetectorAvailability(unittest.TestCase):
    """Tests for SAM detector availability checking."""
    
    def test_sam_availability_check(self):
        """Test checking if SAM is available."""
        from ciclone.services.detection.sam_detector import is_sam_available
        
        # This should not raise an error
        available = is_sam_available()
        self.assertIsInstance(available, bool)
    
    def test_available_models_list(self):
        """Test getting list of available SAM models."""
        from ciclone.services.detection.sam_detector import (
            is_sam_available,
            get_available_sam_models
        )
        
        models = get_available_sam_models()
        
        if is_sam_available():
            # If SAM is available, should return model list
            self.assertIsInstance(models, list)
            self.assertGreater(len(models), 0)
        else:
            # If not available, should return empty list
            self.assertEqual(models, [])


if __name__ == "__main__":
    unittest.main()
