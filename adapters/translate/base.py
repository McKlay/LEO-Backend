"""
Base interface for translation adapters.

Defines the contract for translation services,
enabling easy swapping between translation providers.
"""
from abc import ABC, abstractmethod
from typing import Literal, Optional
from pydantic import BaseModel


SupportedLanguage = Literal["en", "fil", "ceb"]


class TranslationResponse(BaseModel):
    """Translation response."""
    
    translated_text: str
    source_language: str
    target_language: str
    confidence: float = 1.0


class BaseTranslate(ABC):
    """
    Base translation adapter interface.
    
    All translation implementations (Google Translate, DeepL, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def translate(
        self,
        text: str,
        target_language: SupportedLanguage,
        source_language: Optional[str] = None
    ) -> TranslationResponse:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code (en, fil, ceb)
            source_language: Source language (auto-detect if None)
            
        Returns:
            Translation response
            
        Raises:
            TranslationError: If translation fails
        """
        pass
    
    @abstractmethod
    async def detect_language(self, text: str) -> tuple[str, float]:
        """
        Detect language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (language_code, confidence)
            
        Raises:
            TranslationError: If detection fails
        """
        pass
    
    @abstractmethod
    def is_supported(self, language_code: str) -> bool:
        """
        Check if language is supported.
        
        Args:
            language_code: Language code to check
            
        Returns:
            True if supported, False otherwise
        """
        pass
