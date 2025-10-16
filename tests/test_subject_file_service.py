"""
Unit tests for SubjectFileService.

Tests the file operations service that was extracted from the Subject domain class
to maintain proper MVC separation.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from ciclone.services.io.subject_file_service import SubjectFileService


class TestSubjectFileService(unittest.TestCase):
    """Test cases for SubjectFileService."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.subject_path = Path(self.temp_dir) / "test_subject"
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_subject_directories(self):
        """Test that all required subject directories are created."""
        # Act
        SubjectFileService.create_subject_directories(self.subject_path)
        
        # Assert
        self.assertTrue(self.subject_path.exists())
        
        # Check all expected subdirectories
        expected_dirs = [
            self.subject_path / 'documents',
            self.subject_path / 'images' / 'postop' / 'ct',
            self.subject_path / 'images' / 'postop' / 'mri',
            self.subject_path / 'images' / 'preop' / 'ct',
            self.subject_path / 'images' / 'preop' / 'mri',
            self.subject_path / 'processed_tmp',
            self.subject_path / 'pipeline_output'
        ]
        
        for expected_dir in expected_dirs:
            with self.subTest(directory=str(expected_dir)):
                self.assertTrue(expected_dir.exists(), f"Directory {expected_dir} was not created")
                self.assertTrue(expected_dir.is_dir(), f"{expected_dir} is not a directory")
    
    def test_create_subject_directories_idempotent(self):
        """Test that creating directories multiple times doesn't cause errors."""
        # Act - create directories twice
        SubjectFileService.create_subject_directories(self.subject_path)
        SubjectFileService.create_subject_directories(self.subject_path)
        
        # Assert - should still exist and be valid
        self.assertTrue(self.subject_path.exists())
        self.assertTrue((self.subject_path / 'documents').exists())
    
    def test_clear_processed_tmp_with_files(self):
        """Test clearing processed_tmp directory that contains files."""
        # Arrange
        SubjectFileService.create_subject_directories(self.subject_path)
        processed_tmp = self.subject_path / 'processed_tmp'
        
        # Create some test files
        test_file1 = processed_tmp / 'test1.txt'
        test_file2 = processed_tmp / 'test2.nii'
        test_file1.write_text('test content')
        test_file2.write_text('test image data')
        
        # Verify files exist
        self.assertTrue(test_file1.exists())
        self.assertTrue(test_file2.exists())
        
        # Act
        SubjectFileService.clear_processed_tmp(self.subject_path)
        
        # Assert
        self.assertTrue(processed_tmp.exists(), "processed_tmp directory should still exist")
        self.assertFalse(test_file1.exists(), "test1.txt should be deleted")
        self.assertFalse(test_file2.exists(), "test2.nii should be deleted")
        
        # Directory should be empty
        self.assertEqual(len(list(processed_tmp.iterdir())), 0, "processed_tmp should be empty")
    
    def test_clear_processed_tmp_empty_directory(self):
        """Test clearing an empty processed_tmp directory."""
        # Arrange
        SubjectFileService.create_subject_directories(self.subject_path)
        processed_tmp = self.subject_path / 'processed_tmp'
        
        # Act
        SubjectFileService.clear_processed_tmp(self.subject_path)
        
        # Assert
        self.assertTrue(processed_tmp.exists(), "processed_tmp directory should still exist")
        self.assertEqual(len(list(processed_tmp.iterdir())), 0, "processed_tmp should be empty")
    
    def test_clear_processed_tmp_nonexistent_directory(self):
        """Test clearing processed_tmp when it doesn't exist."""
        # Arrange - don't create the directories
        
        # Act & Assert - should not raise an exception
        try:
            SubjectFileService.clear_processed_tmp(self.subject_path)
        except Exception as e:
            self.fail(f"clear_processed_tmp raised an exception: {e}")
    
    def test_get_mni_transformation_matrix_exists(self):
        """Test getting MNI transformation matrix when file exists."""
        # Arrange
        SubjectFileService.create_subject_directories(self.subject_path)
        pipeline_output = self.subject_path / 'pipeline_output'
        subject_name = self.subject_path.name
        mat_file = pipeline_output / f'MNI_{subject_name}_ref.mat'
        mat_file.write_text('matrix data')
        
        # Act
        result = SubjectFileService.get_mni_transformation_matrix(self.subject_path)
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result, mat_file)
        self.assertTrue(result.exists())
    
    def test_get_mni_transformation_matrix_file_not_exists(self):
        """Test getting MNI transformation matrix when file doesn't exist."""
        # Arrange
        SubjectFileService.create_subject_directories(self.subject_path)
        
        # Act
        result = SubjectFileService.get_mni_transformation_matrix(self.subject_path)
        
        # Assert
        self.assertIsNone(result)
    
    def test_get_mni_transformation_matrix_no_pipeline_output(self):
        """Test getting MNI transformation matrix when pipeline_output doesn't exist."""
        # Arrange - create subject path but not pipeline_output
        self.subject_path.mkdir(parents=True)
        
        # Act
        result = SubjectFileService.get_mni_transformation_matrix(self.subject_path)
        
        # Assert
        self.assertIsNone(result)
    
    def test_clear_processed_tmp_with_subdirectories(self):
        """Test clearing processed_tmp that contains subdirectories."""
        # Arrange
        SubjectFileService.create_subject_directories(self.subject_path)
        processed_tmp = self.subject_path / 'processed_tmp'
        
        # Create subdirectory with files
        subdir = processed_tmp / 'subdir'
        subdir.mkdir()
        test_file = subdir / 'nested_test.txt'
        test_file.write_text('nested content')
        
        # Act
        SubjectFileService.clear_processed_tmp(self.subject_path)
        
        # Assert
        self.assertTrue(processed_tmp.exists())
        self.assertFalse(subdir.exists())
        self.assertFalse(test_file.exists())


if __name__ == '__main__':
    unittest.main()