import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont


class PreviewDialog(QDialog):
    """Simple preview dialog for images and text files using Qt's built-in widgets."""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Preview - {os.path.basename(file_path)}")
        self.setModal(True)
        self.resize(800, 600)
        
        # Setup UI
        self._setup_ui()
        
        # Load content based on file type
        self._load_content()
    
    def _setup_ui(self):
        """Setup the basic UI layout."""
        layout = QVBoxLayout(self)
        
        # Main content area - scroll area for large content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget (will hold either image label or text edit)
        self.content_widget = None
        
        layout.addWidget(self.scroll_area)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _load_content(self):
        """Load and display the file content."""
        try:
            from ciclone.utils.file_utils import FileUtils
            
            if FileUtils.is_file_type(self.file_path, FileUtils.IMAGE_EXTENSIONS):
                self._load_image()
            elif FileUtils.is_file_type(self.file_path, FileUtils.MARKDOWN_EXTENSIONS):
                self._load_text()
            else:
                self._show_error("Unsupported file type")
                
        except Exception as e:
            self._show_error(f"Failed to load file: {str(e)}")
    
    def _load_image(self):
        """Load and display an image file."""
        try:
            # Create image label
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
            
            # Load pixmap
            pixmap = QPixmap(self.file_path)
            if pixmap.isNull():
                self._show_error("Failed to load image")
                return
            
            # Scale image to fit dialog while maintaining aspect ratio
            # Max size is 90% of dialog size to leave room for controls
            max_width = int(self.width() * 0.9)
            max_height = int(self.height() * 0.8)
            
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(
                    max_width, max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            image_label.setPixmap(pixmap)
            image_label.setMinimumSize(pixmap.size())
            
            self.content_widget = image_label
            self.scroll_area.setWidget(self.content_widget)
            
        except Exception as e:
            self._show_error(f"Failed to display image: {str(e)}")
    
    def _load_text(self):
        """Load and display a text/markdown file."""
        try:
            # Create text edit widget
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # Load file content
            try:
                with open(self.file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
            except UnicodeDecodeError:
                # Try with different encoding if UTF-8 fails
                with open(self.file_path, 'r', encoding='latin-1') as file:
                    content = file.read()
            
            # Check if this is a markdown file and render accordingly
            from ciclone.utils.file_utils import FileUtils
            if (FileUtils.is_file_type(self.file_path, {'.md', '.markdown'}) and 
                self._is_markdown_available()):
                # Render markdown as HTML
                html_content = self._render_markdown_to_html(content)
                text_edit.setHtml(html_content)
                
                # Style for HTML rendering
                text_edit.setStyleSheet("""
                    QTextEdit {
                        background-color: #ffffff;
                        color: #333333;
                        border: 1px solid #555;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 14px;
                        line-height: 1.6;
                        padding: 16px;
                    }
                """)
            else:
                # Display as plain text with monospace font
                font = QFont("Courier", 10)
                text_edit.setFont(font)
                text_edit.setPlainText(content)
                
                # Style for plain text
                text_edit.setStyleSheet("""
                    QTextEdit {
                        background-color: #2b2b2b;
                        color: #ffffff;
                        border: 1px solid #555;
                        font-family: 'Courier New', monospace;
                        padding: 16px;
                    }
                """)
            
            self.content_widget = text_edit
            self.scroll_area.setWidget(self.content_widget)
            
        except Exception as e:
            self._show_error(f"Failed to display text: {str(e)}")
    
    def _is_markdown_available(self):
        """Check if markdown library is available."""
        try:
            import markdown
            return True
        except ImportError:
            return False
    
    def _render_markdown_to_html(self, markdown_content: str) -> str:
        """Convert markdown content to HTML with nice styling."""
        try:
            import markdown
            import os
            import re
            
            # Fix image paths to be absolute for proper display in QTextEdit
            fixed_markdown_content = self._fix_image_paths(markdown_content)
            
            # Create markdown instance with useful extensions
            md = markdown.Markdown(
                extensions=[
                    'extra',      # Adds tables, fenced code blocks, footnotes, etc.
                    'toc',        # Table of contents
                    'codehilite'  # Syntax highlighting for code blocks
                ],
                extension_configs={
                    'codehilite': {
                        'css_class': 'highlight',
                        'use_pygments': False  # Use simple highlighting
                    }
                }
            )
            
            # Convert markdown to HTML
            html = md.convert(fixed_markdown_content)
            
            # Wrap in a styled container with CSS that exactly matches Cursor's markdown.css
            styled_html = f"""
            <html>
            <head>
            <style>
                html, body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe WPC", "Segoe UI", system-ui, "Ubuntu", "Droid Sans", sans-serif;
                    font-size: 14px;
                    padding: 0 26px;
                    line-height: 22px;
                    word-wrap: break-word;
                    margin: 0;
                    background-color: #ffffff;
                }}
                body {{
                    padding-top: 1em;
                }}
                /* Reset margin top for elements */
                h1, h2, h3, h4, h5, h6,
                p, ol, ul, pre {{
                    margin-top: 0;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    font-weight: 600;
                    margin-top: 24px;
                    margin-bottom: 16px;
                    line-height: 1.25;
                }}
                /* Prevent `sub` and `sup` elements from affecting line height */
                sub,
                sup {{
                    line-height: 0;
                }}
                ul ul:first-child,
                ul ol:first-child,
                ol ul:first-child,
                ol ol:first-child {{
                    margin-bottom: 0;
                }}
                img, video {{
                    max-width: 100%;
                    max-height: 100%;
                }}
                a {{
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                p {{
                    margin-bottom: 16px;
                }}
                li p {{
                    margin-bottom: 0.7em;
                }}
                ul,
                ol {{
                    margin-bottom: 0.7em;
                }}
                hr {{
                    border: 0;
                    height: 1px;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.18);
                }}
                h1 {{
                    font-size: 2em;
                    margin-top: 0;
                    padding-bottom: 0.3em;
                    border-bottom-width: 1px;
                    border-bottom-style: solid;
                    border-color: rgba(0, 0, 0, 0.18);
                }}
                h2 {{
                    font-size: 1.5em;
                    padding-bottom: 0.3em;
                    border-bottom-width: 1px;
                    border-bottom-style: solid;
                    border-color: rgba(0, 0, 0, 0.18);
                }}
                h3 {{
                    font-size: 1.25em;
                }}
                h4 {{
                    font-size: 1em;
                }}
                h5 {{
                    font-size: 0.875em;
                }}
                h6 {{
                    font-size: 0.85em;
                }}
                table {{
                    border-collapse: collapse;
                    margin-bottom: 0.7em;
                }}
                th {{
                    text-align: left;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.69);
                }}
                th,
                td {{
                    padding: 5px 10px;
                }}
                table > tbody > tr + tr > td {{
                    border-top: 1px solid rgba(0, 0, 0, 0.18);
                }}
                blockquote {{
                    margin: 0;
                    padding: 0px 16px 0 10px;
                    border-left-width: 5px;
                    border-left-style: solid;
                    border-left-color: rgba(0, 0, 0, 0.18);
                    border-radius: 2px;
                }}
                code {{
                    font-family: "SF Mono", Monaco, Menlo, Consolas, "Ubuntu Mono", "Liberation Mono", "DejaVu Sans Mono", "Courier New", monospace;
                    font-size: 1em;
                    line-height: 1.357em;
                }}
                pre {{
                    padding: 16px;
                    border-radius: 3px;
                    overflow: auto;
                    background-color: #f8f8f8;
                    border: 1px solid #e1e1e1;
                }}
                pre code {{
                    display: inline-block;
                    tab-size: 4;
                    background: none;
                }}
                strong {{ font-weight: 600; }}
                em {{ font-style: italic; }}
                del {{ text-decoration: line-through; }}
            </style>
            </head>
            <body>
            {html}
            </body>
            </html>
            """
            
            return styled_html
            
        except Exception as e:
            # Fallback to plain text if markdown processing fails
            return f"<pre style='white-space: pre-wrap; font-family: monospace;'>{markdown_content}</pre>"
    
    def _fix_image_paths(self, markdown_content: str) -> str:
        """Fix relative image paths to absolute paths for proper display in QTextEdit."""
        import os
        import re
        
        # Get the directory containing the markdown file
        markdown_dir = os.path.dirname(self.file_path)
        
        # Pattern to match markdown image syntax: ![alt text](image_path)
        image_pattern = r'!\[(.*?)\]\(([^)]+)\)'
        
        def replace_image_path(match):
            alt_text = match.group(1)
            image_path = match.group(2)
            
            # If it's already an absolute path or URL, don't change it
            if os.path.isabs(image_path) or image_path.startswith(('http://', 'https://', 'file://')):
                return match.group(0)
            
            # Convert relative path to absolute path
            absolute_path = os.path.join(markdown_dir, image_path)
            
            # Check if the image file exists
            if os.path.exists(absolute_path):
                # Convert to file:// URL for Qt to properly display
                file_url = f"file://{absolute_path}"
                return f"![{alt_text}]({file_url})"
            else:
                # If image doesn't exist, show a placeholder
                return f"![{alt_text} (Image not found: {image_path})](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2Y2ZjhmYSIgc3Ryb2tlPSIjZGZlMmU1IiBzdHJva2Utd2lkdGg9IjIiLz48dGV4dCB4PSIxMDAiIHk9IjUwIiBmb250LXNpemU9IjE0IiBmaWxsPSIjNTg2MDY5IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+SW1hZ2UgTm90IEZvdW5kPC90ZXh0Pjwvc3ZnPg==)"
        
        # Replace all image references
        fixed_content = re.sub(image_pattern, replace_image_path, markdown_content)
        
        return fixed_content
    
    def _show_error(self, message: str):
        """Display an error message."""
        error_label = QLabel(f"Error: {message}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
        
        self.content_widget = error_label
        self.scroll_area.setWidget(self.content_widget)
    
    def resizeEvent(self, event):
        """Handle dialog resize to rescale image if needed."""
        super().resizeEvent(event)
        
        # Re-scale image if it's an image dialog
        if (self.content_widget and 
            isinstance(self.content_widget, QLabel) and 
            self.content_widget.pixmap()):
            
            try:
                from ciclone.utils.file_utils import FileUtils
                if FileUtils.is_file_type(self.file_path, FileUtils.IMAGE_EXTENSIONS):
                    # Reload image with new size constraints
                    self._load_image()
            except:
                pass  # Ignore resize errors 