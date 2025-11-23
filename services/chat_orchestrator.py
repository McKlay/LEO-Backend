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
        
        Uses LLM-generated clarification questions and suggested topics
        for a more helpful, specific clarification experience.
        
        Args:
            analysis: Query analysis result with clarification data
            language: Response language
            
        Returns:
            Dictionary with clarification content and suggestions
        """
        # Build clarification message
        clarification_parts = []
        
        # Opening (language-aware)
        if language == "fil":
            clarification_parts.append(
                "Salamat sa iyong tanong! Upang makapagbigay ako ng mas tumpak na sagot, "
                "maaari mo bang linawin ang iyong katanungan?"
            )
        elif language == "ceb":
            clarification_parts.append(
                "Salamat sa imong pangutana! Aron makahatag kog mas tukma nga tubag, "
                "mahimo ba nimong klaruhon ang imong pangutana?"
            )
        else:  # English
            clarification_parts.append(
                "Thank you for your question! To provide you with the most accurate answer, "
                "could you please clarify your question?"
            )
        
        # Add reason for clarification
        if analysis.clarification_reason:
            if language == "fil":
                clarification_parts.append(f"\n\n**Dahilan**: {analysis.clarification_reason}")
            elif language == "ceb":
                clarification_parts.append(f"\n\n**Hinungdan**: {analysis.clarification_reason}")
            else:
                clarification_parts.append(f"\n\n**Why**: {analysis.clarification_reason}")
        
        # Add specific follow-up questions
        if analysis.clarification_questions:
            if language == "fil":
                clarification_parts.append("\n\n**Halimbawa ng mga tanong na maaari mong itanong**:")
            elif language == "ceb":
                clarification_parts.append("\n\n**Mga pananglitan sa pangutana nga mahimo nimong ipangutana**:")
            else:
                clarification_parts.append("\n\n**Here are some specific questions you might ask**:")
            
            for i, question in enumerate(analysis.clarification_questions[:4], 1):
                clarification_parts.append(f"\n\n{i}. {question}")
        
        # Add suggested topics
        if analysis.suggested_topics:
            if language == "fil":
                clarification_parts.append("\n\n**O pumili mula sa mga karaniwang paksa**:")
            elif language == "ceb":
                clarification_parts.append("\n\n**O pagpili gikan sa mga kasagarang tema**:")
            else:
                clarification_parts.append("\n\n**Or choose from these common topics**:")
            
            for topic in analysis.suggested_topics[:5]:
                clarification_parts.append(f"\n\n• {topic}")
        
        clarification_text = "".join(clarification_parts)
        
        # Build suggestions for API response
        suggestions = []
        if analysis.clarification_questions:
            for i, question in enumerate(analysis.clarification_questions[:4], 1):
                suggestions.append({
                    "id": f"clarify-q{i}",
                    "type": "query",
                    "label": question[:60] + "..." if len(question) > 60 else question,
                    "data": {"query": question}
                })
        
        # Add topic-based suggestions
        if analysis.suggested_topics:
            topic_queries = {
                "fil": {
                    "overtime pay": "Ano ang aking karapatan sa overtime pay?",
                    "termination": "Ano ang aking karapatan kung ako ay tinanggal?",
                    "13th month pay": "Ano ang 13th month pay at sino ang karapat-dapat?",
                    "maternity leave": "Ano ang maternity leave benefits ko?",
                    "minimum wage": "Ano ang minimum wage sa aking rehiyon?"
                },
                "ceb": {
                    "overtime pay": "Unsa ang akong katungod sa overtime pay?",
                    "termination": "Unsa ang akong katungod kon ako gitagal?",
                    "13th month pay": "Unsa ang 13th month pay ug kinsa ang takos?",
                    "maternity leave": "Unsa ang akong maternity leave benefits?",
                    "minimum wage": "Unsa ang minimum wage sa akong rehiyon?"
                },
                "en": {
                    "overtime pay": "What are my rights regarding overtime pay?",
                    "termination": "What are my rights if I am terminated?",
                    "13th month pay": "What is 13th month pay and who is eligible?",
                    "maternity leave": "What are my maternity leave benefits?",
                    "minimum wage": "What is the minimum wage in my region?"
                }
            }
            
            lang_queries = topic_queries.get(language, topic_queries["en"])
            
            for topic in analysis.suggested_topics[:3]:
                topic_lower = topic.lower()
                query = None
                
                # Try to match topic to predefined query
                for key, predefined_query in lang_queries.items():
                    if key in topic_lower:
                        query = predefined_query
                        break
                
                if query:
                    suggestions.append({
                        "id": f"topic-{topic_lower.replace(' ', '-')[:20]}",
                        "type": "query",
                        "label": topic,
                        "data": {"query": query}
                    })
        
        return {
            "content": clarification_text,
            "suggestions": suggestions
        }
    
    def _generate_clarification_suggestions(
        self,
        language: str
    ) -> List[Dict[str, Any]]:
        """
        Generate suggested actions for clarification responses.
        
        Args:
            language: Response language
            
        Returns:
            List of suggested follow-up queries
        """
        if language == "fil":
            suggestions = [
                {
                    "id": "clarify-1",
                    "type": "query",
                    "label": "Tanong tungkol sa overtime pay",
                    "data": {"query": "Ano ang aking karapatan sa overtime pay?"}
                },
                {
                    "id": "clarify-2",
                    "type": "query",
                    "label": "Tanong tungkol sa termination",
                    "data": {"query": "Ano ang aking karapatan kung ako ay tinanggal sa trabaho?"}
                },
                {
                    "id": "clarify-3",
                    "type": "query",
                    "label": "Tanong tungkol sa benefits",
                    "data": {"query": "Ano ang mga benepisyo na dapat kong matanggap?"}
                }
            ]
        elif language == "ceb":
            suggestions = [
                {
                    "id": "clarify-1",
                    "type": "query",
                    "label": "Pangutana mahitungod sa overtime pay",
                    "data": {"query": "Unsa ang akong katungod sa overtime pay?"}
                },
                {
                    "id": "clarify-2",
                    "type": "query",
                    "label": "Pangutana mahitungod sa termination",
                    "data": {"query": "Unsa ang akong katungod kon ako gitagal sa trabaho?"}
                },
                {
                    "id": "clarify-3",
                    "type": "query",
                    "label": "Pangutana mahitungod sa benefits",
                    "data": {"query": "Unsa ang mga benepisyo nga kinahanglan nakong madawat?"}
                }
            ]
        else:  # English
            suggestions = [
                {
                    "id": "clarify-1",
                    "type": "query",
                    "label": "Ask about overtime pay",
                    "data": {"query": "What are my rights regarding overtime pay?"}
                },
                {
                    "id": "clarify-2",
                    "type": "query",
                    "label": "Ask about termination",
                    "data": {"query": "What are my rights if I am terminated?"}
                },
                {
                    "id": "clarify-3",
                    "type": "query",
                    "label": "Ask about benefits",
                    "data": {"query": "What benefits am I entitled to receive?"}
                }
            ]
        
        return suggestions
    
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
            
            # Step 3: Smart query analysis with clarification detection (if enabled)
            analysis = None
            if settings.enable_smart_clarification:
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
                    conversation_history=conversation_history
                )
                
                analysis_time = time.time() - analysis_start
                
                logger.info(
                    f"Query analysis complete: "
                    f"needs_clarification={analysis.needs_clarification}, "
                    f"concepts={analysis.legal_concepts}, "
                    f"articles={analysis.articles}, "
                    f"time={analysis_time:.3f}s"
                )
                
                # Step 4: Check if clarification is needed (early exit)
                if analysis.needs_clarification:
                    logger.info(
                        f"Clarification needed: {analysis.clarification_reason}"
                    )
                    
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
                                "confidence": 0.5,
                                "disclaimer_required": False,
                                "is_clarification": True,
                                "clarification_reason": analysis.clarification_reason,
                                "tokens_used": 0  # No LLM generation for clarification
                            }
                        }
                    }
                    return
            else:
                # Fallback: no query analysis
                logger.info("Smart clarification disabled - proceeding with retrieval")
            
            # Step 5: Retrieve relevant context
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
            
            retrieval_results = await self.retrieval.retrieve(
                query=user_message,
                keywords=analysis.keywords if analysis else None,
                articles=analysis.articles if analysis else None,
                top_k=settings.retrieval_top_k
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
            
            # Yield metadata event
            yield {
                "type": "metadata",
                "data": {
                    "retrieval_time": round(retrieval_time, 3),
                    "retrieval_count": len(retrieval_results),
                    "avg_confidence": round(avg_score, 3)
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
                        "is_clarification": False
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
