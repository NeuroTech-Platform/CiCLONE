"""
Unit tests for SubjectDataFactory.

Tests the factory that was created to extract business logic from controllers
and move subject data creation to the appropriate model layer.
"""

import unittest
from unittest.mock import Mock, patch
import sys

# Mock SubjectData for testing
class MockSubjectData:
    def __init__(self, name, schema='', pre_ct='', pre_mri='', post_ct='', post_mri=''):
        self.name = name
        self.schema = schema
        self.pre_ct = pre_ct
        self.pre_mri = pre_mri
        self.post_ct = post_ct
        self.post_mri = post_mri
        self.schema_files = []
        self._post_init_called = True
    
    def set_schema_files(self, file_paths):
        self.schema_files = file_paths if file_paths else []
    
    def get_schema_files(self):
        return self.schema_files

# Mock the SubjectData import
with patch.dict('sys.modules', {'ciclone.models.subject_model': Mock()}):
    sys.modules['ciclone.models.subject_model'].SubjectData = MockSubjectData
    from ciclone.models.subject_data_factory import SubjectDataFactory


class TestSubjectDataFactory(unittest.TestCase):
    """Test cases for SubjectDataFactory."""
    
    def test_create_from_form_data_basic(self):
        """Test creating SubjectData from basic form data."""
        # Arrange
        form_data = {
            'name': 'TestSubject',
            'schema': 'test.schema',
            'pre_ct': 'pre_ct.nii',
            'pre_mri': 'pre_mri.nii',
            'post_ct': 'post_ct.nii',
            'post_mri': 'post_mri.nii'
        }
        
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_form_data(form_data)
        
        # Assert
        self.assertEqual(subject_data.name, 'TestSubject')
        self.assertEqual(subject_data.schema, 'test.schema')
        self.assertEqual(subject_data.pre_ct, 'pre_ct.nii')
        self.assertEqual(subject_data.pre_mri, 'pre_mri.nii')
        self.assertEqual(subject_data.post_ct, 'post_ct.nii')
        self.assertEqual(subject_data.post_mri, 'post_mri.nii')
    
    def test_create_from_form_data_minimal(self):
        """Test creating SubjectData with only required name field."""
        # Arrange
        form_data = {'name': 'MinimalSubject'}
        
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_form_data(form_data)
        
        # Assert
        self.assertEqual(subject_data.name, 'MinimalSubject')
        self.assertEqual(subject_data.schema, '')
        self.assertEqual(subject_data.pre_ct, '')
        self.assertEqual(subject_data.pre_mri, '')
        self.assertEqual(subject_data.post_ct, '')
        self.assertEqual(subject_data.post_mri, '')
    
    def test_create_from_form_data_with_schema_files(self):
        """Test creating SubjectData with schema files."""
        # Arrange
        form_data = {
            'name': 'SchemaSubject',
            'schema_files': ['schema1.txt', 'schema2.txt', 'schema3.txt']
        }
        
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_form_data(form_data)
        
        # Assert
        self.assertEqual(subject_data.name, 'SchemaSubject')
        self.assertEqual(subject_data.schema_files, ['schema1.txt', 'schema2.txt', 'schema3.txt'])
    
    def test_create_from_form_data_missing_name_raises_error(self):
        """Test that missing name field raises KeyError."""
        # Arrange
        form_data = {
            'schema': 'test.schema',
            'pre_ct': 'pre_ct.nii'
            # Missing 'name' field
        }
        
        # Act & Assert
        with self.assertRaises(KeyError) as context:
            SubjectDataFactory.create_from_form_data(form_data)
        
        self.assertEqual(str(context.exception), "'Subject name is required'")
    
    def test_create_from_form_data_empty_name_raises_error(self):
        """Test that empty name field raises KeyError."""
        # Arrange
        form_data = {}  # Empty form data
        
        # Act & Assert
        with self.assertRaises(KeyError):
            SubjectDataFactory.create_from_form_data(form_data)
    
    def test_create_from_form_data_partial_fields(self):
        """Test creating SubjectData with some optional fields missing."""
        # Arrange
        form_data = {
            'name': 'PartialSubject',
            'pre_ct': 'pre_ct.nii',
            'post_mri': 'post_mri.nii'
            # Missing schema, pre_mri, post_ct
        }
        
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_form_data(form_data)
        
        # Assert
        self.assertEqual(subject_data.name, 'PartialSubject')
        self.assertEqual(subject_data.pre_ct, 'pre_ct.nii')
        self.assertEqual(subject_data.post_mri, 'post_mri.nii')
        self.assertEqual(subject_data.schema, '')  # Default value
        self.assertEqual(subject_data.pre_mri, '')  # Default value
        self.assertEqual(subject_data.post_ct, '')  # Default value
    
    def test_create_from_values_basic(self):
        """Test creating SubjectData from individual values."""
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_values(
                name='ValueSubject',
                schema='value.schema',
                pre_ct='value_pre_ct.nii',
                pre_mri='value_pre_mri.nii',
                post_ct='value_post_ct.nii',
                post_mri='value_post_mri.nii'
            )
        
        # Assert
        self.assertEqual(subject_data.name, 'ValueSubject')
        self.assertEqual(subject_data.schema, 'value.schema')
        self.assertEqual(subject_data.pre_ct, 'value_pre_ct.nii')
        self.assertEqual(subject_data.pre_mri, 'value_pre_mri.nii')
        self.assertEqual(subject_data.post_ct, 'value_post_ct.nii')
        self.assertEqual(subject_data.post_mri, 'value_post_mri.nii')
    
    def test_create_from_values_minimal(self):
        """Test creating SubjectData with only name."""
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_values(name='MinimalValueSubject')
        
        # Assert
        self.assertEqual(subject_data.name, 'MinimalValueSubject')
        self.assertEqual(subject_data.schema, '')
        self.assertEqual(subject_data.pre_ct, '')
        self.assertEqual(subject_data.pre_mri, '')
        self.assertEqual(subject_data.post_ct, '')
        self.assertEqual(subject_data.post_mri, '')
    
    def test_create_from_values_with_schema_files(self):
        """Test creating SubjectData from values with schema files."""
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_values(
                name='ValueSchemaSubject',
                schema_files=['value_schema1.txt', 'value_schema2.txt']
            )
        
        # Assert
        self.assertEqual(subject_data.name, 'ValueSchemaSubject')
        self.assertEqual(subject_data.schema_files, ['value_schema1.txt', 'value_schema2.txt'])
    
    def test_create_from_values_empty_schema_files(self):
        """Test creating SubjectData with empty schema files list."""
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_values(
                name='EmptySchemaSubject',
                schema_files=[]
            )
        
        # Assert
        self.assertEqual(subject_data.name, 'EmptySchemaSubject')
        self.assertEqual(subject_data.schema_files, [])
    
    def test_create_from_values_none_schema_files(self):
        """Test creating SubjectData with None schema files."""
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_values(
                name='NoneSchemaSubject',
                schema_files=None
            )
        
        # Assert
        self.assertEqual(subject_data.name, 'NoneSchemaSubject')
        # Should not set schema_files if None
        self.assertEqual(subject_data.schema_files, [])
    
    def test_factory_methods_are_static(self):
        """Test that factory methods can be called without instantiation."""
        # Act & Assert - should not raise any errors
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            # Test calling static methods directly on class
            subject_data1 = SubjectDataFactory.create_from_form_data({'name': 'Static1'})
            subject_data2 = SubjectDataFactory.create_from_values('Static2')
        
        self.assertEqual(subject_data1.name, 'Static1')
        self.assertEqual(subject_data2.name, 'Static2')
    
    def test_form_data_with_extra_fields(self):
        """Test that extra fields in form data are ignored."""
        # Arrange
        form_data = {
            'name': 'ExtraFieldsSubject',
            'pre_ct': 'test.nii',
            'extra_field': 'should_be_ignored',
            'another_extra': 123,
            'schema_files': ['schema.txt']
        }
        
        # Act
        with patch('ciclone.models.subject_data_factory.SubjectData', MockSubjectData):
            subject_data = SubjectDataFactory.create_from_form_data(form_data)
        
        # Assert
        self.assertEqual(subject_data.name, 'ExtraFieldsSubject')
        self.assertEqual(subject_data.pre_ct, 'test.nii')
        self.assertEqual(subject_data.schema_files, ['schema.txt'])
        # Extra fields should not cause errors


if __name__ == '__main__':
    unittest.main()