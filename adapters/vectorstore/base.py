"""
Base interface for vector store adapters.

Defines the contract for vector database operations,
enabling easy swapping between vector stores (Supabase, Pinecone, etc.).
"""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class Document(BaseModel):
    """Document model for vector store."""
    
    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, any] = {}


class QueryResult(BaseModel):
    """Vector similarity search result."""
    
    id: str
    content: str
    metadata: dict[str, any]
    score: float  # Similarity score


class BaseVectorStore(ABC):
    """
    Base vector store adapter interface.
    
    All vector store implementations (Supabase, Pinecone, Weaviate, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def upsert(
        self,
        documents: list[Document]
    ) -> None:
        """
        Insert or update documents in vector store.
        
        Args:
            documents: List of documents to upsert
            
        Raises:
            VectorStoreError: If upsert operation fails
        """
        pass
    
    @abstractmethod
    async def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, any]] = None
    ) -> list[QueryResult]:
        """
        Query vector store for similar documents.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of similar documents with scores
            
        Raises:
            VectorStoreError: If query operation fails
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        document_ids: list[str]
    ) -> None:
        """
        Delete documents from vector store.
        
        Args:
            document_ids: List of document IDs to delete
            
        Raises:
            VectorStoreError: If delete operation fails
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document if found, None otherwise
            
        Raises:
            VectorStoreError: If retrieval fails
        """
        pass
