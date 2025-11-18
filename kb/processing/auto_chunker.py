"""
Auto-chunking module for labor_law_chunks table.

Handles automatic sub-chunking of oversized articles (>1000 words) from 
labor_law_sections into labor_law_chunks for better retrieval granularity.

This implements the two-level hierarchy:
- labor_law_sections: Semantically complete articles/sections
- labor_law_chunks: Auto-split sub-chunks for long articles

Usage:
    chunker = AutoChunker(embeddings_adapter, llm_adapter)
    await chunker.auto_chunk_section(section_id, full_text, metadata)
"""
import uuid
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core import get_logger
from adapters.embeddings.base import BaseEmbeddings
from adapters.llm.base import BaseLLM
from kb.processing.summarizer import ChunkSummarizer

logger = get_logger(__name__)


@dataclass
class SubChunk:
    """Represents a sub-chunk for labor_law_chunks table."""
    chunk_index: int
    chunk_text: str
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    embedding: Optional[List[float]] = None


class AutoChunker:
    """
    Auto-chunks oversized articles into labor_law_chunks table.
    
    Strategy:
    1. Check word count of article
    2. If >1000 words, split by paragraphs/sections
    3. Generate summaries and keywords for each sub-chunk
    4. Generate embeddings
    5. Insert into labor_law_chunks table
    """
    
    WORD_COUNT_THRESHOLD = 1000
    TARGET_CHUNK_SIZE = 600  # Target words per sub-chunk
    MAX_CHUNK_SIZE = 900     # Maximum words per sub-chunk
    
    def __init__(
        self,
        embeddings_adapter: BaseEmbeddings,
        llm_adapter: Optional[BaseLLM] = None,
        use_summarization: bool = True
    ):
        """
        Initialize auto-chunker.
        
        Args:
            embeddings_adapter: Adapter for generating embeddings
            llm_adapter: Optional LLM adapter for summarization
            use_summarization: Whether to generate summaries (default: True)
        """
        self.embeddings = embeddings_adapter
        self.use_summarization = use_summarization
        self.summarizer = None
        
        if use_summarization and llm_adapter:
            # Use GPT-4 Turbo Preview (GPT-4.1) for high-quality sub-chunk summaries
            self.summarizer = ChunkSummarizer(llm_adapter)
            logger.info("AutoChunker initialized with GPT-4 Turbo Preview (GPT-4.1) summarization")
    
    def should_auto_chunk(self, text: str) -> bool:
        """
        Determine if text should be auto-chunked.
        
        Args:
            text: Full article text
            
        Returns:
            True if word count exceeds threshold
        """
        word_count = len(text.split())
        should_chunk = word_count > self.WORD_COUNT_THRESHOLD
        
        if should_chunk:
            logger.info(
                f"Article has {word_count} words (>{self.WORD_COUNT_THRESHOLD}), "
                "will auto-chunk"
            )
        
        return should_chunk
    
    def split_by_paragraphs(self, text: str) -> List[str]:
        """
        Split text into chunks by paragraphs, targeting ~600 words per chunk.
        
        Strategy:
        1. Split by double newlines (paragraphs)
        2. Group paragraphs until target size reached
        3. Ensure no chunk exceeds max size
        
        Args:
            text: Full article text
            
        Returns:
            List of chunk texts
        """
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_words = len(para.split())
            
            # If single paragraph exceeds max size, it becomes its own chunk
            if para_words > self.MAX_CHUNK_SIZE:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_word_count = 0
                
                # Add oversized paragraph as standalone chunk
                chunks.append(para)
                continue
            
            # Check if adding this paragraph would exceed max size
            if current_word_count + para_words > self.MAX_CHUNK_SIZE:
                # Save current chunk
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_word_count = 0
            
            # Add paragraph to current chunk
            current_chunk.append(para)
            current_word_count += para_words
            
            # If we've reached target size, save chunk
            if current_word_count >= self.TARGET_CHUNK_SIZE:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_word_count = 0
        
        # Add remaining paragraphs
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        logger.info(f"Split {len(text.split())} words into {len(chunks)} sub-chunks")
        return chunks
    
    async def create_sub_chunks(
        self,
        section_id: str,
        full_text: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Create sub-chunks for insertion into labor_law_chunks table.
        
        Args:
            section_id: UUID of parent section in labor_law_sections
            full_text: Complete article text
            metadata: Metadata from parent section
            
        Returns:
            List of sub-chunk records ready for database insertion
        """
        # Split into sub-chunks
        chunk_texts = self.split_by_paragraphs(full_text)
        
        # Generate summaries and keywords if enabled
        summaries = []
        if self.use_summarization and self.summarizer:
            logger.info(f"Generating summaries for {len(chunk_texts)} sub-chunks...")
            try:
                summaries = await self.summarizer.summarize_batch(
                    chunk_texts,
                    max_concurrent=3
                )
                logger.info("Sub-chunk summaries generated successfully")
            except Exception as e:
                logger.error(f"Summarization failed for sub-chunks: {e}", exc_info=True)
                # Continue without summaries
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(chunk_texts)} sub-chunks...")
        batch_response = await self.embeddings.embed_batch(
            texts=chunk_texts,
            batch_size=100
        )
        
        # Create sub-chunk records
        records = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunk_texts, batch_response.embeddings)):
            # Get summary and keywords if available
            summary = None
            keywords = []
            if summaries and idx < len(summaries):
                summary = summaries[idx].summary
                keywords = summaries[idx].keywords
            
            record = {
                "id": str(uuid.uuid4()),
                "section_id": section_id,
                "chunk_index": idx,
                "chunk_text": chunk_text,
                "summary": summary,
                "keywords": keywords,
                "embedding": embedding
            }
            records.append(record)
        
        logger.info(f"Created {len(records)} sub-chunk records for section {section_id}")
        return records
    
    async def process_section(
        self,
        section_id: str,
        full_text: str,
        metadata: Dict[str, Any],
        db_connection
    ) -> Optional[int]:
        """
        Process a section and create sub-chunks if needed.
        
        Args:
            section_id: UUID of section in labor_law_sections
            full_text: Complete article text
            metadata: Section metadata
            db_connection: Database connection for insertion
            
        Returns:
            Number of sub-chunks created, or None if no chunking needed
        """
        if not self.should_auto_chunk(full_text):
            return None
        
        # Create sub-chunks
        sub_chunks = await self.create_sub_chunks(section_id, full_text, metadata)
        
        # Insert into labor_law_chunks table
        cursor = db_connection.cursor()
        
        try:
            for chunk in sub_chunks:
                # Convert embedding list to PostgreSQL vector format
                embedding_str = "[" + ",".join(map(str, chunk["embedding"])) + "]"
                
                cursor.execute("""
                    INSERT INTO labor_law_chunks (
                        id, section_id, chunk_index, chunk_text,
                        summary, keywords, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        summary = EXCLUDED.summary,
                        keywords = EXCLUDED.keywords,
                        embedding = EXCLUDED.embedding
                """, (
                    chunk["id"],
                    chunk["section_id"],
                    chunk["chunk_index"],
                    chunk["chunk_text"],
                    chunk["summary"],
                    chunk["keywords"],
                    embedding_str
                ))
            
            db_connection.commit()
            logger.info(
                f"✓ Inserted {len(sub_chunks)} sub-chunks for section {section_id} "
                f"into labor_law_chunks table"
            )
            
            return len(sub_chunks)
            
        except Exception as e:
            db_connection.rollback()
            logger.error(f"Failed to insert sub-chunks: {e}", exc_info=True)
            raise
