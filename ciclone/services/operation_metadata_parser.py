"""
Operation metadata parser for extracting docstring information from operations.py
"""
import inspect
from typing import Dict, Optional, Any

from ciclone.services.processing import operations


class OperationMetadataParser:
    """
    Parses operation functions to extract metadata from docstrings for UI display.
    """
    
    def __init__(self):
        self._metadata_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._config_mapping: Optional[Dict[str, str]] = None
    
    def get_all_operations(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns metadata for all operations parsed from the operations module.
        Includes both config names and function names for compatibility.
        
        Returns:
            Dictionary mapping operation names to their metadata
        """
        if self._metadata_cache is None:
            self._metadata_cache = self._parse_operations()
        return self._metadata_cache
    
    def get_operation_metadata(self, operation_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns metadata for a specific operation.
        
        Args:
            operation_name: Name of the operation function
            
        Returns:
            Operation metadata dictionary or None if not found
        """
        all_ops = self.get_all_operations()
        return all_ops.get(operation_name)
    
    def _parse_operations(self) -> Dict[str, Dict[str, Any]]:
        """
        Parses all operation functions from the operations module.
        Prioritizes config names over function names to avoid duplicates.
        
        Returns:
            Dictionary mapping operation names to their parsed metadata
        """
        metadata = {}
        config_mapping = self.get_config_to_function_mapping()
        reverse_mapping = {v: k for k, v in config_mapping.items()}  # function_name -> config_name
        
        # Get all functions from the operations module
        for name, func in inspect.getmembers(operations, inspect.isfunction):
            # Skip private functions
            if name.startswith('_'):
                continue
                
            # Parse the function docstring and signature
            operation_data = self._parse_function(func)
            if operation_data:
                # If this function has a config name, use the config name instead
                if name in reverse_mapping:
                    config_name = reverse_mapping[name]
                    operation_data['config_name'] = config_name
                    operation_data['function_name'] = name
                    # Use config name as the key to avoid duplicates
                    metadata[config_name] = operation_data
                else:
                    # No config name exists, use function name
                    metadata[name] = operation_data
        
        return metadata
    
    def _parse_function(self, func) -> Optional[Dict[str, Any]]:
        """
        Parses a single function to extract its metadata.
        Combines signature information with docstring documentation.
        
        Args:
            func: Function object to parse
            
        Returns:
            Dictionary with operation metadata or None if parsing fails
        """
        try:
            # Get function signature
            signature = inspect.signature(func)
            
            # Get docstring
            docstring = inspect.getdoc(func)
            if not docstring:
                return None
            
            # Parse docstring sections
            parsed_doc = self._parse_docstring(docstring)
            
            # Extract parameter information from signature
            sig_parameters = self._extract_parameters(signature)
            
            # Merge docstring parameter descriptions with signature information
            merged_parameters = self._merge_parameter_info(sig_parameters, parsed_doc.get('parameters', {}))
            
            return {
                'name': func.__name__,
                'description': parsed_doc.get('description', ''),
                'parameters': merged_parameters,
                'example': parsed_doc.get('example', {}),
                'display_name': self._format_display_name(func.__name__)
            }
            
        except Exception as e:
            print(f"Error parsing function {func.__name__}: {e}")
            return None
    
    def _parse_docstring(self, docstring: str) -> Dict[str, Any]:
        """
        Parses a Google-style docstring to extract structured information.
        Uses unified Parameters section only.
        
        Args:
            docstring: The function's docstring
            
        Returns:
            Dictionary with parsed docstring sections
        """
        result = {
            'description': '',
            'parameters': {},
            'example': {}
        }
        
        # Split docstring into lines
        lines = docstring.strip().split('\n')
        
        current_section = 'description'
        current_content = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check for section headers
            if line_stripped == 'Parameters:':
                if current_content and current_section == 'description':
                    result['description'] = '\n'.join(current_content).strip()
                current_section = 'parameters'
                current_content = []
            elif line_stripped == 'Example:':
                current_section = 'example'
                current_content = []
            else:
                # Add content to current section
                if current_section == 'parameters' and line_stripped and line.startswith('    '):
                    # Parse parameter entry (format: "param_name: description")
                    if ':' in line_stripped:
                        param_name, param_desc = line_stripped.split(':', 1)
                        result['parameters'][param_name.strip()] = {
                            'description': param_desc.strip()
                        }
                elif current_section == 'example':
                    if ':' in line_stripped and not line.startswith(' '):
                        key, value = line_stripped.split(':', 1)
                        result['example'][key.strip().lower()] = value.strip()
                    elif line_stripped:
                        current_content.append(line_stripped)
                elif current_section == 'description' and line_stripped:
                    current_content.append(line_stripped)
        
        # Handle final section
        if current_content:
            if current_section == 'description':
                result['description'] = '\n'.join(current_content).strip()
            elif current_section == 'example' and 'description' not in result['example']:
                result['example']['description'] = '\n'.join(current_content).strip()
        
        return result
    
    def _extract_parameters(self, signature: inspect.Signature) -> Dict[str, Dict[str, Any]]:
        """
        Extracts parameter information from function signature.
        
        Args:
            signature: Function signature object
            
        Returns:
            Dictionary mapping parameter names to their info
        """
        parameters = {}
        
        for param_name, param in signature.parameters.items():
            # Determine if this is a file parameter based on type hint
            type_str = self._format_type_annotation(param.annotation)
            is_file = 'Path' in type_str or param_name.endswith('_file') or param_name.endswith('_path')
            
            param_info = {
                'name': param_name,
                'type': type_str,
                'required': param.default == inspect.Parameter.empty,
                'default': None if param.default == inspect.Parameter.empty else param.default,
                'is_file': is_file,
                'display_name': self._format_parameter_display_name(param_name)
            }
            parameters[param_name] = param_info
        
        return parameters
    
    def _merge_parameter_info(self, sig_params: Dict[str, Dict[str, Any]], 
                             doc_params: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Merge parameter information from signature with docstring descriptions.
        
        Args:
            sig_params: Parameters extracted from function signature
            doc_params: Parameters extracted from docstring
            
        Returns:
            Merged parameter information
        """
        merged = sig_params.copy()
        
        # Add descriptions from docstring
        for param_name, doc_info in doc_params.items():
            if param_name in merged:
                merged[param_name]['description'] = doc_info.get('description', '')
            else:
                # Parameter in docstring but not in signature (shouldn't happen)
                print(f"Warning: Parameter '{param_name}' in docstring but not in signature")
        
        return merged
    
    def _format_parameter_display_name(self, param_name: str) -> str:
        """
        Format parameter name for display in UI.
        
        Args:
            param_name: Original parameter name
            
        Returns:
            Human-readable display name
        """
        # Convert snake_case to Title Case
        words = param_name.replace('_', ' ').split()
        return ' '.join(word.capitalize() for word in words)
    
    def _format_type_annotation(self, annotation) -> str:
        """
        Formats type annotation for display.
        
        Args:
            annotation: Type annotation from function signature
            
        Returns:
            Formatted type string
        """
        if annotation == inspect.Parameter.empty:
            return 'Any'
        
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        
        # Handle Union types, Path, etc.
        return str(annotation).replace('typing.', '').replace('<class \'', '').replace('\'>', '')
    
    def _format_display_name(self, function_name: str) -> str:
        """
        Formats function name for display in UI.
        
        Args:
            function_name: Original function name
            
        Returns:
            Human-readable display name
        """
        # Convert snake_case to Title Case
        words = function_name.split('_')
        return ' '.join(word.capitalize() for word in words)
    
    def get_config_to_function_mapping(self) -> Dict[str, str]:
        """
        Extract the mapping from config operation names to function names by parsing stages.py
        
        Returns:
            Dictionary mapping config names to function names
        """
        if self._config_mapping is None:
            self._config_mapping = self._parse_stages_mapping()
        return self._config_mapping
    
    def _parse_stages_mapping(self) -> Dict[str, str]:
        """
        Parse stages.py to extract the operation type to function mapping.
        
        Returns:
            Dictionary mapping config operation types to function names
        """
        import re
        from pathlib import Path
        
        # Read stages.py file  
        stages_file = Path(__file__).parent / 'processing' / 'stages.py'
        
        try:
            with open(stages_file, 'r') as f:
                content = f.read()
            
            # Extract mapping from the get_operation_function dictionary
            mapping = {}
            
            # Pattern to match: 'crop': crop_image,
            pattern = r"'([^']+)':\s*([a-zA-Z_][a-zA-Z0-9_]*)"
            
            # Find the operation_map dictionary section
            operation_map_match = re.search(r'operation_map\s*=\s*\{([^}]+)\}', content, re.DOTALL)
            if operation_map_match:
                map_content = operation_map_match.group(1)
                matches = re.findall(pattern, map_content)
                for config_name, function_name in matches:
                    mapping[config_name] = function_name
            
            return mapping
            
        except Exception as e:
            print(f"Warning: Could not parse stages.py mapping: {e}")
            return {}
    
    def resolve_operation_name(self, config_name: str) -> str:
        """
        Resolve a config operation name to the actual function name.
        
        Args:
            config_name: Operation name as used in config files
            
        Returns:
            Function name as defined in operations.py
        """
        mapping = self.get_config_to_function_mapping()
        return mapping.get(config_name, config_name)