"""
Unit tests for query analysis pipeline.

Tests smart clarification detection, concept extraction, article parsing,
and context awareness.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
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
    monkeypatch.setattr(settings, "max_clarification_questions", 4)
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
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Query is too vague", '
                    '"clarification_questions": ["Are you asking about termination?", "Are you asking about wages?"], '
                    '"suggested_topics": ["Termination", "Wages", "Benefits"], '
                    '"legal_concepts": [], "articles": [], "keywords": ["rights"], '
                    '"query_type": "general", "breadth": "broad"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert result.clarification_reason is not None
        assert len(result.clarification_questions) >= 2
        assert len(result.suggested_topics) >= 2
    
    @pytest.mark.asyncio
    async def test_clear_query_no_clarification(self, analysis_pipeline, mock_llm):
        """Test that clear query doesn't need clarification."""
        query = "What is 13th month pay?"
        
        # Mock LLM response
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": false, '
                    '"legal_concepts": ["13th month pay", "employee benefits"], '
                    '"articles": [], "keywords": ["13th", "month", "pay"], '
                    '"query_type": "specific", "breadth": "narrow"}',
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
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Ambiguous pronouns", '
                    '"clarification_questions": ["Who is \'they\'?", "What action are they taking?"], '
                    '"suggested_topics": ["Termination", "Harassment", "Demotion"], '
                    '"legal_concepts": [], "articles": [], "keywords": [], '
                    '"query_type": "general", "breadth": "broad"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert len(result.clarification_questions) >= 2


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
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": false, '
                    '"legal_concepts": ["13th month pay", "calculation"], '
                    '"articles": [], "keywords": ["calculated", "computation"], '
                    '"query_type": "procedural", "breadth": "narrow"}',
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
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Too broad", '
                    '"clarification_questions": ["Are you asking about overtime pay rates?", '
                    '"Are you asking about overtime work hours?"], '
                    '"suggested_topics": ["Overtime Pay", "Overtime Hours", "Night Differential"], '
                    '"legal_concepts": ["overtime"], "articles": [], "keywords": ["overtime"], '
                    '"query_type": "general", "breadth": "broad"}',
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
        
        query = "What does Article 123 say?"
        result = await analysis_pipeline.analyze(query)
        
        assert "Article 123" in result.articles
    
    @pytest.mark.asyncio
    async def test_fallback_extracts_keywords(self, analysis_pipeline, mock_llm, monkeypatch):
        """Test that fallback extracts basic keywords."""
        from core import settings
        monkeypatch.setattr(settings, "enable_query_analysis", False)
        
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
        
        mock_llm.generate = slow_generate
        
        result = await analysis_pipeline.analyze(query)
        
        # Should return fallback result
        assert isinstance(result, QueryAnalysis)
        assert result.needs_clarification in [True, False]  # Any valid response


class TestClarificationQuestionQuality:
    """Test quality of generated clarification questions."""
    
    @pytest.mark.asyncio
    async def test_specific_questions_not_generic(self, analysis_pipeline, mock_llm):
        """Test that clarification questions are specific, not generic."""
        query = "I have a problem"
        
        # Mock LLM response with specific questions
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Too vague", '
                    '"clarification_questions": ['
                    '"Is this about termination or dismissal?", '
                    '"Is this about wages or benefits?", '
                    '"Is this about working conditions or harassment?"'
                    '], '
                    '"suggested_topics": ["Termination", "Wages", "Working Conditions"], '
                    '"legal_concepts": [], "articles": [], "keywords": [], '
                    '"query_type": "general", "breadth": "broad"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        # Check that questions are specific
        assert result.needs_clarification is True
        assert len(result.clarification_questions) >= 3
        
        # Questions should be specific (contain actual topics)
        for question in result.clarification_questions:
            assert len(question) > 20  # Not too short
            # Should not be generic like "Please clarify"
            assert "please clarify" not in question.lower()
    
    @pytest.mark.asyncio
    async def test_suggested_topics_provided(self, analysis_pipeline, mock_llm):
        """Test that suggested topics are provided for multi-choice clarification."""
        query = "What are my rights?"
        
        # Mock LLM response
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Too broad", '
                    '"clarification_questions": ["What specific right?"], '
                    '"suggested_topics": ["Termination Rights", "Wage Rights", "Leave Benefits", "Safety Rights"], '
                    '"legal_concepts": [], "articles": [], "keywords": ["rights"], '
                    '"query_type": "general", "breadth": "broad"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        assert result.needs_clarification is True
        assert len(result.suggested_topics) >= 3
        # Topics should be specific labor law topics
        assert all(len(topic) > 5 for topic in result.suggested_topics)
    
    @pytest.mark.asyncio
    async def test_max_clarification_questions_limit(self, analysis_pipeline, mock_llm):
        """Test that clarification questions are limited to max setting."""
        query = "Tell me about labor law"
        
        # Mock LLM response with many questions
        mock_llm.generate.return_value = LLMResponse(
            content='{"needs_clarification": true, "clarification_reason": "Too broad", '
                    '"clarification_questions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?", "Q6?", "Q7?"], '
                    '"suggested_topics": ["T1", "T2"], '
                    '"legal_concepts": [], "articles": [], "keywords": [], '
                    '"query_type": "general", "breadth": "broad"}',
            model="gpt-4o-mini",
            tokens_used=100
        )
        
        result = await analysis_pipeline.analyze(query)
        
        # Should be limited to max_clarification_questions (4 by default)
        assert len(result.clarification_questions) <= 4
