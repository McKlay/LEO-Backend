"""
Supabase vector store adapter implementation.

Uses Supabase pgvector extension for semantic search.
Note: Uses direct PostgreSQL connection for vector search due to 
Supabase Python client limitations with vector type RPC calls.
"""
from typing import Optional
from supabase import Client
import json
import psycopg2
import os

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
        
        logger.info(
            f"Supabase vector store initialized: "
            f"table={self.table_name}, dimension={self.embedding_dimension}"
        )
    
    async def upsert(self, documents: list[Document]) -> None:
        """
        Insert or update documents in vector store.
        
        Args:
            documents: List of documents to upsert
            
        Raises:
            AppError: If upsert operation fails
        """
        try:
            if not documents:
                logger.warning("Attempted to upsert empty document list")
                return
            
            # Prepare data for insertion
            records = []
            for doc in documents:
                record = {
                    "id": doc.id,
                    "content": doc.content,
                    "embedding": doc.embedding,
                    "metadata": json.dumps(doc.metadata) if doc.metadata else "{}"
                }
                records.append(record)
            
            # Upsert to Supabase
            response = self.client.table(self.table_name).upsert(
                records,
                on_conflict="id"
            ).execute()
            
            logger.info(f"Upserted {len(documents)} documents to vector store")
            
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
            conn = psycopg2.connect(self.db_url)
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
                cursor.close()
                conn.close()
            
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
        Delete documents from vector store.
        
        Args:
            document_ids: List of document IDs to delete
            
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
