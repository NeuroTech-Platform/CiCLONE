"""Unit tests for the NamingService class."""

import unittest
import tempfile
import yaml
from pathlib import Path
from ciclone.services.naming_service import NamingService


class TestNamingService(unittest.TestCase):
    """Test cases for NamingService."""
    
    def test_default_naming_patterns(self):
        """Test that default naming patterns are used when no config is provided."""
        service = NamingService()
        
        # Test default CT naming
        self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_CT_Bone")
        self.assertEqual(service.get_post_ct_filename("Subject01"), "Subject01_CT_Electrodes")
        
        # Test default MRI naming
        self.assertEqual(service.get_pre_mri_filename("Subject01", "T1"), "Subject01_T1")
        self.assertEqual(service.get_post_mri_filename("Subject01", "T2"), "Subject01_T2")
    
    def test_custom_naming_patterns_from_config(self):
        """Test loading custom naming patterns from a config file."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'file_naming': {
                    'pre_ct': '${name}_pre_CT',
                    'post_ct': '${name}_post_CT',
                    'pre_mri': '${name}_pre_${modality}',
                    'post_mri': '${name}_post_${modality}'
                }
            }
            yaml.dump(config, f)
            config_path = Path(f.name)
        
        try:
            service = NamingService(config_path)
            
            # Test custom CT naming
            self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_pre_CT")
            self.assertEqual(service.get_post_ct_filename("Subject01"), "Subject01_post_CT")
            
            # Test custom MRI naming
            self.assertEqual(service.get_pre_mri_filename("Subject01", "T1"), "Subject01_pre_T1")
            self.assertEqual(service.get_post_mri_filename("Subject01", "FLAIR"), "Subject01_post_FLAIR")
        finally:
            # Clean up temp file
            config_path.unlink()
    
    def test_partial_config_merges_with_defaults(self):
        """Test that partial config merges with defaults."""
        # Create a config with only CT patterns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'file_naming': {
                    'pre_ct': '${name}_baseline_CT',
                    'post_ct': '${name}_implant_CT'
                }
            }
            yaml.dump(config, f)
            config_path = Path(f.name)
        
        try:
            service = NamingService(config_path)
            
            # Test custom CT naming
            self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_baseline_CT")
            self.assertEqual(service.get_post_ct_filename("Subject01"), "Subject01_implant_CT")
            
            # Test that MRI uses defaults
            self.assertEqual(service.get_pre_mri_filename("Subject01", "T1"), "Subject01_T1")
            self.assertEqual(service.get_post_mri_filename("Subject01", "T2"), "Subject01_T2")
        finally:
            config_path.unlink()
    
    def test_get_filename_generic_method(self):
        """Test the generic get_filename method."""
        service = NamingService()
        
        # Test all file types
        self.assertEqual(
            service.get_filename('pre_ct', 'Subject01'),
            "Subject01_CT_Bone"
        )
        self.assertEqual(
            service.get_filename('post_ct', 'Subject01'),
            "Subject01_CT_Electrodes"
        )
        self.assertEqual(
            service.get_filename('pre_mri', 'Subject01', 'T1'),
            "Subject01_T1"
        )
        self.assertEqual(
            service.get_filename('post_mri', 'Subject01', 'FLAIR'),
            "Subject01_FLAIR"
        )
    
    def test_missing_modality_defaults_to_mri(self):
        """Test that missing modality defaults to 'MRI'."""
        service = NamingService()
        
        # When modality is None, should default to 'MRI'
        self.assertEqual(
            service.get_filename('pre_mri', 'Subject01', None),
            "Subject01_MRI"
        )
    
    def test_invalid_file_type_returns_subject_name(self):
        """Test that invalid file type returns subject name."""
        service = NamingService()
        
        # Invalid file type should return subject name
        self.assertEqual(
            service.get_filename('invalid_type', 'Subject01'),
            "Subject01"
        )
    
    def test_get_current_patterns(self):
        """Test getting current naming patterns."""
        service = NamingService()
        patterns = service.get_current_patterns()
        
        # Should return a copy of patterns
        self.assertIsInstance(patterns, dict)
        self.assertIn('pre_ct', patterns)
        self.assertIn('post_ct', patterns)
        self.assertIn('pre_mri', patterns)
        self.assertIn('post_mri', patterns)
        
        # Modifying returned dict should not affect service
        patterns['pre_ct'] = 'modified'
        self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_CT_Bone")
    
    def test_update_pattern_at_runtime(self):
        """Test updating patterns at runtime."""
        service = NamingService()
        
        # Update a pattern
        service.update_pattern('pre_ct', '${name}_custom_CT')
        self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_custom_CT")
        
        # Other patterns should remain unchanged
        self.assertEqual(service.get_post_ct_filename("Subject01"), "Subject01_CT_Electrodes")
    
    def test_special_characters_in_subject_name(self):
        """Test handling of special characters in subject names."""
        service = NamingService()
        
        # Test with various special characters
        test_names = [
            "Subject_01",
            "Subject-01",
            "Subject.01",
            "Subject 01",
            "Subject(01)",
            "Subject[01]"
        ]
        
        for name in test_names:
            result = service.get_pre_ct_filename(name)
            self.assertEqual(result, f"{name}_CT_Bone")
    
    def test_empty_config_file(self):
        """Test handling of empty config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")  # Empty file
            config_path = Path(f.name)
        
        try:
            service = NamingService(config_path)
            # Should fall back to defaults
            self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_CT_Bone")
        finally:
            config_path.unlink()
    
    def test_malformed_config_file(self):
        """Test handling of malformed config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("this is not: valid yaml{")
            config_path = Path(f.name)
        
        try:
            service = NamingService(config_path)
            # Should fall back to defaults and print warning
            self.assertEqual(service.get_pre_ct_filename("Subject01"), "Subject01_CT_Bone")
        finally:
            config_path.unlink()


if __name__ == '__main__':
    unittest.main()