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
        threshold: float = 0.1
    ) -> List[QueryResult]:
        """
        Perform keyword-based full-text search using PostgreSQL FTS.
        
        Args:
            query: Original query text
            keywords: Extracted keywords to search for
            limit: Maximum number of results
            threshold: Minimum rank threshold for FTS
            
        Returns:
            List of query results sorted by relevance
            
        Raises:
            AppError: If search fails
        """
        try:
            if not keywords:
                logger.warning("Keyword search called with empty keywords")
                return []
            
            # Build search query (join keywords with OR)
            search_terms = " | ".join(keywords)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Use PostgreSQL FTS with ts_rank for relevance scoring
                cursor.execute("""
                    SELECT 
                        id,
                        content,
                        metadata,
                        ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) as rank
                    FROM labor_law_sections
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    AND ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) > %s
                    ORDER BY rank DESC
                    LIMIT %s
                """, (search_terms, search_terms, search_terms, threshold, limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append(QueryResult(
                        id=row[0],
                        content=row[1],
                        metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                        score=float(row[3])
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
    
    async def direct_article_lookup(
        self,
        articles: List[str]
    ) -> List[QueryResult]:
        """
        Direct lookup of specific articles by reference.
        
        Searches for exact article matches in metadata or content.
        
        Args:
            articles: List of article references (e.g., ["Article 123", "PD 442"])
            
        Returns:
            List of matching documents with perfect scores
            
        Raises:
            AppError: If lookup fails
        """
        try:
            if not articles:
                logger.warning("Direct article lookup called with empty articles")
                return []
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                results = []
                
                for article_ref in articles:
                    # Try multiple pattern variations
                    patterns = [
                        article_ref,
                        article_ref.replace("Article ", "Art. "),
                        article_ref.replace("Art. ", "Article "),
                    ]
                    
                    for pattern in patterns:
                        # Search in content and metadata
                        cursor.execute("""
                            SELECT id, content, metadata
                            FROM labor_law_sections
                            WHERE content ILIKE %s
                            OR metadata::text ILIKE %s
                            LIMIT 5
                        """, (f"%{pattern}%", f"%{pattern}%"))
                        
                        for row in cursor.fetchall():
                            results.append(QueryResult(
                                id=row[0],
                                content=row[1],
                                metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                                score=1.0  # Perfect score for direct match
                            ))
                        
                        if results:
                            break  # Found matches, no need to try other patterns
                    
                logger.info(
                    f"Direct article lookup returned {len(results)} results "
                    f"(articles: {articles})"
                )
                
                # Deduplicate by ID
                seen_ids = set()
                unique_results = []
                for result in results:
                    if result.id not in seen_ids:
                        seen_ids.add(result.id)
                        unique_results.append(result)
                
                return unique_results
                
            finally:
                self._return_connection(conn, cursor)
                
        except Exception as e:
            logger.error(f"Direct article lookup error: {str(e)}", exc_info=True)
            # Don't fail entire pipeline - return empty results
            return []
    
    async def smart_retrieve(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        articles: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.3
    ) -> List[QueryResult]:
        """
        Smart multi-strategy retrieval orchestrator.
        
        Executes retrieval strategies in parallel based on available inputs:
        1. Direct article lookup (if articles provided) - HIGHEST priority
        2. Keyword search (if keywords provided)
        3. Semantic search (if embedding provided)
        
        Results are merged, deduplicated, and ranked by strategy priority.
        
        Args:
            query_embedding: Query vector for semantic search
            query_text: Original query text
            keywords: Extracted keywords for FTS
            articles: Article references for direct lookup
            limit: Maximum total results to return
            threshold: Minimum similarity/relevance threshold
            
        Returns:
            Merged and ranked list of query results
            
        Raises:
            AppError: If all strategies fail
        """
        try:
            logger.info(
                f"Smart retrieve: "
                f"has_embedding={query_embedding is not None}, "
                f"has_keywords={keywords is not None}, "
                f"has_articles={articles is not None}"
            )
            
            # Execute strategies in parallel
            tasks = []
            strategy_names = []
            
            # 1. Direct article lookup (highest priority)
            if articles:
                tasks.append(self.direct_article_lookup(articles))
                strategy_names.append("direct")
            
            # 2. Keyword search
            if keywords and query_text:
                tasks.append(self.keyword_search(query_text, keywords, limit, threshold * 0.3))
                strategy_names.append("keyword")
            
            # 3. Semantic search
            if query_embedding:
                tasks.append(self.query(query_embedding, limit, None, threshold))
                strategy_names.append("semantic")
            
            if not tasks:
                logger.warning("No retrieval strategies available")
                return []
            
            # Execute all strategies in parallel
            strategy_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Merge results with priority-based ranking
            merged_results = []
            result_map: Dict[str, Tuple[QueryResult, str, int]] = {}  # id -> (result, strategy, priority)
            
            strategy_priority = {"direct": 3, "keyword": 2, "semantic": 1}
            
            for strategy_name, results in zip(strategy_names, strategy_results):
                if isinstance(results, Exception):
                    logger.error(f"{strategy_name} strategy failed: {str(results)}")
                    continue
                
                if not results:
                    continue
                
                priority = strategy_priority.get(strategy_name, 0)
                
                for result in results:
                    if result.id in result_map:
                        # Keep result from higher priority strategy
                        existing_priority = result_map[result.id][2]
                        if priority > existing_priority:
                            result_map[result.id] = (result, strategy_name, priority)
                    else:
                        result_map[result.id] = (result, strategy_name, priority)
            
            # Convert to list and sort by priority, then score
            merged_results = [
                item[0] for item in sorted(
                    result_map.values(),
                    key=lambda x: (x[2], x[0].score),  # Sort by priority, then score
                    reverse=True
                )
            ]
            
            # Limit results
            merged_results = merged_results[:limit]
            
            logger.info(
                f"Smart retrieve merged {len(merged_results)} results from "
                f"{len(strategy_names)} strategies: {strategy_names}"
            )
            
            return merged_results
            
        except Exception as e:
            logger.error(f"Smart retrieve error: {str(e)}", exc_info=True)
            raise AppError(
                message="Smart retrieval failed",
                error_code="SMART_RETRIEVE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
