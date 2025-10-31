"""
Integration tests for Phase 1.B: Core Chat Infrastructure.

Tests adapters (embeddings, LLM, vectorstore, memory) and pipeline modules.
"""
import pytest
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.embeddings.openai_embed import OpenAIEmbeddings
from adapters.llm.openai_llm import OpenAILLM
from adapters.vectorstore.base import Document, QueryResult
from adapters.memory.langchain_memory import LangChainMemory
from services.pipeline.retrieval import RetrievalPipeline
from services.pipeline.grounding import GroundingPipeline
from services.pipeline.generation import GenerationPipeline
from services.pipeline.postprocess import PostprocessPipeline
from services.pipeline.conversation import ConversationPipeline
from core.config import settings


class MockVectorStore:
    """Mock vector store for testing without Supabase."""
    
    async def upsert(self, documents: List[Document]) -> int:
        return len(documents)
    
    async def query(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: dict = None
    ) -> List[QueryResult]:
        # Return mock results
        return [
            QueryResult(
                id=f"doc_{i}",
                content=f"Sample labor law content {i} about employee rights and benefits.",
                metadata={
                    "source": "Labor Code of the Philippines",
                    "section": f"Article {100 + i}",
                    "url": f"https://example.com/labor-code/article-{100 + i}"
                },
                score=0.9 - (i * 0.1)
            )
            for i in range(min(top_k, 3))
        ]
    
    async def delete(self, document_ids: List[str]) -> int:
        return len(document_ids)


@pytest.mark.asyncio
class TestEmbeddingsAdapter:
    """Test OpenAI embeddings adapter."""
    
    @patch('adapters.embeddings.openai_embed.AsyncOpenAI')
    async def test_embed_text(self, mock_openai_class):
        """Test single text embedding generation."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 10
        mock_response.model = "text-embedding-3-small"
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        adapter = OpenAIEmbeddings(
            api_key="test-key",
            model="text-embedding-3-small"
        )
        
        response = await adapter.embed_text("What are employee rights in the Philippines?")
        
        assert response.embedding is not None
        assert len(response.embedding) == 1536
        assert response.tokens_used == 10
        assert response.model == "text-embedding-3-small"
    
    @patch('adapters.embeddings.openai_embed.AsyncOpenAI')
    async def test_embed_batch(self, mock_openai_class):
        """Test batch embedding generation."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock different responses for each batch call
        # First call: 2 texts -> 2 embeddings
        mock_response1 = MagicMock()
        mock_response1.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536)
        ]
        mock_response1.usage.total_tokens = 30
        mock_response1.model = "text-embedding-3-small"
        
        # Second call: 1 text -> 1 embedding
        mock_response2 = MagicMock()
        mock_response2.data = [
            MagicMock(embedding=[0.3] * 1536)
        ]
        mock_response2.usage.total_tokens = 30
        mock_response2.model = "text-embedding-3-small"
        
        # Configure side_effect to return different responses per call
        mock_client.embeddings.create = AsyncMock(side_effect=[mock_response1, mock_response2])
        
        adapter = OpenAIEmbeddings(
            api_key="test-key",
            model="text-embedding-3-small"
        )
        
        texts = [
            "overtime pay rules",
            "maternity leave benefits",
            "minimum wage regulations"
        ]
        
        response = await adapter.embed_batch(texts, batch_size=2)
        
        # BatchEmbeddingResponse has .embeddings list
        assert len(response.embeddings) == 3
        assert all(len(emb) == 1536 for emb in response.embeddings)
        # With batch_size=2 and 3 texts, embed_batch makes 2 API calls (2 + 1 texts)
        # Each call returns 30 tokens, so total is 60
        assert response.total_tokens_used == 60


@pytest.mark.asyncio
class TestLLMAdapter:
    """Test OpenAI LLM adapter."""
    
    @patch('adapters.llm.openai_llm.AsyncOpenAI')
    async def test_generate(self, mock_openai_class):
        """Test standard LLM generation."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "4"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(total_tokens=50, prompt_tokens=10, completion_tokens=40)
        mock_response.model = "gpt-4-turbo-preview"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        adapter = OpenAILLM(
            api_key="test-key",
            model="gpt-4-turbo-preview"
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"}
        ]
        
        response = await adapter.generate(messages=messages, temperature=0.1, max_tokens=50)
        
        assert response.content is not None
        assert len(response.content) > 0
        assert "4" in response.content
        assert response.tokens_used == 50  # LLMResponse uses tokens_used, not usage dict
    
    @patch('adapters.llm.openai_llm.AsyncOpenAI')
    async def test_stream(self, mock_openai_class):
        """Test streaming LLM generation."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Create async generator for streaming
        async def mock_stream():
            for content in ["1", " 2", " 3"]:
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock(delta=MagicMock(content=content))]
                yield mock_chunk
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        
        adapter = OpenAILLM(
            api_key="test-key",
            model="gpt-4-turbo-preview"
        )
        
        messages = [
            {"role": "user", "content": "Count from 1 to 3"}
        ]
        
        chunks = []
        async for chunk in adapter.stream(messages=messages, temperature=0.1, max_tokens=50):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0


@pytest.mark.asyncio
class TestMemoryAdapter:
    """Test LangChain memory adapter."""
    
    async def test_add_and_retrieve(self):
        """Test adding and retrieving messages."""
        memory = LangChainMemory(max_token_limit=4000)
        session_id = "test_session_123"
        
        # Add messages
        await memory.add_message(session_id, "user", "Hello")
        await memory.add_message(session_id, "assistant", "Hi there!")
        await memory.add_message(session_id, "user", "How are you?")
        
        # Retrieve history
        history = await memory.get_history(session_id)
        
        assert len(history.messages) == 3
        assert history.messages[0].role == "user"
        assert history.messages[0].content == "Hello"
        assert history.messages[1].role == "assistant"
    
    async def test_clear_history(self):
        """Test clearing conversation history."""
        memory = LangChainMemory(max_token_limit=4000)
        session_id = "test_session_456"
        
        await memory.add_message(session_id, "user", "Test message")
        await memory.clear_history(session_id)
        
        history = await memory.get_history(session_id)
        assert len(history.messages) == 0


@pytest.mark.asyncio
class TestRetrievalPipeline:
    """Test retrieval pipeline."""
    
    @patch('adapters.embeddings.openai_embed.AsyncOpenAI')
    async def test_retrieve(self, mock_openai_class):
        """Test context retrieval."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 10
        mock_response.model = "text-embedding-3-small"
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        embeddings = OpenAIEmbeddings(
            api_key="test-key",
            model="text-embedding-3-small"
        )
        vectorstore = MockVectorStore()
        
        pipeline = RetrievalPipeline(
            embeddings=embeddings,
            vectorstore=vectorstore,
            default_top_k=3,
            similarity_threshold=0.7
        )
        
        results = await pipeline.retrieve("What are overtime pay rules?")
        
        assert len(results) > 0
        assert all(r.score >= 0.7 for r in results)
    
    @patch('adapters.embeddings.openai_embed.AsyncOpenAI')
    async def test_format_context(self, mock_openai_class):
        """Test context formatting."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 10
        mock_response.model = "text-embedding-3-small"
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        
        embeddings = OpenAIEmbeddings(
            api_key="test-key",
            model="text-embedding-3-small"
        )
        vectorstore = MockVectorStore()
        
        pipeline = RetrievalPipeline(
            embeddings=embeddings,
            vectorstore=vectorstore
        )
        
        results = await pipeline.retrieve("test query")
        formatted = pipeline.format_context(results)
        
        assert len(formatted) > 0
        assert "[1]" in formatted


@pytest.mark.asyncio
class TestGroundingPipeline:
    """Test grounding pipeline."""
    
    async def test_build_grounded_prompt(self):
        """Test grounded prompt construction."""
        pipeline = GroundingPipeline(max_context_length=8000)
        
        mock_results = [
            QueryResult(
                id="doc_1",
                content="Labor law content about overtime",
                metadata={"source": "Labor Code", "section": "Article 87"},
                score=0.9
            )
        ]
        
        messages = pipeline.build_grounded_prompt(
            query="What are overtime rules?",
            context_results=mock_results,
            language="en"
        )
        
        assert len(messages) >= 2  # system + user
        assert messages[0]["role"] == "system"
        assert "Labor Code" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
    
    async def test_extract_citation_metadata(self):
        """Test citation metadata extraction."""
        pipeline = GroundingPipeline()
        
        mock_results = [
            QueryResult(
                id="doc_1",
                content="Test content",
                metadata={"source": "Test Source", "section": "Section 1"},
                score=0.95
            )
        ]
        
        citations = pipeline.extract_citation_metadata(mock_results)
        
        assert len(citations) == 1
        assert citations[0]["id"] == 1
        assert citations[0]["source"] == "Test Source"
        assert citations[0]["citation_key"] == "[1]"


@pytest.mark.asyncio
class TestGenerationPipeline:
    """Test generation pipeline."""
    
    @patch('adapters.llm.openai_llm.AsyncOpenAI')
    async def test_generate(self, mock_openai_class):
        """Test response generation."""
        # Setup mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "10"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(total_tokens=50, prompt_tokens=10, completion_tokens=40)
        mock_response.model = "gpt-4-turbo-preview"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        llm = OpenAILLM(
            api_key="test-key",
            model="gpt-4-turbo-preview"
        )
        
        pipeline = GenerationPipeline(
            llm=llm,
            default_temperature=0.1,
            default_max_tokens=100
        )
        
        messages = [
            {"role": "user", "content": "What is 5+5?"}
        ]
        
        response = await pipeline.generate(messages)
        
        assert response.content is not None
        assert "10" in response.content


@pytest.mark.asyncio
class TestPostprocessPipeline:
    """Test postprocessing pipeline."""
    
    async def test_linkify_citations(self):
        """Test citation linking."""
        pipeline = PostprocessPipeline()
        
        text = "According to [1], overtime pay is mandatory. See also [2]."
        citations = [
            {"id": 1, "source": "Labor Code", "url": "https://example.com/lc"},
            {"id": 2, "source": "DOLE Guidelines", "url": None}
        ]
        
        result = pipeline.linkify_citations(text, citations)
        
        assert "[[1]" in result  # Markdown link
        assert "**[2]**" in result  # Bold (no URL)
    
    async def test_add_disclaimer(self):
        """Test disclaimer addition."""
        pipeline = PostprocessPipeline(enable_auto_disclaimer=True)
        
        text = "This is a response."
        result = pipeline.add_disclaimer(text, "en")
        
        assert "Disclaimer" in result
        assert "legal advice" in result


@pytest.mark.asyncio
class TestConversationPipeline:
    """Test conversation pipeline."""
    
    async def test_conversation_flow(self):
        """Test full conversation flow."""
        memory = LangChainMemory(max_token_limit=4000)
        pipeline = ConversationPipeline(
            memory=memory,
            max_history_messages=10
        )
        
        session_id = "test_conv_789"
        
        # Add messages
        await pipeline.add_user_message(session_id, "Hello")
        await pipeline.add_assistant_message(session_id, "Hi! How can I help?")
        
        # Get context
        context = await pipeline.get_conversation_context(session_id)
        
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"
        
        # Get summary
        summary = await pipeline.get_conversation_summary(session_id)
        
        assert summary["total_messages"] == 2
        assert summary["user_messages"] == 1
        assert summary["assistant_messages"] == 1
