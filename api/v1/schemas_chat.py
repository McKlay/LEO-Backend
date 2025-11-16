"""
Pydantic schemas for chat API endpoints.

Defines request and response models for chat message endpoints.
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Request Models

class UserMetadata(BaseModel):
    """Optional user context metadata."""
    
    employment_type: Optional[str] = Field(
        None,
        description="Employment type (regular, contractual, probationary, etc.)",
        max_length=50
    )
    industry: Optional[str] = Field(
        None,
        description="Industry sector",
        max_length=50
    )


class MessageContext(BaseModel):
    """Context for chat message request."""
    
    previous_message_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="IDs of previous messages in conversation"
    )
    user_metadata: Optional[UserMetadata] = Field(
        None,
        description="Optional user context information"
    )


class ChatMessageRequest(BaseModel):
    """Request schema for sending a chat message."""
    
    conversation_id: Optional[str] = Field(
        None,
        alias="conversationId",
        description="Conversation ID (creates new if not provided)",
        min_length=1,
        max_length=100
    )
    message: str = Field(
        ...,
        description="User message text",
        min_length=1,
        max_length=2000
    )
    language: Literal["en", "fil", "ceb"] = Field(
        default="en",
        description="Preferred response language"
    )
    context: Optional[MessageContext] = Field(
        None,
        description="Optional context for the message"
    )
    
    model_config = ConfigDict(
        populate_by_name=True  # Allow both snake_case and camelCase
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message is not empty or only whitespace."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or only whitespace")
        return v.strip()


# Response Models

class Citation(BaseModel):
    """Legal citation with source information."""
    
    id: str = Field(..., description="Unique citation identifier")
    text: str = Field(..., description="Cited text excerpt")
    source: str = Field(..., description="Source document name")
    article: str = Field(..., description="Article or section reference")
    url: str = Field(..., description="Canonical URL to source")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for citation relevance"
    )


class ContactActionData(BaseModel):
    """Data for contact-type suggested action."""
    
    name: str = Field(..., description="Organization or contact name")
    hotline: Optional[str] = Field(None, description="Hotline number")
    email: Optional[str] = Field(None, description="Contact email")
    website: Optional[str] = Field(None, description="Website URL")


class FormActionData(BaseModel):
    """Data for form-type suggested action."""
    
    form_name: str = Field(..., description="Name of the form")
    instructions: List[str] = Field(
        default_factory=list,
        description="Step-by-step instructions"
    )
    download_url: Optional[str] = Field(None, description="Form download URL")


class LinkActionData(BaseModel):
    """Data for link-type suggested action."""
    
    url: str = Field(..., description="Destination URL")
    external: bool = Field(default=True, description="Whether link is external")


class QueryActionData(BaseModel):
    """Data for query-type suggested action."""
    
    query: str = Field(..., description="Suggested follow-up query text")


class InfoActionData(BaseModel):
    """Data for info-type suggested action."""
    
    title: str = Field(..., description="Information title")
    content: str = Field(..., description="Information content")


class SuggestedAction(BaseModel):
    """Context-aware suggested action for the user."""
    
    id: str = Field(..., description="Unique action identifier")
    type: Literal["contact", "form", "link", "query", "info"] = Field(
        ...,
        description="Action type"
    )
    label: str = Field(..., description="Display label for the action")
    data: Dict[str, Any] = Field(
        ...,
        description="Action-specific data payload"
    )


class MessageMetadata(BaseModel):
    """Metadata about message processing."""
    
    processing_time: float = Field(
        ...,
        ge=0.0,
        description="Total processing time in seconds"
    )
    retrieval_time: float = Field(
        ...,
        ge=0.0,
        description="Vector data retrieval time in seconds"
    )
    generation_time: float = Field(
        ...,
        ge=0.0,
        description="LLM response generation time in seconds"
    )
    model: str = Field(..., description="LLM model used")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall response confidence"
    )
    disclaimer_required: bool = Field(
        default=True,
        description="Whether disclaimer is included"
    )
    tokens_used: Optional[int] = Field(
        None,
        description="Total tokens used for generation"
    )


class ChatMessageResponse(BaseModel):
    """Response schema for chat message."""
    
    message_id: str = Field(..., description="Unique message identifier", serialization_alias="messageId")
    conversation_id: str = Field(..., description="Conversation identifier", serialization_alias="conversationId")
    role: Literal["assistant"] = Field(
        default="assistant",
        description="Message role (always assistant for responses)"
    )
    content: str = Field(..., description="Response content with markdown")
    timestamp: datetime = Field(
        ...,
        description="Response timestamp"
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Legal citations supporting the response"
    )
    suggestions: List[SuggestedAction] = Field(
        default_factory=list,
        description="Context-aware suggested actions"
    )
    metadata: MessageMetadata = Field(
        ...,
        description="Response metadata"
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "messageId": "msg-123e4567-e89b-12d3-a456-426614174000",
                "conversationId": "conv-123e4567-e89b-12d3-a456-426614174000",
                "role": "assistant",
                "content": "Under Article 279 of the Labor Code...",
                "timestamp": "2025-10-31T10:30:00Z",
                "citations": [
                    {
                        "id": "cite-1",
                        "text": "Regular employees are entitled to security of tenure.",
                        "source": "Labor Code of the Philippines",
                        "article": "Article 279",
                        "url": "https://www.dole.gov.ph/labor-code/",
                        "confidence": 0.95
                    }
                ],
                "suggestions": [
                    {
                        "id": "action-1",
                        "type": "contact",
                        "label": "Contact DOLE",
                        "data": {
                            "name": "Department of Labor and Employment",
                            "hotline": "1349",
                            "email": "dolero4a@gmail.com",
                            "website": "https://www.dole.gov.ph"
                        }
                    }
                ],
                "metadata": {
                    "processing_time": 1.5,
                    "model": "gpt-4-turbo-preview",
                    "confidence": 0.92,
                    "disclaimer_required": True,
                    "tokens_used": 450
                }
            }
        }
    )
