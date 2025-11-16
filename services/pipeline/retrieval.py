"""
Retrieval pipeline module for multi-strategy search and context retrieval.

Handles query embedding, vector search, keyword search, and direct article lookup
with intelligent routing based on query analysis.
"""
from typing import List, Optional, Dict, Any
import time

from core import get_logger, AppError
from adapters.embeddings.base import BaseEmbeddings
from adapters.vectorstore.base import BaseVectorStore, QueryResult


logger = get_logger(__name__)


class RetrievalPipeline:
    """
    Handles semantic search and context retrieval.
    
    Orchestrates embedding generation and vector search to retrieve
    relevant knowledge base context for user queries.
    """
    
    def __init__(
        self,
        embeddings: BaseEmbeddings,
        vectorstore: BaseVectorStore,
        default_top_k: int = 5,
        similarity_threshold: float = 0.3  # Lowered to 0.3 for better recall with small KB
    ):
        """
        Initialize retrieval pipeline.
        
        Args:
            embeddings: Embeddings adapter for query vectorization
            vectorstore: Vector store for semantic search
            default_top_k: Default number of results to retrieve
            similarity_threshold: Minimum similarity score (0-1)
        """
        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self.default_top_k = default_top_k
        self.similarity_threshold = similarity_threshold
        
        logger.info(
            f"Retrieval pipeline initialized (top_k={default_top_k}, "
            f"threshold={similarity_threshold})"
        )
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        intent_category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        articles: Optional[List[str]] = None
    ) -> List[QueryResult]:
        """
        Retrieve relevant context using smart multi-strategy retrieval.
        
        Automatically routes to optimal retrieval strategy based on inputs:
        - Direct article lookup if article references provided
        - Keyword search if keywords provided
        - Semantic search if no specific indicators
        
        Args:
            query: User query text
            top_k: Number of results to retrieve (uses default if None)
            filters: Metadata filters for the search
            intent_category: Optional intent category to filter by
            keywords: Optional extracted keywords for keyword search
            articles: Optional article references for direct lookup
            
        Returns:
            List of query results with content and metadata
            
        Raises:
            AppError: If retrieval fails
        """
        try:
            start_time = time.time()
            
            # Use default top_k if not specified
            k = top_k or self.default_top_k
            
            logger.debug(f"Retrieving context for query: {query[:100]}...")
            
            # 1. Generate query embedding (always needed for fallback)
            embedding_response = await self.embeddings.embed_text(query)
            query_vector = embedding_response.embedding
            
            logger.debug(f"Generated query embedding (dim={len(query_vector)})")
            
            # 2. Use smart_retrieve for multi-strategy approach
            results = await self.vectorstore.smart_retrieve(
                query_embedding=query_vector,
                query_text=query,
                keywords=keywords,
                articles=articles,
                limit=k,
                threshold=self.similarity_threshold
            )
            
            elapsed = time.time() - start_time
            
            logger.info(
                f"Smart retrieval completed in {elapsed:.2f}s: "
                f"{len(results)} results "
                f"(articles={bool(articles)}, keywords={bool(keywords)})"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to retrieve relevant context",
                error_code="RETRIEVAL_FAILED",
                status_code=500,
                details={
                    "error": str(e),
                    "query_length": len(query)
                }
            )
    
    async def retrieve_with_reranking(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        intent_category: Optional[str] = None,
        rerank_top_n: Optional[int] = None
    ) -> List[QueryResult]:
        """
        Retrieve and rerank results (reranker hook for future implementation).
        
        Args:
            query: User query text
            top_k: Number of initial results to retrieve
            filters: Metadata filters for the search
            intent_category: Optional intent category to filter by
            rerank_top_n: Number of results to return after reranking
            
        Returns:
            List of reranked query results
        """
        # For now, just call standard retrieval
        # TODO: Implement reranking when reranker adapter is added
        results = await self.retrieve(
            query=query,
            top_k=top_k,
            filters=filters,
            intent_category=intent_category
        )
        
        # Apply rerank limit if specified
        if rerank_top_n and len(results) > rerank_top_n:
            results = results[:rerank_top_n]
        
        return results
    
    def format_context(self, results: List[QueryResult]) -> str:
        """
        Format retrieval results into a context string.
        
        Args:
            results: List of query results
            
        Returns:
            Formatted context string with citations
        """
        if not results:
            return "No relevant context found."
        
        context_parts = []
        for idx, result in enumerate(results, 1):
            # Extract source information
            source = result.metadata.get("source", "Unknown")
            section = result.metadata.get("section", "")
            
            # Format citation
            citation = f"[{idx}] {source}"
            if section:
                citation += f" - {section}"
            
            # Add content with citation
            context_parts.append(
                f"{citation}\n{result.content}\n"
            )
        
        return "\n".join(context_parts)
    
    def extract_citations(self, results: List[QueryResult]) -> List[Dict[str, Any]]:
        """
        Extract citation information from results.
        
        Args:
            results: List of query results
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        for idx, result in enumerate(results, 1):
            citations.append({
                "id": idx,
                "source": result.metadata.get("source", "Unknown"),
                "section": result.metadata.get("section"),
                "url": result.metadata.get("url"),
                "similarity": result.similarity_score
            })
        
        return citations
