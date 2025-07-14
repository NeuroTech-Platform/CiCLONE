"""
Unit tests for the Subject domain object.

Tests the updated Subject class that has been refactored to be a pure domain object
with file I/O operations extracted to the SubjectFileService.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from ciclone.domain.subject import Subject


class TestSubjectDomain(unittest.TestCase):
    """Test cases for the updated Subject domain object."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.subject_path = Path(self.temp_dir) / "test_subject"
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_subject_initialization(self):
        """Test that Subject initializes with correct path structure."""
        # Act
        subject = Subject(self.subject_path)
        
        # Assert
        self.assertEqual(subject.folder_path, self.subject_path)
        self.assertEqual(subject.documents, self.subject_path / 'documents')
        self.assertEqual(subject.postop_ct, self.subject_path / 'images' / 'postop' / 'ct')
        self.assertEqual(subject.postop_mri, self.subject_path / 'images' / 'postop' / 'mri')
        self.assertEqual(subject.preop_ct, self.subject_path / 'images' / 'preop' / 'ct')
        self.assertEqual(subject.preop_mri, self.subject_path / 'images' / 'preop' / 'mri')
        self.assertEqual(subject.processed_tmp, self.subject_path / 'processed_tmp')
        self.assertEqual(subject.pipeline_output, self.subject_path / 'pipeline_output')
    
    def test_subject_initialization_with_string_path(self):
        """Test that Subject accepts string paths."""
        # Act
        subject = Subject(str(self.subject_path))
        
        # Assert
        self.assertEqual(subject.folder_path, self.subject_path)
        self.assertEqual(subject.get_subject_name(), "test_subject")
    
    def test_get_subject_name(self):
        """Test getting the subject name from the folder path."""
        # Arrange
        subject = Subject(self.subject_path)
        
        # Act
        name = subject.get_subject_name()
        
        # Assert
        self.assertEqual(name, "test_subject")
    
    def test_get_subject_name_with_nested_path(self):
        """Test getting subject name from nested path."""
        # Arrange
        nested_path = self.temp_dir / "parent" / "child" / "nested_subject"
        subject = Subject(nested_path)
        
        # Act
        name = subject.get_subject_name()
        
        # Assert
        self.assertEqual(name, "nested_subject")
    
    def test_no_automatic_directory_creation(self):
        """Test that Subject no longer creates directories automatically."""
        # Act
        subject = Subject(self.subject_path)
        
        # Assert - directories should NOT be created automatically
        self.assertFalse(subject.folder_path.exists())
        self.assertFalse(subject.documents.exists())
        self.assertFalse(subject.postop_ct.exists())
        self.assertFalse(subject.processed_tmp.exists())
    
    def test_get_file_with_pattern_matching(self):
        """Test finding files with pattern matching."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        processed_tmp = self.subject_path / 'processed_tmp'
        processed_tmp.mkdir(parents=True)
        
        # Create test files
        test_file1 = processed_tmp / 'test_brain.nii.gz'
        test_file2 = processed_tmp / 'other_data.nii'
        test_file1.write_text('test data')
        test_file2.write_text('other data')
        
        subject = Subject(self.subject_path)
        
        # Act
        found_file = subject.get_file('brain')
        
        # Assert
        self.assertIsNotNone(found_file)
        self.assertEqual(found_file.name, 'test_brain.nii.gz')
    
    def test_get_file_not_found(self):
        """Test getting a file that doesn't exist."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        subject = Subject(self.subject_path)
        
        # Act
        found_file = subject.get_file('nonexistent')
        
        # Assert
        self.assertIsNone(found_file)
    
    def test_get_file_with_specific_directory(self):
        """Test finding files in a specific directory."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        documents = self.subject_path / 'documents'
        documents.mkdir(parents=True)
        
        test_file = documents / 'schema.txt'
        test_file.write_text('schema data')
        
        subject = Subject(self.subject_path)
        
        # Act
        found_file = subject.get_file('.txt', search_dir='documents')
        
        # Assert
        self.assertIsNotNone(found_file)
        self.assertEqual(found_file.name, 'schema.txt')
    
    def test_get_file_priority_processed_tmp(self):
        """Test that get_file prioritizes processed_tmp directory."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        processed_tmp = self.subject_path / 'processed_tmp'
        documents = self.subject_path / 'documents'
        processed_tmp.mkdir(parents=True)
        documents.mkdir(parents=True)
        
        # Create files with same pattern in different directories
        processed_file = processed_tmp / 'test.nii'
        documents_file = documents / 'test.nii'
        processed_file.write_text('processed data')
        documents_file.write_text('documents data')
        
        subject = Subject(self.subject_path)
        
        # Act
        found_file = subject.get_file('test')
        
        # Assert - should find the one in processed_tmp first
        self.assertEqual(found_file, processed_file)
    
    def test_get_folder(self):
        """Test finding folders by pattern."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        test_folder = self.subject_path / 'test_analysis'
        test_folder.mkdir(parents=True)
        
        subject = Subject(self.subject_path)
        
        # Act
        found_folder = subject.get_folder('analysis')
        
        # Assert
        self.assertIsNotNone(found_folder)
        self.assertEqual(found_folder.name, 'test_analysis')
        self.assertTrue(found_folder.is_dir())
    
    def test_get_folder_not_found(self):
        """Test getting a folder that doesn't exist."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        subject = Subject(self.subject_path)
        
        # Act
        found_folder = subject.get_folder('nonexistent')
        
        # Assert
        self.assertIsNone(found_folder)
    
    def test_get_mni_transformation_matrix_exists(self):
        """Test getting MNI transformation matrix when it exists."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        pipeline_output = self.subject_path / 'pipeline_output'
        pipeline_output.mkdir(parents=True)
        
        mat_file = pipeline_output / 'MNI_test_subject_ref_brain.mat'
        mat_file.write_text('matrix data')
        
        subject = Subject(self.subject_path)
        
        # Act
        result = subject.get_mni_transformation_matrix()
        
        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result, mat_file)
    
    def test_get_mni_transformation_matrix_not_exists(self):
        """Test getting MNI transformation matrix when file doesn't exist."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        pipeline_output = self.subject_path / 'pipeline_output'
        pipeline_output.mkdir(parents=True)
        
        subject = Subject(self.subject_path)
        
        # Act
        result = subject.get_mni_transformation_matrix()
        
        # Assert
        self.assertIsNone(result)
    
    def test_get_mni_transformation_matrix_no_pipeline_output(self):
        """Test getting MNI transformation matrix when pipeline_output doesn't exist."""
        # Arrange
        self.subject_path.mkdir(parents=True)
        subject = Subject(self.subject_path)
        
        # Act
        result = subject.get_mni_transformation_matrix()
        
        # Assert
        self.assertIsNone(result)
    
    def test_subject_is_immutable_value_object(self):
        """Test that Subject behaves as an immutable value object."""
        # Arrange
        subject1 = Subject(self.subject_path)
        subject2 = Subject(self.subject_path)
        different_subject = Subject(self.subject_path / "different")
        
        # Assert - same path should result in equivalent objects
        self.assertEqual(subject1.folder_path, subject2.folder_path)
        self.assertEqual(subject1.get_subject_name(), subject2.get_subject_name())
        
        # Different paths should be different
        self.assertNotEqual(subject1.folder_path, different_subject.folder_path)
        self.assertNotEqual(subject1.get_subject_name(), different_subject.get_subject_name())
    
    def test_path_properties_are_readonly(self):
        """Test that path properties maintain their relationships."""
        # Arrange
        subject = Subject(self.subject_path)
        
        # Act & Assert - properties should maintain correct relationships
        self.assertTrue(str(subject.documents).startswith(str(subject.folder_path)))
        self.assertTrue(str(subject.postop_ct).startswith(str(subject.folder_path)))
        self.assertTrue(str(subject.preop_mri).startswith(str(subject.folder_path)))
        self.assertTrue(str(subject.processed_tmp).startswith(str(subject.folder_path)))
        self.assertTrue(str(subject.pipeline_output).startswith(str(subject.folder_path)))
        
        # Check specific path structures
        self.assertIn('images/postop/ct', str(subject.postop_ct))
        self.assertIn('images/preop/mri', str(subject.preop_mri))


if __name__ == '__main__':
    unittest.main()