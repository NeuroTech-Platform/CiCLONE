"""
Subject Data Factory for CiCLONE Application

This factory handles the creation of SubjectData objects from various sources,
moving business logic out of controllers and into the model layer.
"""

from typing import Dict, Any, List
from .subject_model import SubjectData


class SubjectDataFactory:
    """Factory for creating SubjectData objects with proper business logic encapsulation."""
    
    @staticmethod
    def create_from_form_data(form_data: Dict[str, Any]) -> SubjectData:
        """
        Create a SubjectData object from form data.
        
        Args:
            form_data: Dictionary containing form field values
            
        Returns:
            SubjectData: Configured subject data object
            
        Raises:
            KeyError: If required 'name' field is missing
        """
        if 'name' not in form_data:
            raise KeyError("Subject name is required")
        
        # Create subject data object with form values
        subject_data = SubjectData(
            name=form_data['name'],
            schema=form_data.get('schema', ''),
            pre_ct=form_data.get('pre_ct', ''),
            pre_mri=form_data.get('pre_mri', ''),
            post_ct=form_data.get('post_ct', ''),
            post_mri=form_data.get('post_mri', '')
        )
        
        # Set schema files if provided
        if 'schema_files' in form_data:
            subject_data.set_schema_files(form_data['schema_files'])
        
        return subject_data
    
    @staticmethod
    def create_from_values(name: str, schema: str = '', pre_ct: str = '', 
                          pre_mri: str = '', post_ct: str = '', post_mri: str = '',
                          schema_files: List[str] = None) -> SubjectData:
        """
        Create a SubjectData object from individual values.
        
        Args:
            name: Subject name (required)
            schema: Legacy schema path
            pre_ct: Pre-operative CT path
            pre_mri: Pre-operative MRI path
            post_ct: Post-operative CT path
            post_mri: Post-operative MRI path
            schema_files: List of schema file paths
            
        Returns:
            SubjectData: Configured subject data object
        """
        subject_data = SubjectData(
            name=name,
            schema=schema,
            pre_ct=pre_ct,
            pre_mri=pre_mri,
            post_ct=post_ct,
            post_mri=post_mri
        )
        
        if schema_files:
            subject_data.set_schema_files(schema_files)
        
        return subject_data