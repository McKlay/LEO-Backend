"""
Manual Chunk Loader for Day 4 KB Enhancement.

Loads manually chunked Markdown files with YAML frontmatter
from kb/chunks/ directory structure.
"""
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ManualChunk:
    """Represents a manually created chunk from Markdown file."""
    chunk_id: str
    title: str
    content: str
    article_number: str
    semantic_type: Optional[str] = None
    hierarchy: Optional[Dict[str, str]] = None
    keywords: Optional[List[str]] = None
    has_table: bool = False
    has_formula: bool = False
    has_list: bool = False
    
    # Metadata from metadata.json
    source: Optional[str] = None
    reference: Optional[str] = None
    doc_type: Optional[str] = None
    url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "content": self.content,
            "article_number": self.article_number,
            "semantic_type": self.semantic_type,
            "hierarchy": self.hierarchy,
            "keywords": self.keywords,
            "has_table": self.has_table,
            "has_formula": self.has_formula,
            "has_list": self.has_list,
            "source": self.source,
            "reference": self.reference,
            "doc_type": self.doc_type,
            "url": self.url
        }


class ManualChunkLoader:
    """
    Loads manually chunked documents from kb/chunks/ directory.
    
    Expected structure:
        kb/chunks/
        ├── PD-No-851/
        │   ├── metadata.json
        │   ├── 01-decree-main.md
        │   ├── 02-rules-preamble.md
        │   └── ...
        └── ...
    
    Each .md file has YAML frontmatter:
        ---
        chunk_id: unique_id
        title: Chunk title
        article_number: db_article_number
        keywords: [keyword1, keyword2]
        ---
        
        # Content here
    """
    
    def __init__(self):
        """Initialize loader."""
        self.chunks_dir = Path("kb/chunks")
        if not self.chunks_dir.exists():
            logger.warning(f"Chunks directory not found: {self.chunks_dir}")
    
    def load_metadata(self, document_folder: Path) -> Dict[str, Any]:
        """
        Load metadata.json from document folder.
        
        Args:
            document_folder: Path to document folder (e.g., kb/chunks/PD-No-851)
            
        Returns:
            Metadata dictionary
        """
        metadata_file = document_folder / "metadata.json"
        
        if not metadata_file.exists():
            logger.warning(f"No metadata.json found in {document_folder}")
            return {}
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            logger.info(f"Loaded metadata from {metadata_file.name}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to load metadata from {metadata_file}: {e}")
            return {}
    
    def load_chunk_file(
        self, 
        chunk_file: Path, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ManualChunk]:
        """
        Load a single Markdown chunk file with YAML frontmatter.
        
        Args:
            chunk_file: Path to .md file
            metadata: Optional document metadata from metadata.json
            
        Returns:
            ManualChunk object or None if parsing fails
        """
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            if not content.startswith('---'):
                logger.error(f"No YAML frontmatter found in {chunk_file.name}")
                return None
            
            # Split frontmatter and content
            parts = content.split('---', 2)
            if len(parts) < 3:
                logger.error(f"Invalid frontmatter format in {chunk_file.name}")
                return None
            
            # Parse YAML
            frontmatter = yaml.safe_load(parts[1])
            chunk_content = parts[2].strip()
            
            # Validate required fields
            required_fields = ['chunk_id', 'title', 'article_number']
            for field in required_fields:
                if field not in frontmatter:
                    logger.error(f"Missing required field '{field}' in {chunk_file.name}")
                    return None
            
            # Create ManualChunk object
            chunk = ManualChunk(
                chunk_id=frontmatter['chunk_id'],
                title=frontmatter['title'],
                article_number=frontmatter['article_number'],
                content=chunk_content,
                semantic_type=frontmatter.get('semantic_type'),
                hierarchy=frontmatter.get('hierarchy'),
                keywords=frontmatter.get('keywords', []),
                has_table=frontmatter.get('has_table', False),
                has_formula=frontmatter.get('has_formula', False),
                has_list=frontmatter.get('has_list', False)
            )
            
            # Add document metadata if available
            if metadata:
                chunk.source = metadata.get('source')
                chunk.reference = metadata.get('reference')
                chunk.doc_type = metadata.get('doc_type')
                chunk.url = metadata.get('url')
            
            logger.debug(f"Loaded chunk: {chunk.chunk_id} from {chunk_file.name}")
            return chunk
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {chunk_file.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load chunk from {chunk_file.name}: {e}")
            return None
    
    def load_document_chunks(
        self, 
        document_name: str
    ) -> List[ManualChunk]:
        """
        Load all chunks for a specific document.
        
        Args:
            document_name: Name of document folder (e.g., "PD-No-851")
            
        Returns:
            List of ManualChunk objects
        """
        document_folder = self.chunks_dir / document_name
        
        if not document_folder.exists():
            logger.error(f"Document folder not found: {document_folder}")
            return []
        
        # Load document metadata
        metadata = self.load_metadata(document_folder)
        
        # Find all .md files (recursively, to support subfolders)
        chunk_files = sorted(document_folder.rglob("*.md"))
        
        if not chunk_files:
            logger.warning(f"No .md files found in {document_folder}")
            return []
        
        logger.info(f"Found {len(chunk_files)} chunk files in {document_name}")
        
        # Load each chunk
        chunks = []
        for chunk_file in chunk_files:
            chunk = self.load_chunk_file(chunk_file, metadata)
            if chunk:
                chunks.append(chunk)
            else:
                logger.warning(f"Skipped invalid chunk file: {chunk_file.name}")
        
        logger.info(
            f"Successfully loaded {len(chunks)}/{len(chunk_files)} chunks "
            f"from {document_name}"
        )
        
        return chunks
    
    def load_all_chunks(self) -> Dict[str, List[ManualChunk]]:
        """
        Load all chunks from all documents in kb/chunks/.
        
        Returns:
            Dictionary mapping document names to lists of chunks
        """
        if not self.chunks_dir.exists():
            logger.error(f"Chunks directory not found: {self.chunks_dir}")
            return {}
        
        all_chunks = {}
        
        # Find all document folders (direct children of kb/chunks/)
        document_folders = [
            d for d in self.chunks_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]
        
        logger.info(f"Found {len(document_folders)} document folders in kb/chunks/")
        
        for folder in document_folders:
            document_name = folder.name
            chunks = self.load_document_chunks(document_name)
            
            if chunks:
                all_chunks[document_name] = chunks
                logger.info(f"✓ {document_name}: {len(chunks)} chunks")
            else:
                logger.warning(f"✗ {document_name}: No valid chunks found")
        
        total_chunks = sum(len(chunks) for chunks in all_chunks.values())
        logger.info(
            f"\nTotal: {total_chunks} chunks from {len(all_chunks)} documents"
        )
        
        return all_chunks
    
    def load_single_chunk_file(self, chunk_file_path: str) -> Optional[ManualChunk]:
        """
        Load a single chunk file by path.
        
        Args:
            chunk_file_path: Path to .md file (can be relative or absolute)
            
        Returns:
            ManualChunk object or None
        """
        chunk_path = Path(chunk_file_path)
        
        if not chunk_path.exists():
            logger.error(f"Chunk file not found: {chunk_path}")
            return None
        
        # Find parent document folder
        # Assume structure: kb/chunks/{document}/{file.md}
        try:
            document_folder = chunk_path.parent
            metadata = self.load_metadata(document_folder)
            return self.load_chunk_file(chunk_path, metadata)
        except Exception as e:
            logger.error(f"Failed to load single chunk from {chunk_path}: {e}")
            return None
