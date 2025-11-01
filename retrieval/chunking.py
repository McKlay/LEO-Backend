"""
Document chunking utilities for knowledge base ingestion.

Splits legal documents into semantically meaningful chunks with
proper metadata and citation tracking.
"""
import re
import hashlib
from typing import Optional
from dataclasses import dataclass

from core import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""
    id: str
    content: str
    metadata: dict
    char_count: int
    word_count: int


class LegalDocumentChunker:
    """
    Chunks legal documents preserving article/section structure.
    
    Optimized for Philippine legal texts with:
    - Article/Section detection
    - Citation preservation
    - Semantic coherence (100-300 words per chunk)
    """
    
    def __init__(
        self,
        min_chunk_words: int = 100,
        max_chunk_words: int = 300,
        overlap_words: int = 20
    ):
        """
        Initialize chunker with size parameters.
        
        Args:
            min_chunk_words: Minimum words per chunk
            max_chunk_words: Maximum words per chunk
            overlap_words: Words to overlap between chunks for context
        """
        self.min_chunk_words = min_chunk_words
        self.max_chunk_words = max_chunk_words
        self.overlap_words = overlap_words
        
        # Patterns for Philippine legal document structure
        self.article_pattern = re.compile(
            r'(?:^|\n)(ARTICLE\s+[IVXLCDM]+|Article\s+\d+|ART\.\s*\d+)',
            re.MULTILINE
        )
        self.section_pattern = re.compile(
            r'(?:^|\n)(SECTION\s+\d+|Section\s+\d+|Sec\.\s*\d+)',
            re.MULTILINE
        )
        self.rule_pattern = re.compile(
            r'(?:^|\n)(RULE\s+[IVXLCDM]+|Rule\s+\d+)',
            re.MULTILINE
        )
    
    def chunk_document(
        self,
        content: str,
        source: str,
        doc_type: str,
        base_url: Optional[str] = None,
        **extra_metadata
    ) -> list[Chunk]:
        """
        Split document into chunks with metadata.
        
        Args:
            content: Full document text
            source: Document source name (e.g., "Labor Code")
            doc_type: Type of document (statute, order, handbook, etc.)
            base_url: Base URL for citation links
            **extra_metadata: Additional metadata fields
            
        Returns:
            List of document chunks with metadata
        """
        try:
            # Normalize line breaks
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Split by major divisions (Articles/Rules) first
            divisions = self._split_by_divisions(content)
            
            chunks = []
            for div_content, div_title in divisions:
                # Further split large divisions by sections
                section_chunks = self._split_by_sections(div_content, div_title)
                
                # Create final chunks with metadata
                for idx, (chunk_text, section_title) in enumerate(section_chunks):
                    chunk = self._create_chunk(
                        content=chunk_text,
                        source=source,
                        doc_type=doc_type,
                        division=div_title,
                        section=section_title,
                        chunk_index=idx,
                        base_url=base_url,
                        **extra_metadata
                    )
                    chunks.append(chunk)
            
            logger.info(
                f"Chunked document '{source}': {len(chunks)} chunks created "
                f"(avg {sum(c.word_count for c in chunks) // len(chunks)} words/chunk)"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Document chunking error: {str(e)}", exc_info=True)
            raise
    
    def _split_by_divisions(self, content: str) -> list[tuple[str, str]]:
        """Split content by Articles or Rules."""
        divisions = []
        
        # Try article pattern first
        matches = list(self.article_pattern.finditer(content))
        if not matches:
            # Try rule pattern
            matches = list(self.rule_pattern.finditer(content))
        
        if not matches:
            # No divisions found, return entire content
            return [(content, "")]
        
        for i, match in enumerate(matches):
            start_idx = match.start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            div_title = match.group(1).strip()
            div_content = content[start_idx:end_idx].strip()
            
            divisions.append((div_content, div_title))
        
        return divisions
    
    def _split_by_sections(
        self,
        content: str,
        division_title: str
    ) -> list[tuple[str, str]]:
        """Split division content by sections."""
        sections = []
        
        matches = list(self.section_pattern.finditer(content))
        
        if not matches:
            # No sections, split by word count
            return self._split_by_word_count(content, division_title)
        
        for i, match in enumerate(matches):
            start_idx = match.start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            section_title = match.group(1).strip()
            section_content = content[start_idx:end_idx].strip()
            
            # Check if section is too large
            word_count = len(section_content.split())
            if word_count > self.max_chunk_words:
                # Further split large sections
                sub_chunks = self._split_by_word_count(section_content, section_title)
                sections.extend(sub_chunks)
            else:
                sections.append((section_content, section_title))
        
        return sections
    
    def _split_by_word_count(
        self,
        content: str,
        title: str
    ) -> list[tuple[str, str]]:
        """Split content by word count with overlap."""
        words = content.split()
        chunks = []
        
        if len(words) <= self.max_chunk_words:
            return [(content, title)]
        
        i = 0
        chunk_num = 1
        while i < len(words):
            # Take max_chunk_words
            chunk_words = words[i:i + self.max_chunk_words]
            chunk_text = ' '.join(chunk_words)
            
            chunk_title = f"{title} (Part {chunk_num})" if title else f"Part {chunk_num}"
            chunks.append((chunk_text, chunk_title))
            
            # Move forward with overlap
            i += (self.max_chunk_words - self.overlap_words)
            chunk_num += 1
        
        return chunks
    
    def _create_chunk(
        self,
        content: str,
        source: str,
        doc_type: str,
        division: str,
        section: str,
        chunk_index: int,
        base_url: Optional[str] = None,
        **extra_metadata
    ) -> Chunk:
        """Create chunk with complete metadata."""
        # Generate stable ID
        chunk_id = self._generate_chunk_id(source, division, section, chunk_index)
        
        # Build metadata
        metadata = {
            "source": source,
            "doc_type": doc_type,
            "chunk_index": chunk_index,
        }
        
        if division:
            metadata["article"] = division
        if section:
            metadata["section"] = section
        if base_url:
            metadata["url"] = self._build_citation_url(base_url, division, section)
        
        # Add any extra metadata
        metadata.update(extra_metadata)
        
        # Calculate stats
        word_count = len(content.split())
        char_count = len(content)
        
        return Chunk(
            id=chunk_id,
            content=content,
            metadata=metadata,
            char_count=char_count,
            word_count=word_count
        )
    
    def _generate_chunk_id(
        self,
        source: str,
        division: str,
        section: str,
        chunk_index: int
    ) -> str:
        """Generate stable, unique chunk ID."""
        # Create consistent identifier
        parts = [source]
        if division:
            parts.append(division)
        if section:
            parts.append(section)
        parts.append(str(chunk_index))
        
        # Hash to ensure valid ID format
        id_string = "|".join(parts)
        hash_suffix = hashlib.md5(id_string.encode()).hexdigest()[:8]
        
        # Clean source name for ID
        clean_source = re.sub(r'[^a-zA-Z0-9]+', '_', source).lower()
        
        return f"{clean_source}_{hash_suffix}"
    
    def _build_citation_url(
        self,
        base_url: str,
        division: str,
        section: str
    ) -> str:
        """Build citation URL from base URL and division/section."""
        url = base_url.rstrip('/')
        
        # Add anchor if we have specific division/section
        if division:
            # Extract numeric/roman numeral from division
            anchor = re.sub(r'[^a-zA-Z0-9]+', '-', division).lower()
            url += f"#{anchor}"
        elif section:
            anchor = re.sub(r'[^a-zA-Z0-9]+', '-', section).lower()
            url += f"#{anchor}"
        
        return url
