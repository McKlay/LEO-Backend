"""
Chat orchestration service.

Coordinates the full RAG pipeline for processing chat messages.
"""
import time
import uuid
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from datetime import datetime

from core import get_logger, AppError, settings
from services.pipeline.conversation import ConversationPipeline
from services.pipeline.query_analysis import QueryAnalysisPipeline
from services.pipeline.retrieval import RetrievalPipeline
from services.pipeline.grounding import GroundingPipeline
from services.pipeline.generation import GenerationPipeline
from services.pipeline.postprocess import PostprocessPipeline

if TYPE_CHECKING:
    from services.pipeline.query_analysis import QueryAnalysis

logger = get_logger(__name__)


class ChatOrchestrator:
    """
    Orchestrates the full chat pipeline.
    
    Coordinates conversation management, retrieval, grounding,
    generation, and post-processing for chat messages.
    """
    
    def __init__(
        self,
        conversation_pipeline: ConversationPipeline,
        query_analysis_pipeline: QueryAnalysisPipeline,
        retrieval_pipeline: RetrievalPipeline,
        grounding_pipeline: GroundingPipeline,
        generation_pipeline: GenerationPipeline,
        postprocess_pipeline: PostprocessPipeline
    ):
        """
        Initialize chat orchestrator.
        
        Args:
            conversation_pipeline: Conversation management pipeline
            query_analysis_pipeline: Query analysis with smart clarification
            retrieval_pipeline: Knowledge retrieval pipeline
            grounding_pipeline: Context grounding pipeline
            generation_pipeline: LLM generation pipeline
            postprocess_pipeline: Response post-processing pipeline
        """
        self.conversation = conversation_pipeline
        self.query_analysis = query_analysis_pipeline
        self.retrieval = retrieval_pipeline
        self.grounding = grounding_pipeline
        self.generation = generation_pipeline
        self.postprocess = postprocess_pipeline
        
        logger.info("Chat orchestrator initialized with smart query analysis")
    
    def _build_clarification_response(
        self,
        analysis: 'QueryAnalysis',
        language: str
    ) -> Dict[str, Any]:
        """
        Build clarification response from query analysis.
        
        Trusts the LLM-generated clarification question entirely, including
        its language. The LLM already handles preferred_language via its prompt.
        
        Args:
            analysis: Query analysis result with clarification data
            language: Response language (used for logging only)
            
        Returns:
            Dictionary with clarification content and suggestions
        """
        clarification_text = analysis.clarification_question

        logger.info(
            "Clarification response prepared: "
            f"requested_language={language}, detected_original={analysis.original_language}, "
            f"content_preview={repr((clarification_text or '')[:140])}"
        )
        
        suggestions = []
        if analysis.clarification_question:
            label = analysis.clarification_question
            suggestions.append({
                "id": "clarify-q1",
                "type": "query",
                "label": label[:60] + "..." if len(label) > 60 else label,
                "data": {"query": analysis.clarification_question}
            })
        
        return {
            "content": clarification_text,
            "suggestions": suggestions
        }
    
    async def process_message_stream(
        self,
        session_id: str,
        conversation_id: str,
        user_message: str,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Process a user message and stream the response via Server-Sent Events.
        
        Yields events with type and data for progressive UI updates:
        - metadata: Initial processing metadata (retrieval results)
        - content_chunk: Streaming response chunks
        - citations: Citation data
        - complete: Final complete message
        - error: Error information
        
        Args:
            session_id: User session identifier
            conversation_id: Conversation identifier
            user_message: User's message text
            language: Preferred response language (en, fil, ceb)
            context: Optional context information
            
        Yields:
            Dictionary events with 'type' and 'data' keys
            
        Raises:
            AppError: If processing fails
        """
        start_time = time.time()
        
        try:
            logger.info(
                f"Processing streaming message for session={session_id}, "
                f"conversation={conversation_id}, language={language}"
            )
            
            # Step 1: Get conversation history BEFORE adding current message
            # This ensures query analysis has context of PREVIOUS messages only
            conversation_history = await self.conversation.get_conversation_context(
                session_id=conversation_id,
                include_last_n=settings.max_conversation_history
            )
            
            # Step 2: Add user message to conversation history
            await self.conversation.add_user_message(
                session_id=conversation_id,
                content=user_message
            )
            
            # Step 3: Query analysis (Stage 1) — gated by enable_query_analysis
            analysis = None
            if settings.enable_query_analysis:
                logger.info("Analyzing query with conversation context")
                
                # Yield status event: Analyzing
                yield {
                    "type": "status",
                    "data": {
                        "step": "analyze",
                        "message": "Analyzing your query..."
                    }
                }
                
                analysis_start = time.time()
                
                analysis = await self.query_analysis.analyze(
                    query=user_message,
                    conversation_history=conversation_history,
                    preferred_language=language
                )
                
                analysis_time = time.time() - analysis_start
                
                logger.info(
                    f"Query analysis complete: "
                    f"needs_clarification={analysis.needs_clarification}, "
                    f"is_meta_conversational={analysis.is_meta_conversational}, "
                    f"concepts={analysis.legal_concepts}, "
                    f"articles={analysis.articles}, "
                    f"time={analysis_time:.3f}s"
                )

                # Emit analysis event with Stage 1 fields for benchmark tracing
                yield {
                    "type": "analysis",
                    "data": {
                        "normalized_query_en": analysis.normalized_query_en,
                        "original_language": analysis.original_language,
                        "needs_clarification": analysis.needs_clarification,
                        "clarification_question": analysis.clarification_question,
                        "is_meta_conversational": analysis.is_meta_conversational,
                        "out_of_scope": analysis.out_of_scope,
                        "legal_concepts": list(analysis.legal_concepts),
                        "keywords": list(analysis.keywords),
                        "articles_extracted": list(analysis.articles),
                        "analysis_time": round(analysis_time, 3),
                    }
                }

                # Step 4a: Check if query is out of scope (early exit)
                if analysis.out_of_scope:
                    logger.info("Query is out of scope for Philippine labor law")

                    out_of_scope_text = analysis.out_of_scope_message or (
                        "I'm LEO, your Philippine labor law assistant. "
                        "I can only help with labor law questions — feel free to ask about "
                        "wages, termination, benefits, DOLE, and more!"
                    )

                    await self.conversation.add_assistant_message(
                        session_id=conversation_id,
                        content=out_of_scope_text
                    )

                    processing_time = time.time() - start_time
                    message_id = str(uuid.uuid4())

                    yield {
                        "type": "complete",
                        "data": {
                            "message_id": message_id,
                            "conversation_id": conversation_id,
                            "role": "assistant",
                            "content": out_of_scope_text,
                            "timestamp": datetime.utcnow().isoformat(),
                            "citations": [],
                            "suggestions": [
                                {
                                    "id": "oos-wages",
                                    "type": "query",
                                    "label": "Ask about wages or overtime",
                                    "data": {"query": "What are my rights regarding overtime pay?"}
                                },
                                {
                                    "id": "oos-termination",
                                    "type": "query",
                                    "label": "Ask about termination",
                                    "data": {"query": "What are the valid grounds for termination?"}
                                },
                                {
                                    "id": "oos-dole",
                                    "type": "query",
                                    "label": "Ask about DOLE",
                                    "data": {"query": "How do I file a complaint with DOLE?"}
                                }
                            ],
                            "metadata": {
                                "processing_time": round(processing_time, 2),
                                "retrieval_time": 0.0,
                                "generation_time": 0.0,
                                "analysis_time": round(analysis_time, 3),
                                "model": settings.query_analysis_model,
                                "requested_language": language,
                                "analysis_original_language": analysis.original_language,
                                "confidence": 1.0,
                                "disclaimer_required": False,
                                "is_clarification": False,
                                "is_out_of_scope": True,
                                "tokens_used": 0
                            }
                        }
                    }
                    return

                # Step 4b: Check if clarification is needed (early exit)
                # Gated separately: enable_smart_clarification=False skips the gate but
                # preserves the enriched analysis (keywords/articles) for retrieval.
                if settings.enable_smart_clarification and analysis.needs_clarification:
                    logger.info("Clarification needed for current query")
                    
                    # Build clarification response with LLM-generated questions
                    clarification = self._build_clarification_response(
                        analysis=analysis,
                        language=language
                    )
                    
                    # Add clarification as assistant message
                    await self.conversation.add_assistant_message(
                        session_id=conversation_id,
                        content=clarification["content"]
                    )
                    
                    processing_time = time.time() - start_time
                    message_id = str(uuid.uuid4())
                    
                    # Yield complete clarification event
                    yield {
                        "type": "complete",
                        "data": {
                            "message_id": message_id,
                            "conversation_id": conversation_id,
                            "role": "assistant",
                            "content": clarification["content"],
                            "timestamp": datetime.utcnow().isoformat(),
                            "citations": [],
                            "suggestions": clarification.get("suggestions", []),
                            "metadata": {
                                "processing_time": round(processing_time, 2),
                                "retrieval_time": 0.0,  # No retrieval for clarification
                                "generation_time": round(analysis_time, 3),  # Query analysis time
                                "analysis_time": round(analysis_time, 3),
                                "model": settings.query_analysis_model,
                                "requested_language": language,
                                "analysis_original_language": analysis.original_language,
                                "confidence": 0.5,
                                "disclaimer_required": False,
                                "is_clarification": True,
                                "tokens_used": 0  # No LLM generation for clarification
                            }
                        }
                    }
                    return
            else:
                # Query analysis disabled (enable_query_analysis=False, e.g. "Stage 2 Only" variant):
                # skip Stage 1 entirely; retrieval uses raw user_message with no enrichment.
                logger.info("Query analysis disabled - proceeding with raw query retrieval")
            
            # Step 5: Retrieve relevant context (skipped for meta-conversational turns and LLM-only mode)
            if (analysis and analysis.is_meta_conversational) or settings.retrieval_mode == "none":
                if settings.retrieval_mode == "none":
                    logger.info("retrieval_mode=none — LLM-only baseline, skipping retrieval")
                else:
                    logger.info(
                        "Meta-conversational intent — skipping retrieval, "
                        "response will use conversation history only"
                    )
                retrieval_results = []
                retrieval_time = 0.0
                avg_score = 0.0
            else:
                logger.info("Retrieving context from knowledge base")

                # Yield status event: Retrieving
                yield {
                    "type": "status",
                    "data": {
                        "step": "retrieve",
                        "message": "Searching labor laws..."
                    }
                }

                retrieval_start = time.time()

                # When translation is disabled and the query is non-English, use the
                # original-language user_message so the ablation test is meaningful.
                # For English queries or when translation is enabled, always use the
                # LLM-normalized English query for better retrieval quality.
                _original_lang = analysis.original_language if analysis else "en"
                _translation_active = (
                    settings.enable_translation or _original_lang in ("en", "mixed", "")
                )
                retrieval_query = (
                    analysis.normalized_query_en
                    if (analysis and analysis.normalized_query_en and _translation_active)
                    else user_message
                )
                logger.info(
                    "Retrieval query trace: "
                    f"requested_language={language}, "
                    f"analysis_original_language={_original_lang}, "
                    f"translation_active={_translation_active}, "
                    f"query_preview={repr(retrieval_query[:140])}"
                )

                retrieval_results = await self.retrieval.retrieve(
                    query=retrieval_query,
                    keywords=analysis.keywords if analysis else None,
                    articles=analysis.articles if analysis else None,
                    top_k=settings.retrieval_top_k,
                    original_query=user_message
                )

                retrieval_time = time.time() - retrieval_start

                # Calculate average confidence score
                if retrieval_results:
                    avg_score = sum(r.score for r in retrieval_results) / len(retrieval_results)
                else:
                    avg_score = 0.0

                logger.info(
                    f"Retrieved {len(retrieval_results)} results "
                    f"(retrieval_time={retrieval_time:.3f}s, avg_score={avg_score:.3f})"
                )

            # Yield metadata event (always — retrieval_time=0 for meta-conversational turns)
            yield {
                "type": "metadata",
                "data": {
                    "retrieval_time": round(retrieval_time, 3),
                    "retrieval_count": len(retrieval_results),
                    "avg_confidence": round(avg_score, 3),
                    "retrieved_chunk_ids": [
                        (r.metadata or {}).get("chunk_id", r.id)
                        for r in retrieval_results
                    ],
                }
            }
            
            # Step 6: Build grounded prompt with rich context
            logger.info("Building grounded prompt")
            messages = self.grounding.build_grounded_prompt(
                query=user_message,
                context_results=retrieval_results,
                language=language,
                conversation_history=conversation_history[-6:]  # Last 3 exchanges only
            )
            
            # Step 7: Stream LLM response generation
            logger.info("Starting streaming LLM generation")
            
            # Yield status event: Generating
            yield {
                "type": "status",
                "data": {
                    "step": "generate",
                    "message": "Formulating response..."
                }
            }
            
            generation_start = time.time()
            
            full_content = []
            async for chunk in self.generation.generate_stream(
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            ):
                full_content.append(chunk)
                
                # Yield content chunk event
                yield {
                    "type": "content_chunk",
                    "data": {"chunk": chunk}
                }
            
            generation_time = time.time() - generation_start
            complete_content = "".join(full_content)
            
            logger.info(
                f"Streaming generation complete "
                f"(generation_time={generation_time:.3f}s, chunks={len(full_content)})"
            )
            
            # Step 8: Extract citations from retrieval results
            citations_data = self.grounding.extract_citation_metadata(
                results=retrieval_results
            )
            
            # Yield citations event
            yield {
                "type": "citations",
                "data": {"citations": citations_data}
            }
            
            # Step 9: Post-process response
            logger.info("Post-processing response")
            processed_result = self.postprocess.process_response(
                response=complete_content,
                citations=citations_data,
                language=language,
                add_disclaimer=settings.enable_auto_disclaimer
            )
            
            # Step 10: Add assistant message to conversation history
            await self.conversation.add_assistant_message(
                session_id=conversation_id,
                content=processed_result["content"]
            )
            
            processing_time = time.time() - start_time
            message_id = str(uuid.uuid4())
            
            # Step 11: Yield complete message event
            yield {
                "type": "complete",
                "data": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": processed_result["content"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "citations": citations_data,
                    "suggestions": [],  # TODO: Add suggested actions in Phase 4
                    "metadata": {
                        "processing_time": round(processing_time, 2),
                        "retrieval_time": round(retrieval_time, 3),
                        "generation_time": round(generation_time, 3),
                        "model": settings.openai_llm_model,
                        "confidence": round(avg_score, 3),
                        "disclaimer_required": processed_result.get("has_disclaimer", False),
                        "is_clarification": False,
                        "is_meta_conversational": analysis.is_meta_conversational if analysis else False
                    }
                }
            }
            
            logger.info(
                f"Streaming message processed successfully in {processing_time:.2f}s "
                f"(retrieval={retrieval_time:.3f}s, generation={generation_time:.3f}s, "
                f"{len(citations_data)} citations)"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Error in streaming message processing: {str(e)} "
                f"(after {processing_time:.2f}s)",
                exc_info=True
            )
            
            # Yield error event
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "error_code": "STREAMING_ERROR",
                    "processing_time": round(processing_time, 2)
                }
            }
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            conversation_id: Conversation to clear
        """
        await self.conversation.clear_conversation(session_id=conversation_id)
        logger.info(f"Cleared conversation: {conversation_id}")
