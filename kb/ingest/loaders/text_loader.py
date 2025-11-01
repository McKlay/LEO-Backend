"""Text file loader for knowledge base ingestion."""
from pathlib import Path
from typing import Optional

from core import get_logger

logger = get_logger(__name__)


class TextFileLoader:
    """
    Simple text file loader for .txt documents.
    
    Handles UTF-8 encoded legal documents with basic cleaning.
    """
    
    def __init__(self, encoding: str = "utf-8"):
        """
        Initialize text file loader.
        
        Args:
            encoding: Text file encoding (default: utf-8)
        """
        self.encoding = encoding
    
    def load(self, file_path: str | Path) -> str:
        """
        Load text file content.
        
        Args:
            file_path: Path to text file
            
        Returns:
            File content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: If file encoding is incorrect
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Basic cleaning
            content = self._clean_content(content)
            
            logger.info(
                f"Loaded text file: {file_path.name} "
                f"({len(content)} chars, {len(content.split())} words)"
            )
            
            return content
            
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {file_path}: {str(e)}")
            # Try with fallback encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                logger.warning(f"Loaded {file_path} with latin-1 encoding fallback")
                return self._clean_content(content)
            except Exception as fallback_error:
                raise UnicodeDecodeError(
                    self.encoding,
                    b'',
                    0,
                    1,
                    f"Failed to decode {file_path} with {self.encoding} or latin-1"
                ) from fallback_error
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}", exc_info=True)
            raise
    
    def _clean_content(self, content: str) -> str:
        """
        Basic content cleaning.
        
        Args:
            content: Raw file content
            
        Returns:
            Cleaned content
        """
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive whitespace
        lines = [line.rstrip() for line in content.split('\n')]
        
        # Remove excessive blank lines (max 2 consecutive)
        cleaned_lines = []
        blank_count = 0
        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append(line)
            else:
                blank_count = 0
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def load_multiple(self, file_paths: list[str | Path]) -> dict[str, str]:
        """
        Load multiple text files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary mapping file names to content
        """
        results = {}
        
        for path in file_paths:
            path = Path(path)
            try:
                content = self.load(path)
                results[path.name] = content
            except Exception as e:
                logger.error(f"Failed to load {path}: {str(e)}")
                # Continue with other files
        
        logger.info(f"Loaded {len(results)}/{len(file_paths)} text files")
        return results
