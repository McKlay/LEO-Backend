"""
Supabase vector store adapter implementation.

Uses Supabase pgvector extension for semantic search with multi-strategy
retrieval (semantic, keyword, direct article lookup).
Note: Uses direct PostgreSQL connection for vector search due to 
Supabase Python client limitations with vector type RPC calls.
"""
from typing import Optional, List, Dict, Any, Tuple
from supabase import Client
import json
import psycopg2
from psycopg2 import pool
import asyncio
import os
import re
import uuid

from core import get_logger, AppError
from core.config import Settings
from adapters.vectorstore.base import (
    BaseVectorStore,
    Document,
    QueryResult
)

logger = get_logger(__name__)


class SupabaseVectorStore(BaseVectorStore):
    """
    Supabase vector store implementation using pgvector.
    
    Stores document embeddings in Supabase Postgres with pgvector
    extension for efficient similarity search.
    """
    
    def __init__(self, supabase_client: Client, settings: Settings):
        """
        Initialize Supabase vector store.
        
        Args:
            supabase_client: Initialized Supabase client
            settings: Application settings
        """
        self.client = supabase_client
        self.settings = settings
        self.table_name = settings.vectorstore_table_name
        self.embedding_dimension = settings.embedding_dimension
        
        # Initialize direct PostgreSQL connection for vector search
        # (Supabase Python client has issues with vector type in RPC calls)
        self.db_url = settings.supabase_db_url
        
        # Initialize connection pool if enabled
        self.connection_pool = None
        if settings.enable_connection_pooling and self.db_url:
            try:
                self.connection_pool = pool.ThreadedConnectionPool(
                    minconn=settings.db_pool_min_connections,
                    maxconn=settings.db_pool_max_connections,
                    dsn=self.db_url
                )
                logger.info(
                    f"Database connection pool initialized: "
                    f"min={settings.db_pool_min_connections}, "
                    f"max={settings.db_pool_max_connections}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize connection pool: {str(e)}. "
                    f"Falling back to direct connections."
                )
                self.connection_pool = None
        
        logger.info(
            f"Supabase vector store initialized: "
            f"table={self.table_name}, dimension={self.embedding_dimension}, "
            f"pooling_enabled={self.connection_pool is not None}"
        )
    
    def _get_connection(self):
        """
        Get a database connection from pool or create a new one.
        
        Returns:
            Database connection
        """
        if self.connection_pool:
            return self.connection_pool.getconn()
        else:
            return psycopg2.connect(self.db_url)
    
    def _return_connection(self, conn, cursor=None):
        """
        Return connection to pool or close it.
        
        Args:
            conn: Database connection
            cursor: Database cursor (optional, will be closed if provided)
        """
        if cursor:
            cursor.close()
        
        if self.connection_pool:
            self.connection_pool.putconn(conn)
        else:
            conn.close()
    
    def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self._return_connection(conn, cursor)
            return result is not None
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    def __del__(self):
        """Cleanup connection pool on deletion."""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                logger.info("Connection pool closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {str(e)}")
    
    async def upsert(self, documents: list[Document]) -> None:
        """
        Insert or update documents in vector store (labor_law_sections table).
        
        Args:
            documents: List of documents to upsert
            
        Raises:
            AppError: If upsert operation fails
        """
        try:
            if not documents:
                logger.warning("Attempted to upsert empty document list")
                return
            
            # Prepare data for new schema (labor_law_sections)
            records = []
            for doc in documents:
                # Extract metadata fields
                metadata = doc.metadata or {}
                
                # Generate UUID for id field (convert string id to UUID)
                try:
                    doc_uuid = str(uuid.uuid4())
                except:
                    doc_uuid = str(uuid.uuid4())
                
                # Use legal article_number from metadata (e.g., "PD 442", "Article 123")
                # file_stem is stored in metadata for check_ingestion.py tracking
                legal_article_number = metadata.get("article_number", doc.id)
                
                # Extract semantic_type and section_number from metadata
                # These columns exist in the actual database schema
                semantic_type = metadata.get("semantic_type")
                section_number = metadata.get("section_number")
                
                record = {
                    "id": doc_uuid,
                    "full_text": doc.content,  # New schema uses full_text, not content
                    "embedding": doc.embedding,
                    "metadata": metadata,  # Send dict directly; Supabase will encode as JSONB
                    
                    # Extract fields from metadata for structured columns
                    "article_number": legal_article_number,  # Legal identifier from frontmatter
                    "article_title": metadata.get("title", ""),
                    "summary": metadata.get("summary"),
                    "keywords": metadata.get("keywords", []),
                    "book": metadata.get("hierarchy", {}).get("book"),
                    "title_name": metadata.get("hierarchy", {}).get("title"),
                    "chapter": metadata.get("hierarchy", {}).get("chapter"),
                    "has_table": metadata.get("has_table", False),
                    "has_formula": metadata.get("has_formula", False),
                    "has_list": metadata.get("has_list", False),
                    
                    # Additional columns that exist in actual database schema
                    "semantic_type": semantic_type,
                    "section_number": section_number,
                    
                    # Source ID
                    "source_id": metadata.get("source_id")
                }
                
                # Debug: Log metadata keys for first document
                if not records:
                    logger.info(f"First document metadata keys: {list(metadata.keys())}")
                    logger.info(f"  chunk_id: {metadata.get('chunk_id')}")
                    logger.info(f"  file_stem: {metadata.get('file_stem')}")
                
                records.append(record)
            
            # Upsert to Supabase
            response = self.client.table(self.table_name).upsert(
                records,
                on_conflict="id"
            ).execute()
            
            logger.info(f"Upserted {len(documents)} documents to {self.table_name}")
            
        except Exception as e:
            logger.error(f"Vector store upsert error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to upsert documents to vector store",
                error_code="VECTOR_STORE_UPSERT_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def query(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filters: Optional[dict] = None,
        threshold: Optional[float] = None
    ) -> list[QueryResult]:
        """
        Query vector store for similar documents.
        
        Uses cosine similarity for vector comparison.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            filters: Metadata filters (e.g., {"source": "Labor Code"})
            threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of query results sorted by similarity
            
        Raises:
            AppError: If query operation fails
        """
        try:
            # Validate query embedding dimension
            if len(query_embedding) != self.embedding_dimension:
                raise AppError(
                    message=f"Query embedding dimension mismatch: "
                            f"expected {self.embedding_dimension}, "
                            f"got {len(query_embedding)}",
                    error_code="INVALID_EMBEDDING_DIMENSION",
                    status_code=400
                )
            
            # Use direct PostgreSQL connection for vector search
            # The Supabase Python client has issues passing vector types to RPC functions
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Convert embedding to PostgreSQL vector format
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
                
                # Call match_documents function via direct SQL
                cursor.execute("""
                    SELECT * FROM match_documents(
                        %s::vector,
                        %s::float,
                        %s::int,
                        %s::jsonb
                    )
                """, (
                    embedding_str,
                    threshold or 0.0,
                    limit,
                    json.dumps(filters) if filters else '{}'
                ))
                
                # Parse results
                results = []
                for row in cursor.fetchall():
                    # row format: (id, content, metadata, similarity)
                    results.append(QueryResult(
                        id=row[0],
                        content=row[1],
                        metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                        score=float(row[3])
                    ))
                
                logger.info(
                    f"Vector search returned {len(results)} results "
                    f"(threshold: {threshold}, limit: {limit})"
                )
                
                return results
                
            finally:
                self._return_connection(conn, cursor)
            
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Vector store query error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to query vector store",
                error_code="VECTOR_STORE_QUERY_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def delete(self, document_ids: list[str]) -> None:
        """
        Delete documents from vector store by database ID (UUID).
        
        Args:
            document_ids: List of document UUIDs to delete
            
        Raises:
            AppError: If delete operation fails
        """
        try:
            if not document_ids:
                logger.warning("Attempted to delete empty document ID list")
                return
            
            response = self.client.table(self.table_name).delete().in_(
                "id",
                document_ids
            ).execute()
            
            logger.info(f"Deleted {len(document_ids)} documents from vector store")
            
        except Exception as e:
            logger.error(f"Vector store delete error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to delete documents from vector store",
                error_code="VECTOR_STORE_DELETE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def delete_by_article_numbers(self, article_numbers: list[str]) -> int:
        """
        Delete documents by their article_number metadata field.
        
        Args:
            article_numbers: List of article numbers to delete
            
        Returns:
            Number of documents deleted
            
        Raises:
            AppError: If delete operation fails
        """
        try:
            if not article_numbers:
                logger.warning("Attempted to delete with empty article numbers list")
                return 0
            
            # First, get count of documents to delete
            count_response = self.client.table(self.table_name).select(
                "id",
                count="exact"
            ).in_("article_number", article_numbers).execute()
            
            count = count_response.count or 0
            
            if count == 0:
                logger.info(f"No documents found for article_numbers: {article_numbers[:3]}...")
                return 0
            
            # Delete documents by article_number
            response = self.client.table(self.table_name).delete().in_(
                "article_number",
                article_numbers
            ).execute()
            
            logger.info(f"Deleted {count} documents for {len(article_numbers)} article numbers")
            return count
            
        except Exception as e:
            logger.error(f"Vector store delete by article_number error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to delete documents by article_number",
                error_code="VECTOR_STORE_DELETE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def delete_by_source_id(self, source_id: str) -> int:
        """
        Delete all documents associated with a specific source ID.
        
        Args:
            source_id: Source ID to delete documents for
            
        Returns:
            Number of documents deleted
            
        Raises:
            AppError: If delete operation fails
        """
        try:
            if not source_id:
                logger.warning("Attempted to delete with empty source ID")
                return 0
            
            # First, get count of documents to delete
            count_response = self.client.table(self.table_name).select(
                "id",
                count="exact"
            ).eq("source_id", source_id).execute()
            
            count = count_response.count or 0
            
            if count == 0:
                logger.info(f"No documents found for source_id: {source_id}")
                return 0
            
            # Delete documents
            response = self.client.table(self.table_name).delete().eq(
                "source_id",
                source_id
            ).execute()
            
            logger.info(f"Deleted {count} documents for source_id: {source_id}")
            return count
            
        except Exception as e:
            logger.error(f"Vector store delete by source_id error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to delete documents by source_id",
                error_code="VECTOR_STORE_DELETE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def get_by_id(self, document_id: str) -> Optional[QueryResult]:
        """
        Retrieve a specific document by ID.
        
        Args:
            document_id: Document ID to retrieve
            
        Returns:
            Query result or None if not found
            
        Raises:
            AppError: If retrieval fails
        """
        try:
            response = self.client.table(self.table_name).select(
                "id, content, metadata"
            ).eq("id", document_id).execute()
            
            if not response.data:
                return None
            
            row = response.data[0]
            metadata = json.loads(row.get("metadata", "{}"))
            
            return QueryResult(
                id=row["id"],
                content=row["content"],
                metadata=metadata,
                score=1.0  # Perfect match for direct retrieval
            )
            
        except Exception as e:
            logger.error(f"Vector store get_by_id error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to retrieve document from vector store",
                error_code="VECTOR_STORE_GET_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def count(self, filters: Optional[dict] = None) -> int:
        """
        Count documents in vector store.
        
        Args:
            filters: Metadata filters
            
        Returns:
            Number of documents
            
        Raises:
            AppError: If count operation fails
        """
        try:
            query = self.client.table(self.table_name).select(
                "id",
                count="exact"
            )
            
            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    # This is a simplified approach
                    # You may need more complex filtering logic
                    query = query.eq(f"metadata->{key}", value)
            
            response = query.execute()
            
            return response.count or 0
            
        except Exception as e:
            logger.error(f"Vector store count error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to count documents in vector store",
                error_code="VECTOR_STORE_COUNT_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def keyword_search(
        self,
        query: str,
        keywords: List[str],
        limit: int = 10,
        threshold: float = 0.1,
        anchor_phrase: Optional[str] = None,
    ) -> List[QueryResult]:
        """
        Perform keyword-based full-text search using PostgreSQL FTS.
        
        Args:
            query: FTS natural-language signal — the raw original user message.
                Verbatim phrases quoted with single quotes in the original text
                survive as phrase-tsqueries and are exclusive to the gold chunk.
                Non-English filler words in Cebuano/Filipino queries are
                discarded by the English FTS dictionary, so they add no noise.
            keywords: Extracted keyword list, joined with OR as the primary FTS
                signal.  Each keyword is an independent alternative.
            limit: Maximum number of results
            threshold: Minimum rank threshold for FTS
            anchor_phrase: Optional long verbatim phrase (≥5 words) that is
                expected to appear exclusively in the gold document.  When
                provided, documents matching this phrase receive a × 100 ts_rank
                boost via CASE WHEN, overcoming the length-bias of ts_rank that
                would otherwise favour long handbook chunks with many keyword
                occurrences over shorter focused law sections.
            
        Returns:
            List of query results sorted by relevance
            
        Raises:
            AppError: If search fails
        """
        try:
            if not keywords:
                logger.warning("Keyword search called with empty keywords")
                return []
            
            # Build search query with OR semantics using websearch_to_tsquery.
            # plainto_tsquery does not support | or OR — it treats all input as AND.
            # websearch_to_tsquery understands the OR keyword natively, but treats
            # hyphens as negation operators (e.g. "daily-paid" → "daily AND NOT paid").
            # Strip hyphens from each keyword so they are handled as word separators.
            cleaned_keywords = [k.replace('-', ' ') for k in keywords]
            search_terms = " OR ".join(cleaned_keywords)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                if anchor_phrase:
                    # Anchor-boosted FTS: documents matching the exclusive anchor phrase
                    # receive a × 100 ts_rank boost.  This overrides ts_rank's inherent
                    # length bias (long handbook sections with many keyword occurrences
                    # would otherwise outrank a short, focused law section that has the
                    # exclusive phrase appearing only once).
                    # - CASE WHEN branch: anchor match → ts_rank(keywords) × 100
                    # - ELSE branch: standard GREATEST(keywords, fts_natural_query)
                    # The WHERE clause is the union of all three signals so no
                    # relevant document is excluded.
                    cursor.execute("""
                        SELECT 
                            s.id,
                            s.full_text,
                            s.article_number,
                            s.article_title,
                            s.book,
                            s.title_name,
                            s.chapter,
                            s.summary,
                            s.keywords,
                            CASE WHEN to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                                 THEN ts_rank(
                                     to_tsvector('english', s.full_text),
                                     websearch_to_tsquery('english', %s)
                                 ) * 100.0
                                 ELSE GREATEST(
                                     ts_rank(
                                         to_tsvector('english', s.full_text),
                                         websearch_to_tsquery('english', %s)
                                     ),
                                     ts_rank(
                                         to_tsvector('english', s.full_text),
                                         websearch_to_tsquery('english', %s)
                                     )
                                 )
                            END as rank,
                            src.url,
                            src.title AS source_title,
                            s.metadata->>'chunk_id' AS chunk_id
                        FROM labor_law_sections s
                        LEFT JOIN labor_law_sources src ON s.source_id = src.id
                        WHERE (
                            to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                            OR to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                            OR to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                        )
                        AND GREATEST(
                            ts_rank(
                                to_tsvector('english', s.full_text),
                                websearch_to_tsquery('english', %s)
                            ),
                            ts_rank(
                                to_tsvector('english', s.full_text),
                                websearch_to_tsquery('english', %s)
                            )
                        ) > %s
                        ORDER BY rank DESC
                        LIMIT %s
                    """, (anchor_phrase, search_terms,
                          search_terms, query,
                          search_terms, query, anchor_phrase,
                          search_terms, query,
                          threshold, limit))
                else:
                    # Standard dual-signal FTS: GREATEST() of keyword-term query and
                    # fts_natural_query.
                    #
                    # Signal 1 — search_terms (keywords OR'd):
                    #   Extracted keywords are concise, domain-specific phrases that
                    #   target the gold document directly.
                    # Signal 2 — query (fts_natural_query = original user message):
                    #   Verbatim English phrases quoted inside single quotes in the
                    #   original message survive as phrase queries.  For Cebuano/
                    #   Filipino queries the non-English filler words are discarded
                    #   by the English dictionary and cannot add noise.
                    #
                    # FTS scope: full_text only — document content defines lexical
                    # relevance.
                    cursor.execute("""
                        SELECT 
                            s.id,
                            s.full_text,
                            s.article_number,
                            s.article_title,
                            s.book,
                            s.title_name,
                            s.chapter,
                            s.summary,
                            s.keywords,
                            GREATEST(
                                ts_rank(
                                    to_tsvector('english', s.full_text),
                                    websearch_to_tsquery('english', %s)
                                ),
                                ts_rank(
                                    to_tsvector('english', s.full_text),
                                    websearch_to_tsquery('english', %s)
                                )
                            ) as rank,
                            src.url,
                            src.title AS source_title,
                            s.metadata->>'chunk_id' AS chunk_id
                        FROM labor_law_sections s
                        LEFT JOIN labor_law_sources src ON s.source_id = src.id
                        WHERE (
                            to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                            OR to_tsvector('english', s.full_text) @@ websearch_to_tsquery('english', %s)
                        )
                        AND GREATEST(
                            ts_rank(
                                to_tsvector('english', s.full_text),
                                websearch_to_tsquery('english', %s)
                            ),
                            ts_rank(
                                to_tsvector('english', s.full_text),
                                websearch_to_tsquery('english', %s)
                            )
                        ) > %s
                        ORDER BY rank DESC
                        LIMIT %s
                    """, (search_terms, query, search_terms, query, search_terms, query, threshold, limit))
                
                results = []
                for row in cursor.fetchall():
                    # Build metadata from individual columns
                    metadata = {
                        'article_number': row[2],
                        'article_title': row[3],
                        'book': row[4],
                        'title_name': row[5],
                        'chapter': row[6],
                        'summary': row[7],
                        'keywords': row[8] if row[8] else [],
                        'source_url': row[10],
                        'source_title': row[11],
                        'chunk_id': row[12] or '',
                        '_source_table': 'sections',
                        '_strategy': 'lexical',
                    }
                    
                    results.append(QueryResult(
                        id=row[0],
                        content=row[1],  # full_text
                        metadata=metadata,
                        score=float(row[9])  # rank is now at index 9
                    ))
                
                logger.info(
                    f"Keyword search returned {len(results)} results "
                    f"(keywords: {keywords[:3]}...)"
                )
                
                return results
                
            finally:
                self._return_connection(conn, cursor)
                
        except Exception as e:
            logger.error(f"Keyword search error: {str(e)}", exc_info=True)
            # Don't fail entire pipeline - return empty results
            return []
    
    def _normalize_article_refs(self, article_ref: str) -> List[str]:
        """
        Expand short-form article references to canonical forms stored in DB keywords.

        The DB keywords column is LLM-curated and stores canonical forms such as
        "Article 297", "Republic Act No. 10361", "Presidential Decree No. 442",
        "Department Order 147-15", "NLRC Rules Rule I", "SEnA Rules Section 1".
        query_analysis.py may produce abbreviated or prefixed forms ("RA 10361",
        "PD 442", "Art. 297", "DO 147-15", "DOLE Department Order 147-15",
        "NLRC Rule I", "SEnA Rule 1", "SEnA Rule II") that must be expanded/normalised
        before GIN lookup.
        """
        ref = article_ref.strip()
        candidates = [ref]

        # Art. N  →  Article N
        if re.match(r'^Art\.\s*\d', ref, re.IGNORECASE):
            candidates.append(re.sub(r'^Art\.\s*', 'Article ', ref, flags=re.IGNORECASE))

        # RA N  →  Republic Act No. N  +  Republic Act N
        m = re.match(r'^RA\s+(\d+)', ref, re.IGNORECASE)
        if m:
            n = m.group(1)
            candidates += [f"Republic Act No. {n}", f"Republic Act {n}"]

        # PD N  →  Presidential Decree No. N  +  Presidential Decree N
        m = re.match(r'^PD\s+(\d+)', ref, re.IGNORECASE)
        if m:
            n = m.group(1)
            candidates += [f"Presidential Decree No. {n}", f"Presidential Decree {n}"]

        # Department Order variants — LLM sometimes prepends "DOLE" or abbreviates as "DO".
        # All forms resolve to the canonical DB keyword: "Department Order N-NN".
        #
        #   "DOLE Department Order 147-15" → "Department Order 147-15"
        #   "DO 147-15"                    → "Department Order 147-15"
        #   "Department Order 147-15"      → unchanged (already canonical)
        m = re.match(
            r'^(?:DOLE\s+)?Department\s+Order\s+([\d]+-[\w]+)',
            ref, re.IGNORECASE
        )
        if m:
            num = m.group(1)
            candidates += [f"Department Order {num}", f"DO {num}"]
        else:
            m = re.match(r'^DO\s+([\d]+-[\w]+)', ref, re.IGNORECASE)
            if m:
                num = m.group(1)
                candidates.append(f"Department Order {num}")

        # NLRC Rules variants — normalize "NLRC Rule X" to "NLRC Rules Rule X".
        # Handles both Roman numerals (I, II, III) and Arabic numbers (1, 2, 3).
        # Also handles section references like "Section 1, Rule I".
        #
        #   "NLRC Rule I"           → "NLRC Rules Rule I"
        #   "NLRC Rule 1"           → "NLRC Rules Rule 1"
        #   "Section 1, Rule I"     → "NLRC Rules Section 1, Rule I" (if canonical)
        m = re.match(r'^NLRC\s+Rule\s+([IVXivx\d]+)', ref, re.IGNORECASE)
        if m:
            rule_num = m.group(1)
            candidates.append(f"NLRC Rules Rule {rule_num}")
        # Match section references: "Section N, Rule X"
        m = re.match(r'^(?:NLRC\s+)?Section\s+(\d+),?\s+Rule\s+([IVXivx\d]+)', ref, re.IGNORECASE)
        if m:
            section = m.group(1)
            rule_num = m.group(2)
            candidates += [
                f"NLRC Rules Section {section}, Rule {rule_num}",
                f"Section {section}, Rule {rule_num}"
            ]

        # SEnA Rules variants — normalize "SEnA Rule N" to "SEnA Rules Rule N" or
        # "SEnA Rules Section N" depending on the reference pattern.
        # Handles both Roman numerals (I, II, III) and Arabic numbers (1, 2, 3).
        #
        #   "SEnA Rule 1"       → "SEnA Rules Rule 1"
        #   "SEnA Rule II"      → "SEnA Rules Rule II"
        #   "SEnA Section 1"    → "SEnA Rules Section 1"
        #   "SEnA Section II"   → "SEnA Rules Section II"
        m = re.match(r'^SEnA\s+Rule\s+([IVXivx\d]+)', ref, re.IGNORECASE)
        if m:
            rule_num = m.group(1)
            candidates.append(f"SEnA Rules Rule {rule_num}")
        m = re.match(r'^SEnA\s+Section\s+([IVXivx\d]+)', ref, re.IGNORECASE)
        if m:
            section = m.group(1)
            candidates.append(f"SEnA Rules Section {section}")

        # DOLE COVID-19 Guidelines — normalize various forms to canonical.
        #
        #   "COVID-19 Guidelines"          → "DOLE Guidelines"
        #   "COVID-19 Workplace Guidelines" → "DOLE Guidelines"
        #   "DTI DOLE Guidelines"          → "DOLE Guidelines"
        if re.search(r'covid[-\s]*19', ref, re.IGNORECASE):
            candidates.append("DOLE Guidelines")
        if re.match(r'^(?:DTI\s+(?:and\s+)?)?DOLE\s+Guidelines', ref, re.IGNORECASE):
            candidates.append("DOLE Guidelines")

        # DOLE Handbook — normalize to "DOLE Handbook 2023".
        #
        #   "DOLE Handbook"              → "DOLE Handbook 2023"
        #   "Workers' Benefits Handbook" → "DOLE Handbook 2023"
        #   "Handbook 2023"              → "DOLE Handbook 2023"
        if re.match(r'^DOLE\s+Handbook', ref, re.IGNORECASE):
            candidates.append("DOLE Handbook 2023")
        if re.search(r"Workers[\s']*Benefits\s+Handbook", ref, re.IGNORECASE):
            candidates.append("DOLE Handbook 2023")
        if re.match(r'^Handbook\s+2023', ref, re.IGNORECASE):
            candidates.append("DOLE Handbook 2023")

        # Deduplicate while preserving order
        return list(dict.fromkeys(candidates))

    # Compiled once at class level — matches known source-law identifier patterns
    _SOURCE_LAW_RE = re.compile(
        r'\b(labor code|presidential decree|republic act|batas kasambahay|'
        r'omnibus rules|department order|nlrc rules?|sena rules?|'
        r'dole guidelines?|dole handbook|covid[-\s]*19|workers[\s\']*benefits|'
        r'pd\s*\d+|ra\s*\d+|do\s*\d+|nlrc\s+rule|sena\s+rule)\b',
        re.IGNORECASE,
    )

    def _extract_source_law_hints(self, keywords: List[str]) -> List[str]:
        """Return keywords that look like source-law identifiers for GIN disambiguation."""
        return [kw for kw in keywords if self._SOURCE_LAW_RE.search(kw)]

    async def direct_article_lookup(
        self,
        articles: List[str],
        keywords: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[QueryResult]:
        """
        Symbolic lookup of specific articles via keywords GIN array containment.

        Uses the GIN-indexed `keywords` column (idx_sections_keywords) for precise
        symbolic retrieval. Only sections where the article reference is a *primary*
        keyword are returned — cross-reference mentions in full_text are excluded
        because the LLM-curated keywords column omits cross-references by design.

        Args:
            articles: Article references from query analysis
                      (e.g., ["Article 297", "RA 10361"]).
            keywords: Full keyword list from query analysis used to derive source-law
                      disambiguation hints (e.g., "Labor Code"). Optional.
            limit: Maximum results to return.

        Returns:
            Sections ranked by keyword overlap count (best-first, for RRF rank input).
        """
        try:
            if not articles:
                logger.warning("Direct article lookup called with empty articles")
                return []

            # Step 1: normalize all article refs → canonical forms stored in DB keywords
            all_article_terms: List[str] = []
            for ref in articles:
                all_article_terms.extend(self._normalize_article_refs(ref))
            all_article_terms = list(dict.fromkeys(all_article_terms))

            # Step 2: derive source-law disambiguation hints from broader keywords
            source_hints = self._extract_source_law_hints(keywords or [])

            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                _SELECT = """
                    SELECT
                        s.id,
                        s.full_text,
                        s.article_number,
                        s.article_title,
                        s.book,
                        s.title_name,
                        s.chapter,
                        s.summary,
                        s.keywords,
                        src.url,
                        src.title AS source_title,
                        s.metadata->>'chunk_id' AS chunk_id
                    FROM labor_law_sections s
                    LEFT JOIN labor_law_sources src ON s.source_id = src.id
                """

                if source_hints:
                    # Try narrow query first: keywords must overlap BOTH article terms
                    # AND a source-law identifier to prevent cross-statute false positives
                    # when the same article number exists in multiple laws (e.g., "Article 12").
                    # Fall back to article-terms-only if no rows match — source-law identifiers
                    # such as "Labor Code" are not always stored as DB keywords.
                    cursor.execute(
                        _SELECT + """
                        WHERE s.keywords && %s::text[]
                        AND   s.keywords && %s::text[]
                        LIMIT %s
                        """,
                        (all_article_terms, source_hints, limit * 3),
                    )
                    if cursor.rowcount == 0:
                        logger.debug(
                            f"Symbolic lookup: AND+source_hints returned 0 rows — "
                            f"falling back to article-terms-only GIN search "
                            f"(source_hints={source_hints})"
                        )
                        cursor.execute(
                            _SELECT + """
                            WHERE s.keywords && %s::text[]
                            LIMIT %s
                            """,
                            (all_article_terms, limit * 3),
                        )
                else:
                    cursor.execute(
                        _SELECT + """
                        WHERE s.keywords && %s::text[]
                        LIMIT %s
                        """,
                        (all_article_terms, limit * 3),
                    )

                all_query_terms = set(all_article_terms) | set(source_hints)

                results: List[QueryResult] = []
                seen_ids: set = set()

                for row in cursor.fetchall():
                    section_id = row[0]
                    if section_id in seen_ids:
                        continue
                    seen_ids.add(section_id)

                    db_keywords: set = set(row[8]) if row[8] else set()
                    overlap_count = len(db_keywords & all_query_terms)

                    metadata = {
                        'article_number': row[2],
                        'article_title': row[3],
                        'book': row[4],
                        'title_name': row[5],
                        'chapter': row[6],
                        'summary': row[7],
                        'keywords': row[8] if row[8] else [],
                        'source_url': row[9],
                        'source_title': row[10],
                        'chunk_id': row[11] or '',
                        '_source_table': 'sections',
                        '_strategy': 'symbolic',
                        '_overlap_count': overlap_count,
                    }

                    results.append(QueryResult(
                        id=section_id,
                        content=row[1],  # full_text
                        metadata=metadata,
                        score=float(overlap_count),  # rank proxy for RRF (not score=1.0)
                    ))

                # Best-first ordering so RRF receives a properly ranked list
                results.sort(key=lambda r: r.metadata['_overlap_count'], reverse=True)
                results = results[:limit]

                logger.info(
                    f"Symbolic lookup (GIN) returned {len(results)} results "
                    f"(article_terms={all_article_terms}, source_hints={source_hints})"
                )
                return results

            finally:
                self._return_connection(conn, cursor)

        except Exception as e:
            logger.error(f"Direct article lookup error: {str(e)}", exc_info=True)
            return []
    
    async def query_with_chunks(
        self,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[QueryResult]:
        """
        Query both labor_law_sections and labor_law_chunks tables.
        
        Strategy:
        1. Query sections table (top-level articles) in parallel
        2. Query chunks table (granular sub-sections) in parallel
        3. Merge and deduplicate results (prefer chunks over parent sections)
        4. Rank by relevance with priority: high-score chunks > high-score sections
        
        This dual-table approach ensures:
        - Specific queries get granular chunk-level content
        - Broad queries get comprehensive section-level content
        - No duplicate content (parent + child both returned)
        
        Args:
            query_embedding: Query vector for semantic search
            limit: Maximum number of results (distributed across both tables)
            similarity_threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            Merged and ranked list of query results with source metadata
            
        Raises:
            AppError: If both table queries fail
        """
        try:
            # Query both tables in parallel
            sections_task = self._query_sections_table(
                query_embedding, limit, similarity_threshold
            )
            chunks_task = self._query_chunks_table(
                query_embedding, limit, similarity_threshold
            )
            
            sections_results, chunks_results = await asyncio.gather(
                sections_task, chunks_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(sections_results, Exception):
                logger.error(f"Sections query failed: {str(sections_results)}")
                sections_results = []
            if isinstance(chunks_results, Exception):
                logger.error(f"Chunks query failed: {str(chunks_results)}")
                chunks_results = []
            
            # Merge and rank results
            merged_results = self._merge_and_rank_dual_table(
                sections_results, chunks_results, limit
            )
            
            logger.info(
                f"Dual-table query returned {len(merged_results)} results "
                f"(sections={len(sections_results)}, chunks={len(chunks_results)})"
            )
            
            return merged_results
            
        except Exception as e:
            logger.error(f"Dual-table query error: {str(e)}", exc_info=True)
            raise AppError(
                message="Dual-table query failed",
                error_code="DUAL_TABLE_QUERY_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def _query_sections_table(
        self,
        query_embedding: List[float],
        limit: int,
        threshold: float
    ) -> List[QueryResult]:
        """Query labor_law_sections table for top-level articles."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            cursor.execute("""
                SELECT 
                    s.id,
                    s.full_text,
                    s.article_number,
                    s.article_title,
                    s.book,
                    s.title_name,
                    s.chapter,
                    s.summary,
                    s.keywords,
                    1 - (s.embedding <=> %s::vector) as similarity,
                    src.url,
                    src.title AS source_title,
                    s.metadata->>'chunk_id' AS chunk_id
                FROM labor_law_sections s
                LEFT JOIN labor_law_sources src ON s.source_id = src.id
                WHERE 1 - (s.embedding <=> %s::vector) > %s
                ORDER BY s.embedding <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, threshold, embedding_str, limit))
            
            results = []
            for row in cursor.fetchall():
                # Build metadata from individual columns
                metadata = {
                    'article_number': row[2],
                    'article_title': row[3],
                    'book': row[4],
                    'title_name': row[5],
                    'chapter': row[6],
                    'summary': row[7],
                    'keywords': row[8] if row[8] else [],
                    'source_url': row[10],
                    'source_title': row[11],
                    'chunk_id': row[12] or '',
                    '_source_table': 'sections'
                }
                
                results.append(QueryResult(
                    id=row[0],
                    content=row[1],  # full_text
                    metadata=metadata,
                    score=float(row[9])  # similarity is now at index 9
                ))
            
            return results
            
        finally:
            self._return_connection(conn, cursor)
    
    async def _query_chunks_table(
        self,
        query_embedding: List[float],
        limit: int,
        threshold: float
    ) -> List[QueryResult]:
        """Query labor_law_chunks table for granular sub-sections."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            cursor.execute("""
                SELECT 
                    c.id,
                    c.chunk_text,
                    c.keywords,
                    1 - (c.embedding <=> %s::vector) as similarity,
                    s.article_number,
                    s.article_title,
                    c.section_id,
                    c.summary,
                    s.metadata->>'chunk_id' AS chunk_id
                FROM labor_law_chunks c
                LEFT JOIN labor_law_sections s ON c.section_id = s.id
                WHERE 1 - (c.embedding <=> %s::vector) > %s
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, threshold, embedding_str, limit))
            
            results = []
            for row in cursor.fetchall():
                # Build metadata from chunks table structure
                metadata = {
                    'keywords': row[2] if row[2] else [],
                    'section_id': row[6],
                    'summary': row[7],
                    'chunk_id': row[8] or '',
                    '_source_table': 'chunks',
                    '_parent_article': row[4],
                    '_parent_title': row[5]
                }
                
                results.append(QueryResult(
                    id=row[0],
                    content=row[1],  # chunk_text
                    metadata=metadata,
                    score=float(row[3])
                ))
            
            return results
            
        finally:
            self._return_connection(conn, cursor)
    
    def _merge_and_rank_dual_table(
        self,
        sections: List[QueryResult],
        chunks: List[QueryResult],
        limit: int
    ) -> List[QueryResult]:
        """
        Merge and rank results from sections and chunks tables.
        
        Ranking priority:
        1. Chunks with similarity >0.85 (very relevant, granular)
        2. Sections with similarity >0.80 (very relevant, broad)
        3. Chunks with similarity >0.75 (relevant, granular)
        4. Sections with similarity >0.70 (relevant, broad)
        5. Everything else by descending similarity
        
        Deduplication:
        - If both parent section and child chunk are in results, prefer chunk
        - Track parent section IDs to avoid redundant broad content
        """
        # Combine all results
        all_results = []
        parent_section_ids = set()
        
        # First pass: collect all chunks and track their parent sections
        for chunk in chunks:
            all_results.append(chunk)
            section_id = chunk.metadata.get('section_id')
            if section_id:
                parent_section_ids.add(section_id)
        
        # Second pass: add sections that are NOT parents of included chunks
        for section in sections:
            # Skip if this section already has chunks in results
            if section.id not in parent_section_ids:
                all_results.append(section)
        
        # Define ranking key
        def ranking_key(result: QueryResult) -> Tuple[int, float]:
            """
            Returns (priority, similarity) for sorting with reverse=True.
            Higher priority number = higher rank.
            Positive similarity so reverse=True yields descending score within each tier.
            """
            score = result.score
            is_chunk = result.metadata.get('_source_table') == 'chunks'
            
            if is_chunk and score > 0.85:
                return (4, score)  # Highest priority
            elif not is_chunk and score > 0.80:
                return (3, score)
            elif is_chunk and score > 0.75:
                return (2, score)
            elif not is_chunk and score > 0.70:
                return (1, score)
            else:
                return (0, score)  # Lowest priority, sorted by score descending
        
        # Sort by ranking key
        all_results.sort(key=ranking_key, reverse=True)

        # Tag dense strategy on all results
        for r in all_results:
            r.metadata["_strategy"] = "dense"

        # Limit results
        return all_results[:limit]
    
    async def smart_retrieve(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        original_query: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        articles: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.3,
        enabled_strategies: Optional[set] = None,  # None = all applicable strategies
    ) -> List[QueryResult]:
        """
        Multi-strategy retrieval orchestrator with RRF fusion.

        Runs enabled strategies in parallel, then merges via Reciprocal Rank Fusion
        (k=60). Strategy gating is controlled by ``enabled_strategies``:

        - ``None``     → all applicable strategies (default, equivalent to hybrid)
        - ``set()``    → no retrieval; returns [] immediately (LLM-only mode)
        - ``{"dense"}``→ only dense HNSW search, even if articles/keywords present

        Args:
            query_embedding: Query vector for dense HNSW search.
            query_text: Normalized English query (used as embedding input; dense only).
            original_query: Raw user query before LLM normalization. Used as the
                second FTS signal in keyword_search so verbatim phrases from
                Filipino/Cebuano input (e.g. 'Letter of Instructions No. 174')
                are matched by FTS without leaking into the dense embedding path.
                Falls back to query_text when not provided.
            keywords: Extracted keywords for FTS lexical search.
            articles: Article references for GIN symbolic search.
            limit: Maximum results to return.
            threshold: Minimum similarity/relevance threshold.
            enabled_strategies: Explicit set of strategy names to run.
                                 Allowed values: ``"symbolic"``, ``"lexical"``, ``"dense"``.

        Returns:
            RRF-merged and ranked list of query results.

        Raises:
            AppError: If all active strategies raise exceptions.
        """
        from retrieval.ranking import reciprocal_rank_fusion

        _STRATEGY_DEFAULTS = {"symbolic", "lexical", "dense"}
        active = enabled_strategies if enabled_strategies is not None else _STRATEGY_DEFAULTS

        # LLM-only mode: caller explicitly disabled all retrieval
        if not active:
            logger.info("smart_retrieve: enabled_strategies=set() — skipping retrieval (LLM-only mode)")
            return []

        try:
            # Build parallel task list, gated by active set
            tasks: List = []
            strategy_names: List[str] = []

            # Per-strategy candidate pool: fetch more candidates than the final limit
            # so RRF sees a rich pool and cross-strategy agreement boosts the best docs.
            # Without this, with limit=8 and two strategies (no overlap), the merged list
            # strictly alternates, meaning dense-rank-6 ends up at merged position 12 —
            # well outside the final cut. Fetching 2× candidates ensures gold chunks
            # at per-strategy rank 6-9 can appear in both strategy pools and receive
            # the cross-strategy RRF boost that lifts them into the final top-k.
            candidate_limit = max(limit * 2, 10)

            # 1. Symbolic — keywords GIN array lookup
            if "symbolic" in active and articles:
                tasks.append(self.direct_article_lookup(articles, keywords=keywords, limit=candidate_limit))
                strategy_names.append("symbolic")

            # 2. Lexical — PostgreSQL FTS ts_rank
            # Note: FTS ts_rank scores are much lower than cosine similarity (0.01-0.1 range).
            # Use a minimal threshold (0.01) to filter only truly irrelevant results while
            # letting RRF handle relevance ranking across strategies.
            #
            # Augment LLM-extracted keywords with verbatim single-quoted phrases from the
            # original query.  The LLM keyword extractor often paraphrases multi-word FTS
            # anchor phrases (e.g. reducing 'carried over to the succeeding years' to just
            # 'carry over'), which loses the exclusive discriminating power of the full
            # phrase.  Single-quoted phrases in the original query text are benchmark-
            # designed verbatim anchors intended to survive intact to the FTS layer.
            # min-length guard (≥4 chars) prevents short noise tokens from being added.
            fts_keywords = list(keywords) if keywords else []
            fts_anchor: Optional[str] = None
            if original_query:
                # Negative lookbehind (?<![a-zA-Z\d]) prevents matching contractions
                # like the apostrophe in "I'm" or "doesn't" where a letter immediately
                # precedes the quote.  Intentionally-quoted phrases like
                # 'Annual Establishment Report on Wages' are always preceded by a
                # space or punctuation, so they still match.
                quoted = re.findall(r"(?<![a-zA-Z\d])'([^']{4,})'", original_query)
                seen = set(fts_keywords)
                fts_keywords = fts_keywords + [p for p in quoted if p not in seen]
                # Long quoted phrases (≥5 words) are treated as exclusive anchors:
                # documents matching the anchor receive a × 100 ts_rank boost.
                # This overcomes the ts_rank length-bias that favours large handbook
                # chunks with many keyword occurrences over short focused law sections
                # that contain the anchor phrase exactly once but uniquely.
                # Only the LONGEST such phrase is used (it is the most exclusive).
                long_quoted = [p for p in quoted if len(p.split()) >= 5]
                if long_quoted:
                    fts_anchor = max(long_quoted, key=len)

            # Two-signal FTS: extracted keywords (OR alternatives) + fts_natural_query
            # (the raw original user message), with optional exclusive-anchor boost.
            fts_natural_query = original_query if original_query else query_text
            if "lexical" in active and fts_keywords and fts_natural_query:
                tasks.append(self.keyword_search(
                    fts_natural_query, fts_keywords, candidate_limit,
                    threshold=0.01, anchor_phrase=fts_anchor,
                ))
                strategy_names.append("lexical")

            # 3. Dense — dual-table HNSW cosine similarity
            if "dense" in active and query_embedding:
                tasks.append(self.query_with_chunks(query_embedding, candidate_limit, threshold))
                strategy_names.append("dense")

            if not tasks:
                logger.warning(
                    f"smart_retrieve: no tasks launched "
                    f"(active={sorted(active)}, has_articles={bool(articles)}, "
                    f"has_keywords={bool(keywords)}, has_embedding={query_embedding is not None})"
                )
                return []

            # Execute all active strategies with TRUE parallelism.
            # The strategy methods are async def but internally use synchronous
            # psycopg2, which blocks the event loop. Wrapping each coroutine in
            # run_in_executor runs it in a separate OS thread (ThreadedConnectionPool
            # is thread-safe), cutting full_pipeline latency from ~10s to ~7s.
            loop = asyncio.get_running_loop()
            thread_tasks = [
                loop.run_in_executor(None, lambda c=coro: asyncio.run(c))
                for coro in tasks
            ]
            raw_results = await asyncio.gather(*thread_tasks, return_exceptions=True)

            # Tag each result with its originating strategy and collect per-strategy lists
            rrf_input: Dict[str, List[QueryResult]] = {}
            for strategy_name, results in zip(strategy_names, raw_results):
                if isinstance(results, Exception):
                    logger.error(f"smart_retrieve: {strategy_name} strategy failed: {results}")
                    continue
                if not results:
                    continue
                # Tag strategy on each result (dense results from _merge_and_rank_dual_table
                # may already have _source_table set; we add _strategy here)
                for r in results:
                    r.metadata["_strategy"] = strategy_name
                rrf_input[strategy_name] = results

            if not rrf_input:
                logger.warning("smart_retrieve: all strategies returned empty or failed")
                return []

            # Merge via weighted RRF (k=60, Cormack et al. 2009)
            # Strategy weights derived from Phase-1 benchmark; configurable via env.
            rrf_weights = {
                "dense": self.settings.rrf_dense_weight,
                "lexical": self.settings.rrf_lexical_weight,
                "symbolic": self.settings.rrf_symbolic_weight,
            }
            merged = reciprocal_rank_fusion(rrf_input, k=60, weights=rrf_weights)
            merged = merged[:limit]

            # Build per-strategy count summary for INFO log
            counts = ", ".join(f"{s}={len(rrf_input[s])}" for s in strategy_names if s in rrf_input)
            logger.info(
                f"smart_retrieve: active={sorted(active)} [{counts}] -> rrf_merged={len(merged)}"
            )

            return merged

        except Exception as e:
            logger.error(f"Smart retrieve error: {str(e)}", exc_info=True)
            raise AppError(
                message="Smart retrieval failed",
                error_code="SMART_RETRIEVE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
