"""
Chat orchestration service.

Coordinates the full RAG pipeline for processing chat messages.
"""
import time
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from core import get_logger, AppError, settings
from services.pipeline.conversation import ConversationPipeline
from services.pipeline.retrieval import RetrievalPipeline
from services.pipeline.grounding import GroundingPipeline
from services.pipeline.generation import GenerationPipeline
from services.pipeline.postprocess import PostprocessPipeline


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
        retrieval_pipeline: RetrievalPipeline,
        grounding_pipeline: GroundingPipeline,
        generation_pipeline: GenerationPipeline,
        postprocess_pipeline: PostprocessPipeline
    ):
        """
        Initialize chat orchestrator.
        
        Args:
            conversation_pipeline: Conversation management pipeline
            retrieval_pipeline: Knowledge retrieval pipeline
            grounding_pipeline: Context grounding pipeline
            generation_pipeline: LLM generation pipeline
            postprocess_pipeline: Response post-processing pipeline
        """
        self.conversation = conversation_pipeline
        self.retrieval = retrieval_pipeline
        self.grounding = grounding_pipeline
        self.generation = generation_pipeline
        self.postprocess = postprocess_pipeline
        
        logger.info("Chat orchestrator initialized")
    
    async def process_message(
        self,
        session_id: str,
        conversation_id: str,
        user_message: str,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the full RAG pipeline.
        
        Args:
            session_id: User session identifier
            conversation_id: Conversation identifier
            user_message: User's message text
            language: Preferred response language (en, fil, ceb)
            context: Optional context information
            
        Returns:
            Dictionary containing response data:
                - message_id: Unique message identifier
                - conversation_id: Conversation identifier
                - role: "assistant"
                - content: Response text
                - citations: List of citations
                - suggestions: List of suggested actions
                - metadata: Processing metadata
                
        Raises:
            AppError: If processing fails
        """
        start_time = time.time()
        
        try:
            logger.info(
                f"Processing message for session={session_id}, "
                f"conversation={conversation_id}, language={language}"
            )
            
            # Step 1: Add user message to conversation history
            await self.conversation.add_user_message(
                session_id=conversation_id,  # Use conversation_id as session
                content=user_message
            )
            
            # Step 2: Check if clarification is needed
            needs_clarification = self.conversation.is_clarification_needed(
                query=user_message
            )
            
            if needs_clarification:
                logger.info("Vague query detected, generating clarification")
                clarification_response = await self._generate_clarification(
                    query=user_message,
                    language=language
                )
                
                # Add clarification to conversation
                await self.conversation.add_assistant_message(
                    session_id=conversation_id,
                    content=clarification_response["content"]
                )
                
                processing_time = time.time() - start_time
                
                return {
                    "message_id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": clarification_response["content"],
                    "timestamp": datetime.utcnow(),
                    "citations": [],
                    "suggestions": clarification_response.get("suggestions", []),
                    "metadata": {
                        "processing_time": processing_time,
                        "model": settings.openai_llm_model,
                        "confidence": 0.5,  # Low confidence for clarifications
                        "disclaimer_required": False,
                        "is_clarification": True
                    }
                }
            
            # Step 3: Retrieve relevant knowledge base chunks
            logger.info(f"Retrieving knowledge for query: {user_message[:50]}...")
            retrieval_results = await self.retrieval.retrieve(
                query=user_message,
                top_k=settings.retrieval_top_k,
                min_similarity=settings.retrieval_similarity_threshold,
                filters=None  # TODO: Add intent-based filtering in Phase 4
            )
            
            logger.info(
                f"Retrieved {len(retrieval_results.results)} chunks "
                f"(avg_score={retrieval_results.avg_score:.3f})"
            )
            
            # Step 4: Get conversation history for context
            conversation_history = await self.conversation.get_conversation_context(
                session_id=conversation_id,
                include_last_n=settings.max_conversation_history
            )
            
            # Step 5: Build grounded prompt with citations
            logger.info("Building grounded prompt with context")
            messages = self.grounding.build_grounded_prompt(
                query=user_message,
                context_results=retrieval_results.results,
                language=language,
                conversation_history=conversation_history
            )
            
            # Step 6: Generate response with LLM
            logger.info("Generating LLM response")
            generation_result = await self.generation.generate_with_retry(
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                max_retries=3
            )
            
            # Step 7: Extract citations from response
            citations_data = self.grounding.extract_citation_metadata(
                response_text=generation_result.content,
                context_results=retrieval_results.results
            )
            
            # Step 8: Post-process response
            logger.info("Post-processing response")
            processed_result = self.postprocess.process_response(
                response=generation_result.content,
                citations=citations_data,
                language=language,
                apply_disclaimer=settings.enable_auto_disclaimer,
                redact_pii=settings.enable_pii_redaction
            )
            
            # Step 9: Add assistant message to conversation history
            await self.conversation.add_assistant_message(
                session_id=conversation_id,
                content=processed_result["content"]
            )
            
            processing_time = time.time() - start_time
            
            # Step 10: Build final response
            message_id = str(uuid.uuid4())
            
            response = {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": processed_result["content"],
                "timestamp": datetime.utcnow(),
                "citations": processed_result["citations"],
                "suggestions": processed_result.get("suggested_actions", []),
                "metadata": {
                    "processing_time": round(processing_time, 2),
                    "model": settings.openai_llm_model,
                    "confidence": retrieval_results.avg_score,
                    "disclaimer_required": settings.enable_auto_disclaimer,
                    "tokens_used": (
                        generation_result.token_usage.get("total_tokens")
                        if generation_result.token_usage
                        else None
                    )
                }
            }
            
            logger.info(
                f"Message processed successfully in {processing_time:.2f}s "
                f"({len(citations_data)} citations, "
                f"{len(processed_result.get('suggested_actions', []))} actions)"
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Error processing message: {str(e)} "
                f"(after {processing_time:.2f}s)",
                exc_info=True
            )
            raise AppError(
                message=f"Failed to process message: {str(e)}",
                code="CHAT_PROCESSING_ERROR",
                details={"processing_time": processing_time}
            )
    
    async def _generate_clarification(
        self,
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Generate a clarification request for vague queries.
        
        Args:
            query: User's vague query
            language: Response language
            
        Returns:
            Dictionary with clarification content and suggestions
        """
        clarification_text = await self.generation.generate_clarification(
            vague_query=query,
            language=language
        )
        
        # Generate helpful follow-up suggestions
        suggestions = self._generate_clarification_suggestions(language)
        
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
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            conversation_id: Conversation to clear
        """
        await self.conversation.clear_conversation(session_id=conversation_id)
        logger.info(f"Cleared conversation: {conversation_id}")
