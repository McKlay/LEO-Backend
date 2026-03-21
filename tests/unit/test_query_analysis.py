"""
Unit tests for query analysis pipeline.

Tests smart clarification detection, concept extraction, article parsing,
and context awareness.
"""
import pytest
from unittest.mock import AsyncMock
from services.pipeline.query_analysis import QueryAnalysisPipeline, QueryAnalysis
from adapters.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    """Mock LLM adapter for testing."""
    llm = AsyncMock()
    return llm


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    from core import settings
    monkeypatch.setattr(settings, "enable_query_analysis", True)
    monkeypatch.setattr(settings, "enable_smart_clarification", True)
    monkeypatch.setattr(settings, "query_analysis_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "analysis_timeout", 3.0)
    return settings


@pytest.fixture
def analysis_pipeline(mock_llm, mock_settings):
    """Create query analysis pipeline instance."""
    return QueryAnalysisPipeline(llm=mock_llm)


class TestArticleExtraction:
    """Test article number extraction using regex."""
    
    @pytest.mark.asyncio
    async def test_extract_article_number(self, analysis_pipeline):
        """Test extraction of 'Article 123' format."""
        query = "What does Article 123 say about overtime?"
        articles = analysis_pipeline._extract_articles_regex(query)
        assert "Article 123" in articles
    
    @pytest.mark.asyncio
    async def test_extract_art_abbreviation(self, analysis_pipeline):
        """Test extraction of 'Art. 123' format."""
        query = "Art. 97 states something about wages"
        articles = analysis_pipeline._extract_articles_regex(query)
        assert "Article 97" in articles
    
    @pytest.mark.asyncio
    async def test_extract_presidential_decree(self, analysis_pipeline):
        """Test extraction of 'PD 442' format."""
        query = "PD 442 is the Labor Code"
        articles = analysis_pipeline._extract_articles_regex(query)
        assert "PD 442" in articles
    
    @pytest.mark.asyncio
    async def test_extract_republic_act(self, analysis_pipeline):
        """Test extraction of 'RA 10361' format."""
        query = "RA 10361 covers domestic workers"
        articles = analysis_pipeline._extract_articles_regex(query)
        assert "RA 10361" in articles
    
    @pytest.mark.asyncio
    async def test_extract_multiple_articles(self, analysis_pipeline):
        """Test extraction of multiple article references."""
        query = "Compare Article 123 and PD 442"
        articles = analysis_pipeline._extract_articles_regex(query)
        assert len(articles) == 2
        assert "Article 123" in articles
        assert "PD 442" in articles


class TestSmartClarificationDetection:
    """Test smart clarification detection with LLM."""
    
    @pytest.mark.asyncio
    async def test_vague_query_needs_clarification(self, analysis_pipeline, mock_llm):
        """Test that vague query triggers clarification."""
        query = "What about my rights?"
        
        # Mock LLM response
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"clarification_question": "What specific labor right are you asking about?", '
                    '"legal_concepts": [], "articles": [], "keywords": ["rights"], '
                    '"normalized_query_en": "employee rights philippines"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert result.clarification_question is not None
    
    @pytest.mark.asyncio
    async def test_clear_query_no_clarification(self, analysis_pipeline, mock_llm):
        """Test that clear query doesn't need clarification."""
        query = "What is 13th month pay?"
        
        # Mock LLM response
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": false, '
                    '"legal_concepts": ["13th month pay", "employee benefits"], '
                    '"articles": [], "keywords": ["13th", "month", "pay"]}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is False
        assert len(result.legal_concepts) >= 1
        assert len(result.keywords) >= 1
    
    @pytest.mark.asyncio
    async def test_ambiguous_pronoun_needs_clarification(self, analysis_pipeline, mock_llm):
        """Test that query with ambiguous pronouns needs clarification."""
        query = "Can they do this to me?"
        
        # Mock LLM response
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"clarification_question": "Who is \'they\' and what action did they take?", '
                    '"legal_concepts": [], "articles": [], "keywords": []}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert result.clarification_question is not None


class TestContextAwareness:
    """Test context-aware query analysis using conversation history."""
    
    @pytest.mark.asyncio
    async def test_followup_with_context_no_clarification(self, analysis_pipeline, mock_llm):
        """Test that follow-up question with clear context doesn't need clarification."""
        query = "How is it calculated?"
        conversation_history = [
            {"role": "user", "content": "What is 13th month pay?"},
            {"role": "assistant", "content": "13th month pay is..."}
        ]
        
        # Mock LLM response (should understand context)
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": false, '
                    '"legal_concepts": ["13th month pay", "calculation"], '
                    '"articles": [], "keywords": ["calculated", "computation"]}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query, conversation_history)
        
        assert result.needs_clarification is False
        assert "calculation" in result.legal_concepts or "computation" in result.keywords
    
    @pytest.mark.asyncio
    async def test_vague_first_query_needs_clarification(self, analysis_pipeline, mock_llm):
        """Test that vague first query needs clarification even with no history."""
        query = "What about overtime?"
        conversation_history = []
        
        # Mock LLM response
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"clarification_question": "Are you asking about overtime pay rates or overtime work hours?", '
                    '"legal_concepts": ["overtime"], "articles": [], "keywords": ["overtime"]}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query, conversation_history)
        
        assert result.needs_clarification is True


class TestFallbackAnalysis:
    """Test fallback analysis when LLM is disabled or fails."""
    
    @pytest.mark.asyncio
    async def test_fallback_extracts_articles(self, analysis_pipeline, mock_llm, monkeypatch):
        """Test that fallback still extracts articles using regex."""
        from core import settings
        monkeypatch.setattr(settings, "enable_query_analysis", False)
        analysis_pipeline.enabled = False
        
        query = "What does Article 123 say?"
        result = await analysis_pipeline.analyze(query)
        
        assert "Article 123" in result.articles
    
    @pytest.mark.asyncio
    async def test_fallback_extracts_keywords(self, analysis_pipeline, mock_llm, monkeypatch):
        """Test that fallback extracts basic keywords."""
        from core import settings
        monkeypatch.setattr(settings, "enable_query_analysis", False)
        analysis_pipeline.enabled = False
        
        query = "What is overtime pay calculation?"
        result = await analysis_pipeline.analyze(query)
        
        assert len(result.keywords) > 0
        assert any(kw in ["overtime", "calculation"] for kw in result.keywords)
    
    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, analysis_pipeline, mock_llm):
        """Test fallback when LLM times out."""
        import asyncio
        
        query = "What is 13th month pay?"
        
        # Mock LLM to timeout
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(5)  # Longer than timeout
            return LLMResponse(content='{}', model="gpt-4o-mini", tokens_used=0)
        
        mock_llm.analyze_query = slow_generate
        
        result = await analysis_pipeline.analyze(query)
        
        # Should return fallback result
        assert isinstance(result, QueryAnalysis)
        assert result.needs_clarification in [True, False]  # Any valid response


class TestClarificationQuestionQuality:
    """Test quality of generated single clarification question."""
    
    @pytest.mark.asyncio
    async def test_specific_questions_not_generic(self, analysis_pipeline, mock_llm):
        """Test that clarification questions are specific, not generic."""
        query = "I have a problem"
        
        # Mock LLM response with specific question
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                '"clarification_question": "Is your concern about termination, wages, or working conditions?", '
                '"legal_concepts": [], "articles": [], "keywords": []}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        # Check that questions are specific
        assert result.needs_clarification is True
        assert result.clarification_question is not None
        assert len(result.clarification_question) > 20
        assert "please clarify" not in result.clarification_question.lower()
    
    @pytest.mark.asyncio
    async def test_single_question_used_when_present(self, analysis_pipeline, mock_llm):
        """Test that single clarification question is preserved."""
        query = "What are my rights?"
        
        # Mock LLM response
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"clarification_question": "Are you asking about wage rights, termination rights, or leave benefits?", '
                    '"legal_concepts": [], "articles": [], "keywords": ["rights"]}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert result.clarification_question is not None
        assert "rights" in result.clarification_question.lower() or "wage" in result.clarification_question.lower()
    
    @pytest.mark.asyncio
    async def test_default_question_backfilled_when_missing(self, analysis_pipeline, mock_llm):
        """Test default clarification question fallback when model omits it."""
        query = "Tell me about labor law"
        
        # Mock LLM response without clarification question
        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"legal_concepts": [], "articles": [], "keywords": []}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert result.clarification_question is not None


class TestStage1ContractAlignment:
    """Test alignment with Stage 1 structured output contract."""

    @pytest.mark.asyncio
    async def test_normalized_query_fallback_to_original_query(self, analysis_pipeline, mock_llm):
        """If LLM omits normalized_query_en, pipeline should fallback to original query."""
        query = "Magkano ang minimum wage sa NCR ngayon?"

        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": false, "keywords": ["minimum wage", "NCR"]}',
            model="gpt-4o-mini",
            tokens_used=50
        )

        result = await analysis_pipeline.analyze(query)

        assert result.normalized_query_en == query

    @pytest.mark.asyncio
    async def test_single_clarification_question_kept(self, analysis_pipeline, mock_llm):
        """Single clarification_question should be used as-is."""
        query = "What's the minimum wage?"

        mock_llm.analyze_query.return_value = LLMResponse(
            content='{"needs_clarification": true, '
                    '"clarification_question": "Could you specify your region?", '
                    '"normalized_query_en": "minimum wage philippines by region", '
                    '"keywords": ["minimum wage", "region"]}',
            model="gpt-4o-mini",
            tokens_used=80
        )

        result = await analysis_pipeline.analyze(query)

        assert result.needs_clarification is True
        assert result.clarification_question == "Could you specify your region?"
