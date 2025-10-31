"""
Dependency injection container for service instances.

Provides factory functions for creating and managing service dependencies.
"""
from functools import lru_cache
from supabase import create_client, Client

from core import settings, get_logger
from services.auth import SessionService

# Adapters
from adapters.embeddings.openai_embed import OpenAIEmbeddings
from adapters.llm.openai_llm import OpenAILLM
from adapters.vectorstore.supabase_store import SupabaseVectorStore
from adapters.memory.langchain_memory import LangChainMemory

# Pipeline services
from services.pipeline.retrieval import RetrievalPipeline
from services.pipeline.grounding import GroundingPipeline
from services.pipeline.generation import GenerationPipeline
from services.pipeline.postprocess import PostprocessPipeline
from services.pipeline.conversation import ConversationPipeline

logger = get_logger(__name__)


# Singleton instances
_supabase_client: Client = None
_embeddings_adapter = None
_llm_adapter = None
_vectorstore_adapter = None
_memory_adapter = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton.
    
    Returns:
        Initialized Supabase client
    """
    global _supabase_client
    
    if _supabase_client is None:
        logger.info("Initializing Supabase client")
        _supabase_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_key
        )
        logger.info("Supabase client initialized successfully")
    
    return _supabase_client


@lru_cache()
def get_session_service() -> SessionService:
    """
    Get or create SessionService singleton.
    
    Returns:
        Initialized SessionService instance
    """
    supabase_client = get_supabase_client()
    return SessionService(supabase_client, settings)


# Adapter factories
def get_embeddings_adapter() -> OpenAIEmbeddings:
    """Get or create OpenAI embeddings adapter."""
    global _embeddings_adapter
    
    if _embeddings_adapter is None:
        logger.info("Initializing OpenAI embeddings adapter")
        _embeddings_adapter = OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model
        )
    
    return _embeddings_adapter


def get_llm_adapter() -> OpenAILLM:
    """Get or create OpenAI LLM adapter."""
    global _llm_adapter
    
    if _llm_adapter is None:
        logger.info("Initializing OpenAI LLM adapter")
        _llm_adapter = OpenAILLM(
            api_key=settings.openai_api_key,
            model=settings.openai_llm_model
        )
    
    return _llm_adapter


def get_vectorstore_adapter() -> SupabaseVectorStore:
    """Get or create Supabase vector store adapter."""
    global _vectorstore_adapter
    
    if _vectorstore_adapter is None:
        logger.info("Initializing Supabase vector store adapter")
        supabase_client = get_supabase_client()
        _vectorstore_adapter = SupabaseVectorStore(
            client=supabase_client,
            table_name=settings.vectorstore_table_name,
            embedding_dimension=settings.embedding_dimension
        )
    
    return _vectorstore_adapter


def get_memory_adapter() -> LangChainMemory:
    """Get or create LangChain memory adapter."""
    global _memory_adapter
    
    if _memory_adapter is None:
        logger.info("Initializing LangChain memory adapter")
        _memory_adapter = LangChainMemory(
            max_token_limit=settings.memory_token_limit
        )
    
    return _memory_adapter


# Pipeline service factories
@lru_cache()
def get_retrieval_pipeline() -> RetrievalPipeline:
    """Get or create retrieval pipeline."""
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    return RetrievalPipeline(
        embeddings=embeddings,
        vectorstore=vectorstore,
        default_top_k=settings.retrieval_top_k,
        similarity_threshold=settings.retrieval_similarity_threshold
    )


@lru_cache()
def get_grounding_pipeline() -> GroundingPipeline:
    """Get or create grounding pipeline."""
    return GroundingPipeline(
        max_context_length=settings.max_context_length
    )


@lru_cache()
def get_generation_pipeline() -> GenerationPipeline:
    """Get or create generation pipeline."""
    llm = get_llm_adapter()
    
    return GenerationPipeline(
        llm=llm,
        default_temperature=settings.llm_temperature,
        default_max_tokens=settings.llm_max_tokens,
        enable_streaming=settings.enable_streaming
    )


@lru_cache()
def get_postprocess_pipeline() -> PostprocessPipeline:
    """Get or create postprocessing pipeline."""
    return PostprocessPipeline(
        enable_auto_disclaimer=settings.enable_auto_disclaimer,
        enable_redaction=settings.enable_pii_redaction
    )


@lru_cache()
def get_conversation_pipeline() -> ConversationPipeline:
    """Get or create conversation pipeline."""
    memory = get_memory_adapter()
    
    return ConversationPipeline(
        memory=memory,
        max_history_messages=settings.max_history_messages,
        context_window_tokens=settings.context_window_tokens
    )


def cleanup_services():
    """
    Cleanup service instances and connections.
    
    Should be called during application shutdown.
    """
    global _supabase_client, _embeddings_adapter, _llm_adapter
    global _vectorstore_adapter, _memory_adapter
    
    logger.info("Cleaning up service instances")
    
    # Clear LRU caches
    get_session_service.cache_clear()
    get_retrieval_pipeline.cache_clear()
    get_grounding_pipeline.cache_clear()
    get_generation_pipeline.cache_clear()
    get_postprocess_pipeline.cache_clear()
    get_conversation_pipeline.cache_clear()
    
    # Reset singletons
    _supabase_client = None
    _embeddings_adapter = None
    _llm_adapter = None
    _vectorstore_adapter = None
    _memory_adapter = None
    
    logger.info("Service cleanup completed")
