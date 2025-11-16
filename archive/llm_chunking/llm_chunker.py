"""
LLM-Driven Intelligent Chunker for Day 4 KB Enhancement.

Uses GPT-4o to analyze document structure and create semantically
coherent chunks while preserving tables, formulas, and lists.
"""
import asyncio
import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

from core.logging import get_logger
from core.config import settings
from adapters.llm.openai_llm import OpenAILLM

logger = get_logger(__name__)


# Prompt template for structure analysis
STRUCTURE_ANALYSIS_PROMPT = """You are a legal document structure analyzer for Philippine labor law.

Analyze this document section and create semantically complete chunks that preserve the hierarchical structure.

CRITICAL RULES:
1. Group related content together (e.g., preamble + its sections, rules + their subsections)
2. Each chunk should be SELF-CONTAINED and MEANINGFUL on its own
3. Preserve natural legal boundaries (Articles, Sections, Rules)
4. Keep special formats intact:
   - Tables (salary rates, benefits schedules)
   - Formulas/equations (e.g., "Basic salary x 12 months")
   - Numbered/bulleted lists (must be complete)
5. Chunk size: 200-800 words (flexible for semantic completeness)
6. Include ALL content - do not omit anything

HIERARCHICAL GROUPING RULES:
- If you see a preamble/header followed by numbered sections, group them together
- Example: "RULES AND REGULATIONS" + its Section 1, 2, 3... = ONE chunk (if reasonable size)
- Example: "Presidential Decree" preamble + Section 1-3 = ONE chunk (if short sections)
- Only split into separate chunks if content exceeds 800 words or is semantically distinct

Document Type: {doc_type}
Document Source: {source}

Content to analyze:
{content}

Return ONLY valid JSON in this exact format:
{{
  "chunks": [
    {{
      "chunk_id": "unique_identifier",
      "title": "Descriptive title (e.g., 'Presidential Decree No. 851: Main Provisions')",
      "content": "COMPLETE text including preamble and all subsections",
      "has_table": false,
      "has_formula": false,
      "has_list": true,
      "semantic_type": "decree|rules|definitions|provisions",
      "hierarchy": {{
        "part": "Main Decree",
        "sections": "Sections 1-3"
      }},
      "keywords": ["13th month", "payment", "employer"]
    }}
  ]
}}"""


@dataclass
class Chunk:
    """Represents a semantic chunk of a legal document."""
    chunk_id: str
    title: str
    content: str
    has_table: bool = False
    has_formula: bool = False
    has_list: bool = False
    semantic_type: Optional[str] = None
    hierarchy: Optional[Dict[str, str]] = None
    keywords: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "content": self.content,
            "has_table": self.has_table,
            "has_formula": self.has_formula,
            "has_list": self.has_list,
            "semantic_type": self.semantic_type,
            "hierarchy": self.hierarchy or {},
            "keywords": self.keywords or []
        }


class LLMDrivenChunker:
    """
    Uses LLM to intelligently chunk legal documents.
    Preserves structure, tables, formulas, and semantic coherence.
    """
    
    def __init__(self, llm_model: Optional[str] = None, fallback_to_regex: bool = False):
        """
        Initialize with GPT-4o for superior structural understanding.
        
        Args:
            llm_model: Model to use (defaults to settings.openai_ingestion_model, typically gpt-4o)
            fallback_to_regex: Use regex chunking if LLM fails (DISABLED - causes accuracy issues)
        """
        # Use ingestion-specific model from config
        model = llm_model or settings.openai_ingestion_model
        self.llm = OpenAILLM(settings=settings, model=model) if settings.openai_api_key else None
        self.fallback_to_regex = fallback_to_regex
        self.max_content_chars = 2000  # Reduced from 8000 for better accuracy
        
        if fallback_to_regex:
            logger.warning("Regex fallback enabled - may cause title-content mismatches")
        else:
            logger.info("LLM-only chunking enabled (no regex fallback)")
    
    async def chunk_document(
        self,
        content: str,
        source: str,
        doc_type: str,
        **metadata
    ) -> List[Chunk]:
        """
        Chunk document using LLM analysis with sliding window for complete coverage.
        
        Args:
            content: Full document text
            source: Document source (e.g., "PD-442")
            doc_type: Type of document (statute, handbook, etc.)
            **metadata: Additional metadata
            
        Returns:
            List of Chunk objects
        """
        try:
            # Always use sliding window to ensure complete document coverage
            # Split by natural boundaries first, then process each part
            if len(content) > self.max_content_chars:
                logger.info(f"Document size {len(content)} chars exceeds limit {self.max_content_chars} - using multi-pass approach")
                return await self._chunk_large_document(content, source, doc_type, metadata)
            
            # Single-pass analysis for very small documents only
            chunks = await self._analyze_structure(content, source, doc_type, metadata)
            
            if not chunks and self.fallback_to_regex:
                logger.warning("LLM chunking returned no results - falling back to regex")
                return self._fallback_regex_chunking(content, source, doc_type, metadata)
            
            logger.info(f"LLM chunking successful: {len(chunks)} chunks created")
            return chunks
            
        except Exception as e:
            logger.error(f"LLM chunking failed: {e}", exc_info=True)
            
            if self.fallback_to_regex:
                logger.info("Falling back to regex chunking")
                return self._fallback_regex_chunking(content, source, doc_type, metadata)
            else:
                raise
    
    async def _analyze_structure(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict
    ) -> List[Chunk]:
        """Run LLM structure analysis on a content section."""
        if not self.llm:
            logger.warning("No LLM configured")
            return []
        
        # For sections larger than max_content_chars, we need to split further
        # But preserve semantic boundaries
        if len(content) > self.max_content_chars:
            logger.info(f"Section {source} is {len(content)} chars, splitting into smaller parts")
            # Split by section markers (Section 1, Section 2, etc.)
            parts = self._split_by_section_markers(content, source)
            
            all_chunks = []
            for part_id, part_content in parts:
                logger.info(f"  Processing part: {part_id} ({len(part_content)} chars)")
                part_chunks = await self._analyze_structure_single(part_content, part_id, doc_type, metadata)
                all_chunks.extend(part_chunks)
            
            return all_chunks
        else:
            # Content fits in one LLM call
            return await self._analyze_structure_single(content, source, doc_type, metadata)
    
    async def _analyze_structure_single(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict
    ) -> List[Chunk]:
        """Run LLM structure analysis on a single chunk of content (no further splitting)."""
        prompt = STRUCTURE_ANALYSIS_PROMPT.format(
            doc_type=doc_type,
            source=source,
            content=content  # Use full content, not truncated
        )
        
        try:
            # Call LLM with JSON mode and timeout
            logger.info(f"Calling LLM for {source} ({len(content)} chars, timeout: 30s)...")
            
            response = await asyncio.wait_for(
                self.llm.generate(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000,
                    temperature=0.0,  # Deterministic output for accuracy
                    response_format={"type": "json_object"}
                ),
                timeout=30.0  # 30 second timeout
            )
            
            logger.info(f"LLM responded successfully ({len(response.content)} chars)")
            
            # Parse JSON response
            result = json.loads(response.content)
            chunks_data = result.get("chunks", [])
            
            if not chunks_data:
                logger.warning("LLM returned empty chunks array")
                return []
            
            # Convert to Chunk objects
            chunks = []
            for i, chunk_data in enumerate(chunks_data):
                chunk = Chunk(
                    chunk_id=chunk_data.get("chunk_id", f"{source}_chunk_{i}"),
                    title=chunk_data.get("title", f"Section {i+1}"),
                    content=chunk_data.get("content", ""),
                    has_table=chunk_data.get("has_table", False),
                    has_formula=chunk_data.get("has_formula", False),
                    has_list=chunk_data.get("has_list", False),
                    semantic_type=chunk_data.get("semantic_type"),
                    hierarchy=chunk_data.get("hierarchy"),
                    keywords=chunk_data.get("keywords")
                )
                chunks.append(chunk)
            
            logger.info(f"Parsed {len(chunks)} chunks from {source}")
            return chunks
            
        except asyncio.TimeoutError:
            logger.error(f"LLM analysis timed out for {source}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response content: {response.content[:500]}...")
            return []
        except Exception as e:
            logger.error(f"LLM analysis failed for {source}: {e}", exc_info=True)
            return []
    
    def _split_by_section_markers(self, content: str, source: str) -> List[tuple]:
        """
        Split content by Section markers while preserving preambles.
        
        Returns:
            List of (section_id, content) tuples
        """
        parts = []
        lines = content.split('\n')
        current_part = []
        current_section_name = "preamble"
        part_index = 0
        
        section_pattern = re.compile(r'^Section\s+(\d+)', re.IGNORECASE)
        
        for line in lines:
            match = section_pattern.match(line.strip())
            
            if match and current_part:
                # Found a new section, save previous part
                part_content = '\n'.join(current_part).strip()
                if part_content:
                    parts.append((f"{source}_{current_section_name}", part_content))
                    part_index += 1
                
                # Start new part
                current_section_name = f"section_{match.group(1)}"
                current_part = [line]
            else:
                current_part.append(line)
        
        # Add last part
        if current_part:
            part_content = '\n'.join(current_part).strip()
            if part_content:
                parts.append((f"{source}_{current_section_name}", part_content))
        
        # If only one part (no sections found), return whole content
        if len(parts) <= 1:
            return [(source, content)]
        
        return parts
    
    async def _chunk_large_document(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict
    ) -> List[Chunk]:
        """
        Handle documents larger than max_content_chars using intelligent splitting.
        
        Strategy:
        1. Split by major document boundaries (e.g., "RULES AND REGULATIONS", "SUPPLEMENTARY")
        2. Process each major section independently
        3. Combine results while preserving document structure
        """
        logger.info(f"Processing document ({len(content)} chars) with multi-pass approach")
        
        # First, try to split by major document boundaries
        sections = self._split_by_document_structure(content, source)
        
        if not sections:
            # Fallback to splitting by major section markers
            sections = self._split_by_major_sections(content)
            sections = [(f"{source}_section_{i}", sec) for i, sec in enumerate(sections)]
        
        logger.info(f"Split into {len(sections)} major sections for processing")
        
        all_chunks = []
        for section_id, section_content in sections:
            logger.info(f"Processing section: {section_id} ({len(section_content)} chars)")
            
            # Process this section
            section_chunks = await self._analyze_structure(
                section_content,
                section_id,
                doc_type,
                metadata
            )
            
            if section_chunks:
                logger.info(f"  → Created {len(section_chunks)} chunks from {section_id}")
                all_chunks.extend(section_chunks)
            else:
                logger.warning(f"  → No chunks created from {section_id}")
        
        logger.info(f"Multi-pass chunking complete: {len(all_chunks)} total chunks from {len(sections)} sections")
        return all_chunks
    
    def _split_by_document_structure(self, content: str, source: str) -> List[tuple]:
        """
        Split document by major structural boundaries specific to Philippine legal documents.
        
        Returns:
            List of (section_id, content) tuples
        """
        sections = []
        
        # Patterns for major document divisions
        # These indicate distinct parts of a legal document
        major_boundaries = [
            (r'RULES AND REGULATIONS IMPLEMENTING', 'implementing_rules'),
            (r'SUPPLEMENTARY RULES AND REGULATIONS', 'supplementary_rules'),
            (r'AMENDATORY PROVISIONS', 'amendments'),
            (r'TRANSITORY PROVISIONS', 'transitory'),
        ]
        
        # Find all boundary positions
        boundaries_found = []
        for pattern, section_type in major_boundaries:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                boundaries_found.append((match.start(), section_type, match.group(0)))
        
        # Sort by position
        boundaries_found.sort(key=lambda x: x[0])
        
        if not boundaries_found:
            # No major boundaries found, return whole document
            return [(source, content)]
        
        # Create sections based on boundaries
        # First section: from start to first boundary (the main decree/act)
        first_boundary_pos = boundaries_found[0][0]
        if first_boundary_pos > 0:
            sections.append((
                f"{source}_main_decree",
                content[:first_boundary_pos].strip()
            ))
        
        # Middle sections: between boundaries
        for i, (pos, section_type, heading) in enumerate(boundaries_found):
            # Find end position (next boundary or end of document)
            if i + 1 < len(boundaries_found):
                end_pos = boundaries_found[i + 1][0]
            else:
                end_pos = len(content)
            
            section_content = content[pos:end_pos].strip()
            sections.append((
                f"{source}_{section_type}",
                section_content
            ))
        
        logger.info(f"Found {len(sections)} major document sections:")
        for section_id, section_content in sections:
            logger.info(f"  - {section_id}: {len(section_content)} chars")
        
        return sections
    
    def _split_by_major_sections(self, content: str) -> List[str]:
        """Split document by major structural boundaries."""
        # Patterns for major boundaries
        patterns = [
            r'^BOOK\s+[IVXLCDM]+',  # BOOK I, BOOK II, etc.
            r'^TITLE\s+[IVXLCDM]+',  # TITLE I, TITLE II, etc.
            r'^RULE\s+[IVXLCDM]+',   # RULE I, RULE II, etc.
        ]
        
        sections = []
        current_section = []
        
        for line in content.split('\n'):
            is_boundary = any(re.match(pattern, line.strip(), re.IGNORECASE) for pattern in patterns)
            
            if is_boundary and current_section:
                # Save previous section
                sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        # Add last section
        if current_section:
            sections.append('\n'.join(current_section))
        
        # If no major sections found, split by size
        if len(sections) <= 1:
            return self._split_by_size(content, self.max_content_chars * 10)
        
        return sections
    
    def _split_by_size(self, content: str, max_size: int) -> List[str]:
        """Split content into chunks of approximately max_size."""
        sections = []
        current_pos = 0
        
        while current_pos < len(content):
            end_pos = current_pos + max_size
            
            # Try to break at paragraph boundary
            if end_pos < len(content):
                # Look for double newline (paragraph break)
                break_pos = content.rfind('\n\n', current_pos, end_pos)
                if break_pos > current_pos:
                    end_pos = break_pos
            
            sections.append(content[current_pos:end_pos])
            current_pos = end_pos
        
        return sections
    
    def _fallback_regex_chunking(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict
    ) -> List[Chunk]:
        """
        Fallback to regex-based chunking if LLM fails.
        
        Uses simple pattern matching for Articles, Sections, etc.
        """
        logger.info("Using regex fallback chunking")
        
        chunks = []
        
        # Pattern for articles (Article 1, Article 123, etc.)
        article_pattern = r'(Article\s+\d+[a-z]*\.?\s*[^\n]*)\n((?:(?!Article\s+\d+).*\n)*)'
        
        matches = re.finditer(article_pattern, content, re.IGNORECASE | re.MULTILINE)
        
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            chunk_content = match.group(0).strip()
            
            # Detect format features
            has_table = self._detect_table(chunk_content)
            has_formula = self._detect_formula(chunk_content)
            has_list = self._detect_list(chunk_content)
            
            chunk = Chunk(
                chunk_id=f"{source}_article_{i}",
                title=title,
                content=chunk_content,
                has_table=has_table,
                has_formula=has_formula,
                has_list=has_list,
                semantic_type="article",
                hierarchy={"source": source},
                keywords=self._extract_keywords_simple(title)
            )
            chunks.append(chunk)
        
        # If no articles found, split by size
        if not chunks:
            logger.warning("No articles found - splitting by size")
            chunks = self._split_by_paragraphs(content, source)
        
        logger.info(f"Regex chunking created {len(chunks)} chunks")
        return chunks
    
    def _detect_table(self, text: str) -> bool:
        """Detect if text contains a table structure."""
        # Look for aligned columns (multiple spaces or tabs)
        lines = text.split('\n')
        aligned_lines = sum(1 for line in lines if re.search(r'\s{3,}|\t', line))
        return aligned_lines >= 3  # At least 3 lines with alignment
    
    def _detect_formula(self, text: str) -> bool:
        """Detect if text contains mathematical formulas."""
        formula_indicators = [
            r'\d+\s*[+\-×÷/]\s*\d+',  # Basic math operations
            r'=\s*\d+',  # Equals sign with number
            r'\d+%',  # Percentages
            r'\(\d+\s*[+\-×÷/]\s*\d+\)',  # Parenthesized expressions
        ]
        return any(re.search(pattern, text) for pattern in formula_indicators)
    
    def _detect_list(self, text: str) -> bool:
        """Detect if text contains numbered or bulleted lists."""
        list_patterns = [
            r'^\s*\d+\.\s+',  # Numbered list (1., 2., etc.)
            r'^\s*\([a-z0-9]+\)\s+',  # Lettered list ((a), (b), etc.)
            r'^\s*[a-z]\.\s+',  # Letter list (a., b., etc.)
            r'^\s*[-•*]\s+',  # Bullet list
        ]
        lines = text.split('\n')
        list_lines = sum(1 for line in lines if any(re.match(p, line) for p in list_patterns))
        return list_lines >= 2  # At least 2 list items
    
    def _extract_keywords_simple(self, title: str) -> List[str]:
        """Simple keyword extraction from title."""
        # Remove common words and extract significant terms
        stopwords = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for'}
        words = re.findall(r'\b\w+\b', title.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 3]
        return keywords[:5]  # Limit to 5 keywords
    
    def _split_by_paragraphs(self, content: str, source: str, max_words: int = 300) -> List[Chunk]:
        """Split content into paragraph-based chunks."""
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_words = 0
        
        for i, para in enumerate(paragraphs):
            para_words = len(para.split())
            
            if current_words + para_words > max_words and current_chunk:
                # Save current chunk
                chunk_content = '\n\n'.join(current_chunk)
                chunk = Chunk(
                    chunk_id=f"{source}_para_{len(chunks)}",
                    title=f"Section {len(chunks) + 1}",
                    content=chunk_content,
                    has_table=self._detect_table(chunk_content),
                    has_formula=self._detect_formula(chunk_content),
                    has_list=self._detect_list(chunk_content),
                    semantic_type="paragraph_group",
                    hierarchy={"source": source}
                )
                chunks.append(chunk)
                current_chunk = [para]
                current_words = para_words
            else:
                current_chunk.append(para)
                current_words += para_words
        
        # Add last chunk
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunk = Chunk(
                chunk_id=f"{source}_para_{len(chunks)}",
                title=f"Section {len(chunks) + 1}",
                content=chunk_content,
                has_table=self._detect_table(chunk_content),
                has_formula=self._detect_formula(chunk_content),
                has_list=self._detect_list(chunk_content),
                semantic_type="paragraph_group",
                hierarchy={"source": source}
            )
            chunks.append(chunk)
        
        return chunks
