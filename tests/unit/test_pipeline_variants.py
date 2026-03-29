"""
Task 8 — Pipeline Variant Unit Tests

Tests ChatOrchestrator behavior for the three Stage 1 ablation variants
defined in the thesis evaluation framework (§4.5.3).

Variants covered:
  A. Hybrid – No Translation  (enable_translation=False)
     Non-English query → retrieval uses original user_message, NOT the
     LLM-normalized English form. Stage 1 (analysis + clarification) still runs.

  B. Hybrid – No Clarification  (enable_smart_clarification=False)
     Ambiguous query (needs_clarification=True) → pipeline skips clarification
     early exit and proceeds normally to retrieval + generation.

  C. Stage 2 Only  (enable_query_analysis=False)
     Entire Stage 1 is bypassed: analyze() never called, raw user_message
     forwarded to retrieval with no keyword/article enrichment.

All tests are fully offline — no live DB, API keys, or server required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.chat_orchestrator import ChatOrchestrator
from services.pipeline.query_analysis import QueryAnalysis
from adapters.vectorstore.base import QueryResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _collect(gen) -> list:
    """Drain an async generator and return all yielded items."""
    items = []
    async for item in gen:
        items.append(item)
    return items


def _make_query_result(doc_id: str = "r1", score: float = 0.8) -> QueryResult:
    return QueryResult(
        id=doc_id,
        content="Relevant legal text",
        metadata={"_strategy": "dense"},
        score=score,
    )


def _make_analysis(
    needs_clarification: bool = False,
    original_language: str = "en",
    normalized_query_en: str = "termination by employer",
    is_meta_conversational: bool = False,
) -> QueryAnalysis:
    return QueryAnalysis(
        needs_clarification=needs_clarification,
        clarification_question="What kind of termination?" if needs_clarification else None,
        original_language=original_language,
        normalized_query_en=normalized_query_en,
        legal_concepts=["termination"],
        articles=["Article 297"],
        keywords=["termination", "employer"],
        out_of_scope=False,
        is_meta_conversational=is_meta_conversational,
    )


async def _mock_stream(*args, **kwargs):
    """Async generator stub for LLM streaming generation."""
    yield "Employers may "
    yield "terminate employees for just causes."


def _base_settings_patches(monkeypatch, settings, **overrides):
    """Apply a common base set of settings patches, then apply overrides."""
    base = {
        "enable_query_analysis": True,
        "enable_smart_clarification": True,
        "enable_translation": True,
        "retrieval_mode": "hybrid",
        "retrieval_top_k": 5,
        "max_conversation_history": 10,
        "enable_auto_disclaimer": False,
    }
    base.update(overrides)
    for key, val in base.items():
        monkeypatch.setattr(settings, key, val)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pipelines():
    """Fully-mocked pipeline components wired to the orchestrator."""
    conversation = AsyncMock()
    conversation.get_conversation_context.return_value = []
    conversation.add_user_message.return_value = None
    conversation.add_assistant_message.return_value = None

    query_analysis = AsyncMock()
    query_analysis.analyze.return_value = _make_analysis()

    retrieval = AsyncMock()
    retrieval.retrieve.return_value = [_make_query_result()]

    grounding = MagicMock()
    grounding.build_grounded_prompt.return_value = [
        {"role": "system", "content": "You are LEO..."},
        {"role": "user", "content": "Query"},
    ]
    grounding.extract_citation_metadata.return_value = []

    generation = MagicMock()
    generation.generate_stream = _mock_stream

    postprocess = MagicMock()
    postprocess.process_response.return_value = {
        "content": "Final answer.",
        "has_disclaimer": False,
        "citation_count": 0,
        "redaction_count": 0,
    }

    return {
        "conversation": conversation,
        "query_analysis": query_analysis,
        "retrieval": retrieval,
        "grounding": grounding,
        "generation": generation,
        "postprocess": postprocess,
    }


@pytest.fixture
def orchestrator(mock_pipelines):
    """Create orchestrator wired to all mocked pipelines."""
    return ChatOrchestrator(
        conversation_pipeline=mock_pipelines["conversation"],
        query_analysis_pipeline=mock_pipelines["query_analysis"],
        retrieval_pipeline=mock_pipelines["retrieval"],
        grounding_pipeline=mock_pipelines["grounding"],
        generation_pipeline=mock_pipelines["generation"],
        postprocess_pipeline=mock_pipelines["postprocess"],
    )


# ---------------------------------------------------------------------------
# A. Hybrid – No Translation  (enable_translation=False)
# ---------------------------------------------------------------------------

class TestHybridNoTranslation:
    """
    Variant: enable_translation=False

    Stage 1 runs fully (analysis + clarification gate), but when the query
    is non-English the retrieval query must fall back to the raw user_message
    rather than the LLM-normalized English form.
    """

    @pytest.mark.asyncio
    async def test_non_english_query_uses_raw_message_for_retrieval(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """Non-English query + translation=False → retrieval called with original user_message."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_translation=False)

        # Analysis reports Filipino origin with English normalisation
        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            needs_clarification=False,
            original_language="fil",
            normalized_query_en="termination by employer",
        )

        filipino_query = "Ano ang mga dahilan ng pagtanggal sa trabaho?"

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message=filipino_query,
                language="fil",
            )
        )

        # Stage 1 must have run
        mock_pipelines["query_analysis"].analyze.assert_called_once()

        # Retrieval must use the original Filipino message (translation inactive)
        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        assert retrieve_call is not None, "retrieval.retrieve() was not called"
        retrieval_query_used = retrieve_call.kwargs.get("query") or retrieve_call.args[0]

        assert retrieval_query_used == filipino_query, (
            f"Expected retrieval with raw user_message '{filipino_query}', "
            f"got '{retrieval_query_used}'"
        )

        # Pipeline completes normally (no clarification early-exit)
        event_types = [e["type"] for e in events]
        assert "complete" in event_types
        complete_evt = next(e for e in events if e["type"] == "complete")
        assert complete_evt["data"]["metadata"]["is_clarification"] is False

    @pytest.mark.asyncio
    async def test_english_query_still_uses_normalized_form(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        English query with translation=False → normalized_query_en is still used,
        because the original language IS English (translation_active=True when lang is 'en').
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_translation=False)

        normalized = "overtime pay computation"
        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            original_language="en",
            normalized_query_en=normalized,
        )

        english_query = "How is overtime pay calculated?"

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message=english_query,
                language="en",
            )
        )

        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        retrieval_query_used = retrieve_call.kwargs.get("query") or retrieve_call.args[0]

        assert retrieval_query_used == normalized, (
            f"English original should use normalized_query_en '{normalized}', "
            f"got '{retrieval_query_used}'"
        )

    @pytest.mark.asyncio
    async def test_cebuano_query_uses_raw_message(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """Cebuano query + translation=False → retrieval uses the Cebuano user_message."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_translation=False)

        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            original_language="ceb",
            normalized_query_en="minimum wage rate",
        )

        cebuano_query = "Pila ang minimum nga suweldo sa Pilipinas?"

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message=cebuano_query,
                language="ceb",
            )
        )

        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        retrieval_query_used = retrieve_call.kwargs.get("query") or retrieve_call.args[0]

        assert retrieval_query_used == cebuano_query, (
            f"Cebuano query must be passed raw to retrieval when translation is off, "
            f"got '{retrieval_query_used}'"
        )


# ---------------------------------------------------------------------------
# B. Hybrid – No Clarification  (enable_smart_clarification=False)
# ---------------------------------------------------------------------------

class TestHybridNoClarification:
    """
    Variant: enable_smart_clarification=False

    Stage 1 runs (query analysis enriches retrieval), but even when
    needs_clarification=True the pipeline must skip the clarification
    early-exit and proceed to retrieval + generation.
    """

    @pytest.mark.asyncio
    async def test_ambiguous_query_proceeds_to_retrieval(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        Ambiguous query (needs_clarification=True) + clarification disabled
        → retrieval.retrieve() IS called (no early exit).
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_smart_clarification=False)

        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            needs_clarification=True,
            original_language="en",
            normalized_query_en="employee rights",
        )

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="What about my rights?",
                language="en",
            )
        )

        # Stage 1 must have run
        mock_pipelines["query_analysis"].analyze.assert_called_once()

        # Retrieval must still be called — no early exit
        mock_pipelines["retrieval"].retrieve.assert_called_once()

        # Pipeline produces a final answer (not a clarification)
        event_types = [e["type"] for e in events]
        assert "complete" in event_types, "Pipeline must yield a complete event"

    @pytest.mark.asyncio
    async def test_no_clarification_complete_event_emitted(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        With clarification disabled, the complete event must NOT carry
        is_clarification=True regardless of analysis.needs_clarification.
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_smart_clarification=False)

        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            needs_clarification=True,
        )

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="What about my rights?",
                language="en",
            )
        )

        complete_events = [e for e in events if e["type"] == "complete"]
        assert complete_events, "Expected at least one complete event"
        for evt in complete_events:
            is_clarif = evt["data"].get("metadata", {}).get("is_clarification")
            assert is_clarif is not True, (
                "is_clarification must be False when enable_smart_clarification=False"
            )

    @pytest.mark.asyncio
    async def test_analysis_keywords_forwarded_to_retrieval(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        Clarification disabled → analysis keywords and articles still
        flow through to retrieval.retrieve() as enrichment signals.
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_smart_clarification=False)

        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            needs_clarification=True,
            normalized_query_en="termination by employer",
        )

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="my termination",
                language="en",
            )
        )

        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        assert retrieve_call is not None

        keywords = retrieve_call.kwargs.get("keywords")
        articles = retrieve_call.kwargs.get("articles")

        assert keywords == ["termination", "employer"], (
            "Analysis keywords must be forwarded to retrieval even when "
            f"clarification is disabled. Got: {keywords}"
        )
        assert articles == ["Article 297"], (
            f"Analysis articles must be forwarded to retrieval. Got: {articles}"
        )

    @pytest.mark.asyncio
    async def test_generation_receives_grounded_messages(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        With clarification disabled, the grounding pipeline is called and
        generation produces content_chunk events.
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_smart_clarification=False)

        mock_pipelines["query_analysis"].analyze.return_value = _make_analysis(
            needs_clarification=True,
        )

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="Vague question",
                language="en",
            )
        )

        # Grounding must be called
        mock_pipelines["grounding"].build_grounded_prompt.assert_called_once()

        # content_chunk events should be emitted
        chunk_events = [e for e in events if e["type"] == "content_chunk"]
        assert len(chunk_events) > 0, "Expected content_chunk events from generation"


# ---------------------------------------------------------------------------
# C. Stage 2 Only — Query Analysis Disabled  (enable_query_analysis=False)
# ---------------------------------------------------------------------------

class TestStage2Only:
    """
    Variant: enable_query_analysis=False

    The entire Stage 1 (query analysis) is bypassed. Retrieval must use
    the raw user_message with no keyword/article enrichment from Stage 1.
    """

    @pytest.mark.asyncio
    async def test_query_analysis_not_called(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """enable_query_analysis=False → analyze() is never invoked."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="What is overtime pay?",
                language="en",
            )
        )

        mock_pipelines["query_analysis"].analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieval_uses_raw_user_message(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """enable_query_analysis=False → retrieval called with unmodified user_message."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        raw_query = "What is the minimum wage in the Philippines?"

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message=raw_query,
                language="en",
            )
        )

        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        assert retrieve_call is not None, "retrieval.retrieve() must be called"
        retrieval_query_used = retrieve_call.kwargs.get("query") or retrieve_call.args[0]

        assert retrieval_query_used == raw_query, (
            f"Expected retrieval with raw user_message '{raw_query}', "
            f"got '{retrieval_query_used}'"
        )

    @pytest.mark.asyncio
    async def test_no_keywords_or_articles_passed_to_retrieval(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """enable_query_analysis=False → keywords and articles are None (no enrichment)."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="What is overtime pay?",
                language="en",
            )
        )

        retrieve_call = mock_pipelines["retrieval"].retrieve.call_args
        keywords = retrieve_call.kwargs.get("keywords")
        articles = retrieve_call.kwargs.get("articles")

        assert keywords is None, (
            f"No keywords should be passed when Stage 1 is disabled, got {keywords}"
        )
        assert articles is None, (
            f"No articles should be passed when Stage 1 is disabled, got {articles}"
        )

    @pytest.mark.asyncio
    async def test_pipeline_completes_with_generated_answer(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """enable_query_analysis=False → pipeline still yields a complete event with content."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="What is overtime pay?",
                language="en",
            )
        )

        event_types = [e["type"] for e in events]
        assert "complete" in event_types, "Pipeline must yield a complete event"

        complete_evt = next(e for e in events if e["type"] == "complete")
        assert complete_evt["data"]["content"], "Complete event must have non-empty content"

    @pytest.mark.asyncio
    async def test_retrieval_is_still_called(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """
        Stage 2 Only: retrieval runs even without Stage 1 enrichment.
        This confirms Stage 2 (hybrid retrieval) is still active.
        """
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="Termination rights of employees",
                language="en",
            )
        )

        mock_pipelines["retrieval"].retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_chunk_events_emitted(
        self, orchestrator, mock_pipelines, monkeypatch
    ):
        """Stage 2 Only: generation still streams content_chunk events."""
        from core import settings

        _base_settings_patches(monkeypatch, settings, enable_query_analysis=False)

        events = await _collect(
            orchestrator.process_message_stream(
                session_id="sess-1",
                conversation_id="conv-1",
                user_message="Back pay rules",
                language="en",
            )
        )

        chunk_events = [e for e in events if e["type"] == "content_chunk"]
        assert len(chunk_events) > 0, "Expected streaming content_chunk events"
