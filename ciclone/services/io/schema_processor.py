import os
from pathlib import Path
from typing import List, Tuple

from ciclone.utils.file_utils import FileUtils

# Required imports for PowerPoint processing
from docling.document_converter import DocumentConverter


class SchemaProcessor:
    """Service for processing schema files including PowerPoint conversion and multi-file handling."""
    
    @classmethod
    def is_supported_file(cls, file_path: str) -> bool:
        """Check if file is supported (image or PowerPoint)."""
        return (FileUtils.is_file_type(file_path, FileUtils.IMAGE_EXTENSIONS) or 
                FileUtils.is_file_type(file_path, FileUtils.POWERPOINT_EXTENSIONS))
    
    @classmethod
    def is_powerpoint_file(cls, file_path: str) -> bool:
        """Check if file is a PowerPoint file."""
        return FileUtils.is_file_type(file_path, FileUtils.POWERPOINT_EXTENSIONS)
    
    @classmethod
    def is_image_file(cls, file_path: str) -> bool:
        """Check if file is an image file."""
        return FileUtils.is_file_type(file_path, FileUtils.IMAGE_EXTENSIONS)
    
    @classmethod
    def convert_powerpoint_to_images(cls, ppt_path: str, output_dir: str, 
                                   output_format: str = 'png') -> Tuple[bool, List[str], str]:
        """
        Convert PowerPoint slides to structured content with images and text using Docling.
        
        Args:
            ppt_path: Path to PowerPoint file
            output_dir: Directory to save converted content
            output_format: Output image format ('png', 'jpg', 'tiff')
        
        Returns:
            Tuple of (success, list_of_output_paths, error_message)
        """
        try:
            # Ensure output directory exists
            if not FileUtils.ensure_directory(output_dir):
                return False, [], f"Cannot create output directory: {output_dir}"
            
            # Get base filename without extension
            base_name = Path(ppt_path).stem
            
            # Convert PowerPoint using Docling
            return cls._convert_ppt_with_docling(ppt_path, output_dir, base_name)
                
        except Exception as e:
            return False, [], f"PowerPoint conversion failed: {str(e)}"
    
    @classmethod
    def _convert_ppt_with_docling(cls, ppt_path: str, output_dir: str, base_name: str) -> Tuple[bool, List[str], str]:
        """Convert PowerPoint using Docling for advanced document understanding."""
        try:
            # Use Docling for PowerPoint conversion
            converter = DocumentConverter()
            result = converter.convert(ppt_path)
            
            if not result or not result.document:
                return False, [], "Docling failed to process PowerPoint file"
            
            # Extract markdown content from Docling result
            markdown_content = result.document.export_to_markdown()
            
            # Save markdown file
            markdown_filename = f"{base_name}_slides.md"
            markdown_path = os.path.join(output_dir, markdown_filename)
            
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            output_paths = [markdown_path]
            
            # Try to extract any embedded images from the document
            image_count = 0
            if hasattr(result.document, 'pictures') and result.document.pictures:
                print(f"Found {len(result.document.pictures)} images in PowerPoint, attempting extraction...")
                for i, picture in enumerate(result.document.pictures, 1):
                    try:
                        image_filename = f"{base_name}_image_{i:02d}.png"
                        image_path = os.path.join(output_dir, image_filename)
                        
                        # Extract image using Docling API
                        if hasattr(picture, 'get_image'):
                            img = picture.get_image(result.document)
                            if img:
                                img.save(image_path)
                                output_paths.append(image_path)
                                image_count += 1
                                print(f"Successfully extracted image {i}")
                            
                    except Exception as e:
                        print(f"Warning: Could not extract image {i}: {str(e)}")
                        continue
            else:
                print("No images found in PowerPoint document")
            
            # Count content for summary
            lines = markdown_content.split('\n')
            slide_count = len([line for line in lines if line.startswith('## ') or line.startswith('# ')])
            
            print(f"Created Docling markdown: {markdown_filename}")
            return True, output_paths, f"Successfully converted PowerPoint using Docling: {slide_count} sections, {image_count} images extracted, markdown created."
            
        except Exception as e:
            print(f"Docling conversion failed: {str(e)}")
            return False, [], f"Docling conversion failed: {str(e)}"
    


    @classmethod
    def copy_and_rename_images(cls, image_paths: List[str], output_dir: str, 
                              base_name: str = "schema") -> Tuple[bool, List[str], str]:
        """
        Copy multiple image files to output directory with consistent naming.
        
        Args:
            image_paths: List of source image file paths
            output_dir: Directory to copy images to
            base_name: Base name for renamed files
        
        Returns:
            Tuple of (success, list_of_copied_paths, error_message)
        """
        if not FileUtils.ensure_directory(output_dir):
            return False, [], f"Cannot create output directory: {output_dir}"
        
        copied_paths = []
        errors = []
        
        for i, image_path in enumerate(image_paths, 1):
            if not cls.is_image_file(image_path):
                continue
            
            # Generate new filename using utility
            file_ext = FileUtils.get_file_extension(image_path)
            new_filename = FileUtils.generate_filename(base_name, file_ext, i, len(image_paths))
            output_path = os.path.join(output_dir, new_filename)
            
            # Use centralized copy utility
            success, error = FileUtils.safe_copy_file(image_path, output_path)
            if success:
                copied_paths.append(output_path)
            else:
                errors.append(error)
        
        if copied_paths:
            error_msg = "; ".join(errors) if errors else ""
            return True, copied_paths, error_msg
        else:
            return False, [], "; ".join(errors) if errors else "No valid image files to copy"
    
    @classmethod
    def process_schema_files(cls, file_paths: List[str], output_dir: str, 
                           subject_name: str) -> Tuple[bool, List[str], str]:
        """
        Process schema files (images or PowerPoint) for a subject.
        
        Args:
            file_paths: List of file paths to process
            output_dir: Subject's output directory
            subject_name: Name of the subject (for naming)
        
        Returns:
            Tuple of (success, list_of_processed_files, error_message)
        """
        if not file_paths:
            return False, [], "No files provided"
        
        # Use the provided output directory directly (no subdirectory)
        if not FileUtils.ensure_directory(output_dir):
            return False, [], f"Cannot create output directory: {output_dir}"
        
        try:
            all_processed_files = []
            all_errors = []
            
            # Separate image files and PowerPoint files
            image_files = []
            powerpoint_files = []
            unsupported_files = []
            
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    all_errors.append(f"File not found: {file_path}")
                    continue
                
                if cls.is_powerpoint_file(file_path):
                    powerpoint_files.append(file_path)
                elif cls.is_image_file(file_path):
                    image_files.append(file_path)
                else:
                    unsupported_files.append(file_path)
            
            # Process all image files together (for proper numbering)
            if image_files:
                base_name = f"{subject_name}_schema"
                success, copied_paths, error = cls.copy_and_rename_images(
                    image_files, output_dir, base_name
                )
                if success:
                    all_processed_files.extend(copied_paths)
                    print(f"Copied {len(copied_paths)} image files")
                if error:
                    all_errors.append(f"Image processing: {error}")
            
            # Process each PowerPoint file
            for ppt_file in powerpoint_files:
                success, output_paths, error = cls.convert_powerpoint_to_images(
                    ppt_file, output_dir, 'png'
                )
                if success:
                    all_processed_files.extend(output_paths)
                    if error:  # Warning message
                        all_errors.append(f"PowerPoint conversion warning: {error}")
                else:
                    all_errors.append(f"PowerPoint conversion failed: {error}")
            
            # Report unsupported files
            for unsupported_file in unsupported_files:
                all_errors.append(f"Unsupported file format: {unsupported_file}")
            
            # Combine results
            overall_success = len(all_processed_files) > 0
            error_message = "; ".join(all_errors) if all_errors else ""
            
            return overall_success, all_processed_files, error_message
            
        except Exception as e:
            return False, [], f"Schema processing failed: {str(e)}"
    
    @classmethod
    def get_supported_extensions_filter(cls) -> str:
        """Get file filter string for supported schema files."""
        file_types = {
            "Image files": FileUtils.IMAGE_EXTENSIONS,
            "PowerPoint files": FileUtils.POWERPOINT_EXTENSIONS
        }
        return FileUtils.create_file_filter(file_types) 