"""
Knowledge base ingestion CLI.

Ingests labor law documents into Supabase vector store with embeddings 
and proper metadata for citation.

Supports two ingestion modes:
1. Manual chunking (recommended): Use pre-chunked files from kb/chunks/
2. Regex chunking (legacy): Automatic chunking using regex patterns

Usage:
    # Manual chunking (RECOMMENDED - 100% coverage)
    python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-851
    python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-851 --dry-run
    python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-851 --force
    python -m kb.ingest.sync_to_vectorstore --manual  # Ingest all manual chunks
    python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-851/01-decree-main.md
    
    # Regex chunking (LEGACY - for backward compatibility only)
    python -m kb.ingest.sync_to_vectorstore --help
    python -m kb.ingest.sync_to_vectorstore --file kb/docs/PD-No-442.txt
    python -m kb.ingest.sync_to_vectorstore --all
    python -m kb.ingest.sync_to_vectorstore --all --dry-run
    python -m kb.ingest.sync_to_vectorstore --file kb/docs/PD-No-442.txt --force
    python -m kb.ingest.sync_to_vectorstore --new-only
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional
import argparse

from core import get_logger, setup_logging
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from retrieval.chunking import LegalDocumentChunker
from kb.ingest.loaders import TextFileLoader
from kb.ingest.loaders.manual_chunk_loader import ManualChunkLoader, ManualChunk
from kb.ingest.incremental_tracker import IngestionTracker
from kb.ingest.source_manager import SourceManager
from kb.processing.summarizer import ChunkSummarizer
from kb.processing.auto_chunker import AutoChunker
from adapters.vectorstore.base import Document

logger = get_logger(__name__)


# Document metadata registry with canonical URLs
DOCUMENT_REGISTRY = {
    "PD-No-442.txt": {
        "source": "Presidential Decree No. 442 (Labor Code)",
        "doc_type": "statute",
        "year": "1974",
        "url": "https://lawphil.net/statutes/presdecs/pd1974/pd_442_1974.html",
        "short_name": "Labor Code"
    },
    "RA-No-11058.txt": {
        "source": "Republic Act No. 11058",
        "doc_type": "statute",
        "year": "2018",
        "url": "https://lawphil.net/statutes/repacts/ra2018/ra_11058_2018.html",
        "short_name": "OSH Standards Law"
    },
    "RA-No-11199.txt": {
        "source": "Republic Act No. 11199",
        "doc_type": "statute",
        "year": "2019",
        "url": "https://lawphil.net/statutes/repacts/ra2019/ra_11199_2019.html",
        "short_name": "Social Security Act"
    },
    "RA-No-10361.txt": {
        "source": "Republic Act No. 10361",
        "doc_type": "statute",
        "year": "2013",
        "url": "https://lawphil.net/statutes/repacts/ra2013/ra_10361_2013.html",
        "short_name": "Domestic Workers Act"
    },
    "PD-No-851.txt": {
        "source": "Presidential Decree No. 851",
        "doc_type": "statute",
        "year": "1975",
        "url": "https://lawphil.net/statutes/presdecs/pd1975/pd_851_1975.html",
        "short_name": "13th Month Pay Law"
    },
    "DOLE-Dep-Order-147-15.txt": {
        "source": "DOLE Department Order No. 147-15",
        "doc_type": "department_order",
        "year": "2015",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/71535",
        "short_name": "DO 147-15"
    },
    "SEnA.txt": {
        "source": "Single Entry Approach Rules",
        "doc_type": "procedural_rules",
        "year": "2011",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/5/92443",
        "short_name": "SEnA Rules"
    },
    "NLRC-Rules.txt": {
        "source": "NLRC Rules of Procedure",
        "doc_type": "procedural_rules",
        "year": "2011",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/57844",
        "short_name": "NLRC Rules"
    },
    "DOLE-Handbook.txt": {
        "source": "DOLE Handbook on Workers' Statutory Monetary Benefits",
        "doc_type": "handbook",
        "year": "2023",
        "url": "https://library.laborlaw.ph/resources/",
        "short_name": "DOLE Handbook"
    },
    "DOLE-Covid-Protocols.txt": {
        "source": "DOLE COVID-19 Workplace Protocols",
        "doc_type": "guidelines",
        "year": "2020",
        "url": "https://www.dole.gov.ph/covid-19-labor-advisories/",
        "short_name": "COVID-19 Protocols"
    }
}


class KnowledgeBaseIngester:
    """Handles ingestion of legal documents into vector store."""
    
    def __init__(
        self,
        embeddings_adapter,
        vectorstore_adapter,
        llm_adapter=None,
        chunker: Optional[LegalDocumentChunker] = None,
        summarizer: Optional[ChunkSummarizer] = None,
        tracker: Optional[IngestionTracker] = None,
        source_manager: Optional[SourceManager] = None,
        loader: Optional[TextFileLoader] = None,
        use_summarization: bool = True,
        use_auto_chunking: bool = True
    ):
        """
        Initialize ingester.
        
        Args:
            embeddings_adapter: Embeddings adapter instance
            vectorstore_adapter: Vector store adapter instance
            llm_adapter: LLM adapter for summarization
            chunker: Regex document chunker for automatic chunking (legacy)
            summarizer: Chunk summarizer for generating summaries and keywords
            tracker: Incremental ingestion tracker
            source_manager: Source manager for linking documents to sources
            loader: Text file loader (optional)
            use_summarization: Generate summaries and keywords
            use_auto_chunking: Auto-chunk oversized articles into labor_law_chunks
        """
        self.embeddings = embeddings_adapter
        self.vectorstore = vectorstore_adapter
        self.llm = llm_adapter
        
        # Chunking strategy (regex-based for legacy automatic ingestion)
        self.chunker = chunker or LegalDocumentChunker(
            min_chunk_words=100,
            max_chunk_words=300,
            overlap_words=20
        )
        
        # Summarization
        self.use_summarization = use_summarization
        self.summarizer = summarizer or ChunkSummarizer(
            llm=llm_adapter,
            use_llm=use_summarization
        )
        
        # Auto-chunking for oversized articles
        self.use_auto_chunking = use_auto_chunking
        self.auto_chunker = None
        if use_auto_chunking:
            self.auto_chunker = AutoChunker(
                embeddings_adapter=embeddings_adapter,
                llm_adapter=llm_adapter,
                use_summarization=use_summarization
            )
        
        # Incremental tracking
        self.tracker = tracker or IngestionTracker()
        
        # Source management
        self.source_manager = source_manager or SourceManager()
        
        # File loading
        self.loader = loader or TextFileLoader()
        
        # Manual chunk loading
        self.manual_loader = ManualChunkLoader()
    
    async def ingest_file(
        self,
        file_path: Path,
        dry_run: bool = False,
        force: bool = False
    ) -> dict:
        """
        Ingest a single file into vector store.
        
        Args:
            file_path: Path to text file
            dry_run: If True, only simulate ingestion
            force: If True, force re-ingestion even if unchanged
            
        Returns:
            Dictionary with ingestion statistics
        """
        try:
            # Check if file should be ingested (incremental detection)
            should_ingest, reason = self.tracker.should_ingest(file_path, force=force)
            
            if not should_ingest:
                logger.info(f"Skipping {file_path.name}: {reason}")
                return {
                    "file": file_path.name,
                    "status": "skipped",
                    "reason": reason
                }
            
            logger.info(f"Processing file: {file_path.name} ({reason})")
            
            # Calculate file hash for tracking
            file_hash = self.tracker.calculate_file_hash(file_path)
            
            # Get metadata from registry
            metadata = DOCUMENT_REGISTRY.get(file_path.name)
            if not metadata:
                logger.warning(
                    f"No metadata found for {file_path.name}. "
                    "Using default metadata."
                )
                metadata = {
                    "source": file_path.stem,
                    "doc_type": "unknown",
                    "url": "",
                    "short_name": file_path.stem
                }
            
            # Get or create source record
            logger.info(f"Retrieving source record for {metadata['source']}")
            source_name = metadata.get("source", "")
            short_name = metadata.get("short_name", file_path.name)
            
            # Derive reference from source or short_name
            if "PD" in source_name or "Presidential Decree" in source_name:
                import re
                match = re.search(r'(?:PD|Presidential Decree)\s*(?:No\.)?\s*(\d+)', source_name)
                reference = f"PD {match.group(1)}" if match else short_name
            elif "RA" in source_name or "Republic Act" in source_name:
                import re
                match = re.search(r'(?:RA|Republic Act)\s*(?:No\.)?\s*(\d+)', source_name)
                reference = f"RA {match.group(1)}" if match else short_name
            else:
                reference = short_name or file_path.name.replace('.txt', '')
            
            # Get or create source
            try:
                source_id = self.source_manager.create_source(
                    source_type=metadata.get("doc_type", "statute"),
                    title=source_name,
                    reference=reference,
                    url=metadata.get("url")
                )
                logger.info(f"Using source ID: {source_id} for {reference}")
            except Exception as e:
                logger.error(f"Failed to get/create source: {e}")
                raise
            
            # Load document
            content = self.loader.load(file_path)
            
            # Chunk document using regex chunker (legacy automatic method)
            logger.info(f"Using regex chunking for {file_path.name}")
            chunks = self.chunker.chunk_document(
                content=content,
                source=metadata["source"],
                doc_type=metadata["doc_type"],
                base_url=metadata.get("url"),
                year=metadata.get("year"),
                short_name=metadata.get("short_name"),
                source_id=str(source_id)
            )
            ingestion_method = "regex_chunking"
            logger.info(f"Regex chunking created {len(chunks)} chunks")
            
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would create {len(chunks)} chunks "
                    f"for {file_path.name}"
                )
                return {
                    "file": file_path.name,
                    "chunks": len(chunks),
                    "status": "dry_run"
                }
            
            # Generate summaries and keywords
            if self.use_summarization:
                logger.info(f"Generating summaries and keywords for {len(chunks)} chunks...")
                try:
                    summaries = await self.summarizer.summarize_batch(
                        [chunk.content for chunk in chunks],
                        max_concurrent=3
                    )
                    
                    # Add summaries and keywords to metadata
                    for chunk, summary in zip(chunks, summaries):
                        chunk.metadata["summary"] = summary.summary
                        # Merge LLM-extracted keywords with summarizer keywords
                        existing_keywords = chunk.metadata.get("keywords", [])
                        chunk.metadata["keywords"] = list(set(existing_keywords + summary.keywords))
                    
                    logger.info(f"Summaries generated successfully")
                except Exception as e:
                    logger.error(f"Summarization failed: {e}", exc_info=True)
                    # Continue without summaries
            
            # Generate embeddings in batches
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [chunk.content for chunk in chunks]
            
            batch_response = await self.embeddings.embed_batch(
                texts=texts,
                batch_size=100
            )
            
            # Delete old chunks if re-ingesting
            # This happens when:
            # 1. Force flag is set (--force)
            # 2. File content changed (hash mismatch)
            if force or reason == "File content changed":
                deleted_count = self.tracker.delete_old_chunks(file_path.name)
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} old chunks from previous ingestion")
            
            # Create documents for vector store
            documents = []
            for chunk, embedding in zip(chunks, batch_response.embeddings):
                doc = Document(
                    id=chunk.id,
                    content=chunk.content,
                    embedding=embedding,
                    metadata=chunk.metadata
                )
                documents.append(doc)
            
            # Upsert to vector store
            logger.info(f"Upserting {len(documents)} documents to vector store...")
            await self.vectorstore.upsert(documents)
            
            # Record successful ingestion
            self.tracker.record_ingestion(
                file_path=file_path,
                file_hash=file_hash,
                chunk_count=len(chunks),
                token_count=batch_response.total_tokens_used,
                ingestion_method=ingestion_method,
                status="success"
            )
            
            logger.info(
                f"✓ Successfully ingested {file_path.name}: "
                f"{len(chunks)} chunks, {batch_response.total_tokens_used} tokens"
            )
            
            return {
                "file": file_path.name,
                "chunks": len(chunks),
                "tokens": batch_response.total_tokens_used,
                "ingestion_method": ingestion_method,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest {file_path.name}: {str(e)}", exc_info=True)
            
            # Record failed ingestion
            try:
                file_hash = self.tracker.calculate_file_hash(file_path)
                self.tracker.record_ingestion(
                    file_path=file_path,
                    file_hash=file_hash,
                    chunk_count=0,
                    token_count=0,
                    ingestion_method="failed",
                    status="failed",
                    error_message=str(e)
                )
            except Exception as tracking_error:
                logger.error(f"Failed to record ingestion error: {tracking_error}")
            
            return {
                "file": file_path.name,
                "status": "failed",
                "error": str(e)
            }
    
    async def ingest_manual_chunks(
        self,
        document_name: Optional[str] = None,
        single_file: Optional[Path] = None,
        dry_run: bool = False,
        force: bool = False
    ) -> dict:
        """
        Ingest manually chunked documents from kb/chunks/.
        
        Args:
            document_name: Specific document folder (e.g., "PD-No-851")
            single_file: Path to single .md file to ingest
            dry_run: Simulate without writing
            force: Force re-ingestion
        
        Returns:
            Ingestion statistics
        """
        try:
            # Load chunks
            if single_file:
                logger.info(f"Loading single manual chunk: {single_file}")
                chunk = self.manual_loader.load_single_chunk_file(str(single_file))
                if not chunk:
                    logger.error(f"Failed to load chunk from {single_file}")
                    return {
                        "status": "failed",
                        "error": "Failed to parse chunk file"
                    }
                chunks = [chunk]
                document_name = single_file.parent.name
            elif document_name:
                logger.info(f"Loading manual chunks for document: {document_name}")
                chunks = self.manual_loader.load_document_chunks(document_name)
                if not chunks:
                    logger.error(f"No valid chunks found for {document_name}")
                    return {
                        "status": "failed",
                        "error": "No valid chunks found"
                    }
            else:
                logger.info("Loading all manual chunks from kb/chunks/")
                all_chunks_dict = self.manual_loader.load_all_chunks()
                if not all_chunks_dict:
                    logger.error("No manual chunks found in kb/chunks/")
                    return {
                        "status": "failed",
                        "error": "No chunks found"
                    }
                
                # Flatten all chunks
                chunks = []
                for doc_name, doc_chunks in all_chunks_dict.items():
                    chunks.extend(doc_chunks)
                logger.info(f"Loaded {len(chunks)} total chunks from {len(all_chunks_dict)} documents")
            
            # Check if manual chunks should be ingested (incremental detection)
            # Track EACH FILE individually, not the entire folder
            # This applies to both specific folders and --all mode
            if not force:
                # Filter chunks: keep only those that changed or are new
                filtered_chunks = []
                skipped_count = 0
                skipped_by_file = {}
                
                for chunk in chunks:
                    # Each chunk has file_stem and document_name to identify its source file
                    # Reconstruct the file path based on available information
                    
                    # For single_file mode, we already have the path
                    if single_file:
                        file_to_check = single_file
                    # For document_name mode (specific folder) or --all mode with document_name set
                    elif chunk.document_name:
                        folder_path = Path(f"kb/chunks/{chunk.document_name}")
                        file_to_check = folder_path / f"{chunk.file_stem}.md"
                    # Fallback: try to derive from current document_name parameter
                    elif document_name:
                        folder_path = Path(f"kb/chunks/{document_name}")
                        file_to_check = folder_path / f"{chunk.file_stem}.md"
                    else:
                        # Should not happen with updated ManualChunk, but handle gracefully
                        logger.warning(
                            f"Cannot determine file path for chunk {chunk.chunk_id}. "
                            f"Including in ingestion (file: {chunk.file_stem}.md)."
                        )
                        filtered_chunks.append(chunk)
                        continue
                    
                    should_ingest_file, reason = self.tracker.should_ingest(
                        file_to_check,
                        force=force
                    )
                    
                    if should_ingest_file:
                        filtered_chunks.append(chunk)
                    else:
                        skipped_count += 1
                        file_name = file_to_check.name
                        skipped_by_file[file_name] = skipped_by_file.get(file_name, 0) + 1
                        logger.debug(f"Skipping chunk from {file_name}: {reason}")
                
                # If ALL chunks are skipped, return early
                if not filtered_chunks:
                    logger.info(
                        f"Skipping {document_name or 'all documents'}: "
                        f"All {len(chunks)} chunks unchanged"
                    )
                    return {
                        "document": document_name or "all",
                        "status": "skipped",
                        "reason": "All chunks unchanged",
                        "skipped": len(chunks),
                        "total": len(chunks)
                    }
                
                if skipped_count > 0:
                    logger.info(
                        f"Processing {document_name or 'selected documents'}: "
                        f"{len(filtered_chunks)} chunks to ingest, {skipped_count} chunks skipped"
                    )
                    for file_name, count in sorted(skipped_by_file.items()):
                        logger.info(f"  Skipped {file_name}: {count} chunks (unchanged)")
                else:
                    logger.info(
                        f"Processing {document_name or 'all documents'}: "
                        f"All {len(chunks)} chunks are new or modified"
                    )
                
                # Replace chunks with only the ones that need ingesting
                chunks = filtered_chunks
            else:
                # Force flag is set - ingest everything
                logger.info(f"Force flag enabled - ingesting all {len(chunks)} chunks")
            
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would ingest {len(chunks)} manual chunks "
                    f"for {document_name or 'all documents'}"
                )
                return {
                    "status": "dry_run",
                    "chunks": len(chunks),
                    "document": document_name
                }
            
            # Get or create source record
            # Use metadata from first chunk (all chunks from same doc share metadata)
            first_chunk = chunks[0]
            source_name = first_chunk.source or document_name or "Unknown"
            reference = first_chunk.reference or document_name or "Unknown"
            
            logger.info(f"Creating/retrieving source record for {source_name}")
            
            try:
                source_id = self.source_manager.create_source(
                    source_type=first_chunk.doc_type or "statute",
                    title=source_name,
                    reference=reference,
                    url=first_chunk.url
                )
                logger.info(f"Using source ID: {source_id} for {reference}")
            except Exception as e:
                logger.error(f"Failed to get/create source: {e}")
                raise
            
            # Convert ManualChunk objects to standard format
            documents = []
            texts_for_embedding = []
            
            for manual_chunk in chunks:
                # Prepare metadata
                chunk_metadata = {
                    "source": manual_chunk.source or source_name,
                    "source_id": str(source_id),
                    "doc_type": manual_chunk.doc_type or "statute",
                    "url": manual_chunk.url or "",
                    "short_name": reference,
                    "title": manual_chunk.title,
                    "chunk_id": manual_chunk.chunk_id,  # Store chunk_id in metadata
                    "file_stem": manual_chunk.file_stem,  # Store file stem for tracking
                    "article_number": manual_chunk.article_number,  # Store legal article number in metadata
                    "has_table": manual_chunk.has_table,
                    "has_formula": manual_chunk.has_formula,
                    "has_list": manual_chunk.has_list,
                    "semantic_type": manual_chunk.semantic_type,
                    "hierarchy": manual_chunk.hierarchy or {},
                    "keywords": manual_chunk.keywords or [],
                    "summary": None  # Will be filled by summarizer if enabled
                }
                
                texts_for_embedding.append(manual_chunk.content)
                
                # Store for later (after embedding)
                documents.append({
                    "id": manual_chunk.chunk_id,
                    "content": manual_chunk.content,
                    "metadata": chunk_metadata
                })
            
            # Generate summaries and keywords if enabled
            if self.use_summarization:
                logger.info(f"Generating summaries and keywords for {len(chunks)} chunks...")
                try:
                    summaries = await self.summarizer.summarize_batch(
                        [chunk.content for chunk in chunks],
                        max_concurrent=3
                    )
                    
                    # Add summaries and merge keywords
                    for doc, summary in zip(documents, summaries):
                        doc["metadata"]["summary"] = summary.summary
                        existing_keywords = doc["metadata"].get("keywords", [])
                        doc["metadata"]["keywords"] = list(set(existing_keywords + summary.keywords))
                    
                    logger.info("Summaries generated successfully")
                except Exception as e:
                    logger.error(f"Summarization failed: {e}", exc_info=True)
                    # Continue without summaries
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            batch_response = await self.embeddings.embed_batch(
                texts=texts_for_embedding,
                batch_size=100
            )
            
            # Delete old chunks if re-ingesting
            # Delete ONLY the chunks from files that are being re-ingested
            # Group chunks by file to delete only what's being replaced
            if force or any(
                chunk.file_stem in {c.file_stem for c in chunks}
                for chunk in chunks
            ):
                # Collect article_numbers to delete (only from files being re-ingested)
                article_numbers_to_delete = []
                files_to_delete = set()
                
                for chunk in chunks:
                    article_numbers_to_delete.append(chunk.article_number)
                    files_to_delete.add(chunk.file_stem)
                
                if article_numbers_to_delete:
                    logger.info(
                        f"Re-ingesting {len(files_to_delete)} file(s) - "
                        f"deleting {len(article_numbers_to_delete)} old chunks"
                    )
                    try:
                        deleted_count = await self.vectorstore.delete_by_article_numbers(
                            article_numbers_to_delete
                        )
                        if deleted_count > 0:
                            logger.info(
                                f"Deleted {deleted_count} old chunks from "
                                f"{', '.join(sorted(files_to_delete))}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to delete old chunks: {e}", exc_info=True)
                        # Continue anyway - upsert will handle duplicates
            
            # Create final documents with embeddings
            final_documents = []
            for doc_dict, embedding in zip(documents, batch_response.embeddings):
                doc = Document(
                    id=doc_dict["id"],
                    content=doc_dict["content"],
                    embedding=embedding,
                    metadata=doc_dict["metadata"]
                )
                final_documents.append(doc)
            
            # Upsert to vector store
            logger.info(f"Upserting {len(final_documents)} documents to vector store...")
            await self.vectorstore.upsert(final_documents)
            
            # Auto-chunk oversized articles into labor_law_chunks table
            if self.use_auto_chunking and self.auto_chunker:
                logger.info("Checking for oversized articles that need auto-chunking...")
                total_sub_chunks = 0
                
                # Get database connection from vectorstore adapter
                db_conn = self.vectorstore._get_connection()
                
                for doc_dict in documents:
                    try:
                        # Check if this article needs auto-chunking
                        if self.auto_chunker.should_auto_chunk(doc_dict["content"]):
                            # Extract section_id from metadata (it was set during upsert)
                            # We need to query the section we just inserted to get its UUID
                            cursor = db_conn.cursor()
                            cursor.execute("""
                                SELECT id FROM labor_law_sections
                                WHERE article_number = %s
                                ORDER BY created_at DESC
                                LIMIT 1
                            """, (doc_dict["metadata"]["article_number"],))
                            
                            result = cursor.fetchone()
                            if result:
                                section_id = str(result[0])
                                
                                # Create and insert sub-chunks
                                num_sub_chunks = await self.auto_chunker.process_section(
                                    section_id=section_id,
                                    full_text=doc_dict["content"],
                                    metadata=doc_dict["metadata"],
                                    db_connection=db_conn
                                )
                                
                                if num_sub_chunks:
                                    total_sub_chunks += num_sub_chunks
                                    logger.info(
                                        f"  Article {doc_dict['metadata']['article_number']}: "
                                        f"created {num_sub_chunks} sub-chunks"
                                    )
                    except Exception as e:
                        logger.error(
                            f"Failed to auto-chunk article "
                            f"{doc_dict['metadata'].get('article_number', 'unknown')}: {e}",
                            exc_info=True
                        )
                        # Continue with other articles
                
                if total_sub_chunks > 0:
                    logger.info(
                        f"✓ Auto-chunked {total_sub_chunks} sub-chunks "
                        f"into labor_law_chunks table"
                    )
            
            # Record successful ingestion in history
            # Track EACH FILE individually (not the folder as a whole)
            if document_name:
                try:
                    folder_path = Path(f"kb/chunks/{document_name}")
                    
                    # Record each ingested chunk's file
                    # Group by file_stem to get unique files
                    unique_files = set()
                    for chunk in chunks:
                        file_path = folder_path / f"{chunk.file_stem}.md"
                        unique_files.add(file_path)
                    
                    for file_path in unique_files:
                        # Calculate hash for this specific file
                        try:
                            file_hash = self.tracker.calculate_file_hash(file_path)
                        except:
                            file_hash = ""
                        
                        # Count chunks from this file
                        file_chunk_count = sum(
                            1 for chunk in chunks 
                            if chunk.file_stem == file_path.stem
                        )
                        
                        self.tracker.record_ingestion(
                            file_path=file_path,
                            file_hash=file_hash,
                            chunk_count=file_chunk_count,
                            token_count=0,  # Don't double-count tokens
                            ingestion_method="manual_chunking",
                            status="success"
                        )
                    
                    logger.info(
                        f"✓ Recorded ingestion history for {len(unique_files)} files "
                        f"in {document_name}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to record ingestion history: {e}")
                    # Don't fail the whole ingestion if history recording fails
            
            logger.info(
                f"✓ Successfully ingested {len(chunks)} manual chunks: "
                f"{batch_response.total_tokens_used} tokens"
            )
            
            return {
                "status": "success",
                "document": document_name or "all",
                "chunks": len(chunks),
                "tokens": batch_response.total_tokens_used,
                "ingestion_method": "manual_chunking"
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest manual chunks: {str(e)}", exc_info=True)
            
            # Record failed ingestion in history
            if document_name:
                try:
                    folder_path = Path(f"kb/chunks/{document_name}")
                    self.tracker.record_ingestion(
                        file_path=folder_path,
                        file_hash="",
                        chunk_count=0,
                        token_count=0,
                        ingestion_method="manual_chunking",
                        status="failed",
                        error_message=str(e)
                    )
                except:
                    pass  # Ignore errors in error recording
            
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def ingest_all(
        self,
        docs_dir: Path,
        dry_run: bool = False,
        force: bool = False,
        new_only: bool = False
    ) -> dict:
        """
        Ingest all registered documents from directory.
        
        Args:
            docs_dir: Directory containing documents
            dry_run: If True, only simulate ingestion
            force: If True, force re-ingestion of all files
            new_only: If True, only ingest new/modified files
            
        Returns:
            Dictionary with overall statistics
        """
        results = []
        total_chunks = 0
        total_tokens = 0
        successful = 0
        failed = 0
        skipped = 0
        
        for filename in DOCUMENT_REGISTRY.keys():
            file_path = docs_dir / filename
            
            if not file_path.exists():
                logger.warning(f"File not found: {filename} (skipping)")
                results.append({
                    "file": filename,
                    "status": "not_found"
                })
                failed += 1
                continue
            
            result = await self.ingest_file(file_path, dry_run=dry_run, force=force)
            results.append(result)
            
            if result["status"] == "success":
                successful += 1
                total_chunks += result["chunks"]
                total_tokens += result.get("tokens", 0)
            elif result["status"] == "dry_run":
                total_chunks += result["chunks"]
            elif result["status"] == "skipped":
                skipped += 1
            else:
                failed += 1
        
        # Get ingestion statistics
        stats = self.tracker.get_ingestion_stats()
        
        summary = {
            "total_files": len(DOCUMENT_REGISTRY),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "total_chunks": total_chunks,
            "total_tokens": total_tokens,
            "stats": stats,
            "results": results
        }
        
        logger.info(
            f"\n{'='*60}\n"
            f"Ingestion Summary:\n"
            f"  Files processed: {successful}/{len(DOCUMENT_REGISTRY)}\n"
            f"  Skipped: {skipped}\n"
            f"  Total chunks: {total_chunks}\n"
            f"  Total tokens: {total_tokens}\n"
            f"  Failed: {failed}\n"
            f"{'='*60}\n"
            f"Overall Statistics:\n"
            f"  Total files ingested: {stats['total_files']}\n"
            f"  Total chunks: {stats['total_chunks']}\n"
            f"  Total tokens: {stats['total_tokens']}\n"
            f"  Success rate: {stats['success_rate']*100:.1f}%\n"
            f"{'='*60}"
        )
        
        return summary


async def main():
    """CLI entry point."""
    # Initialize logging for CLI output
    setup_logging(level="INFO", json_output=False)
    
    parser = argparse.ArgumentParser(
        description="Ingest Philippine labor law documents into vector store"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to single file to ingest"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all registered documents"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Use manually chunked files from kb/chunks/ instead of automatic chunking"
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Specific document folder in kb/chunks/ to ingest (e.g., 'PD-No-851'). Use with --manual"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate ingestion without writing to vector store"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion even if file is unchanged"
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only ingest new/modified files (skip unchanged)"
    )
    parser.add_argument(
        "--no-summarization",
        action="store_true",
        help="Disable summary and keyword generation"
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="kb/docs",
        help="Directory containing knowledge base documents (default: kb/docs)"
    )
    
    args = parser.parse_args()
    
    # Validate argument combinations
    if args.manual:
        # Manual mode: --folder or --file (for single chunk) or neither (all chunks)
        if args.all or args.new_only:
            parser.error("--manual cannot be used with --all or --new-only")
    else:
        # Automatic mode: need --file, --all, or --new-only
        if not args.file and not args.all and not args.new_only:
            parser.error("Must specify either --file, --all, --new-only, or use --manual mode")
        if args.folder:
            parser.error("--folder can only be used with --manual")
    
    try:
        # Initialize adapters
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        llm = get_llm_adapter()
        
        # Create ingester
        ingester = KnowledgeBaseIngester(
            embeddings_adapter=embeddings,
            vectorstore_adapter=vectorstore,
            llm_adapter=llm,
            use_summarization=not args.no_summarization
        )
        
        # Route to appropriate ingestion method
        if args.manual:
            # Manual chunking mode
            logger.info("Using manual chunking mode")
            
            # Determine what to ingest
            single_file = None
            if args.file:
                # Single chunk file
                single_file = Path(args.file)
                if not single_file.exists():
                    logger.error(f"Chunk file not found: {args.file}")
                    sys.exit(1)
            
            result = await ingester.ingest_manual_chunks(
                document_name=args.folder,
                single_file=single_file,
                dry_run=args.dry_run,
                force=args.force
            )
            
            if result["status"] == "failed":
                logger.error(f"Manual ingestion failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            elif result["status"] == "skipped":
                logger.info(
                    f"Skipped: {result.get('document', 'Document')} - {result.get('reason', 'unchanged')}"
                )
            elif result["status"] == "dry_run":
                logger.info(
                    f"[DRY RUN] Would ingest {result['chunks']} chunks "
                    f"from {result.get('document', 'all documents')}"
                )
            else:
                logger.info(
                    f"✓ Successfully ingested {result['chunks']} chunks "
                    f"({result['tokens']} tokens)"
                )
        
        else:
            # Automatic chunking mode (original behavior)
            docs_dir = Path(args.docs_dir)
            
            if args.file:
                # Ingest single file
                file_path = Path(args.file)
                if not file_path.exists():
                    logger.error(f"File not found: {args.file}")
                    sys.exit(1)
                
                result = await ingester.ingest_file(
                    file_path, 
                    dry_run=args.dry_run,
                    force=args.force
                )
                
                if result["status"] == "failed":
                    sys.exit(1)
            else:
                # Ingest all
                summary = await ingester.ingest_all(
                    docs_dir, 
                    dry_run=args.dry_run,
                    force=args.force,
                    new_only=args.new_only
                )
                
                if summary["failed"] > 0:
                    sys.exit(1)
        
        logger.info("✓ Knowledge base ingestion completed successfully")
        
    except KeyboardInterrupt:
        logger.info("\nIngestion cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
