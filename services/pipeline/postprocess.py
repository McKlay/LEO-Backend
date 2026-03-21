"""
Postprocessing pipeline module for response formatting and enhancement.

Handles citation linking, disclaimers, redaction, and formatting.
"""
from typing import List, Dict, Any, Optional
import re

from core import get_logger


logger = get_logger(__name__)


class PostprocessPipeline:
    """
    Handles post-processing of LLM responses.
    
    Includes citation linking, disclaimer addition, content formatting,
    and optional redaction of sensitive information.
    """
    
    def __init__(
        self,
        enable_auto_disclaimer: bool = True,
        enable_redaction: bool = False
    ):
        """
        Initialize postprocessing pipeline.
        
        Args:
            enable_auto_disclaimer: Automatically add disclaimers
            enable_redaction: Enable PII redaction
        """
        self.enable_auto_disclaimer = enable_auto_disclaimer
        self.enable_redaction = enable_redaction
        
        logger.info(
            f"Postprocessing pipeline initialized "
            f"(disclaimer={enable_auto_disclaimer}, redaction={enable_redaction})"
        )
    
    def process_response(
        self,
        response: str,
        citations: List[Dict[str, Any]],
        language: str = "en",
        add_disclaimer: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Apply all post-processing steps to a response.
        
        Args:
            response: Raw LLM response
            citations: Citation metadata
            language: Language code
            add_disclaimer: Override auto disclaimer setting
            
        Returns:
            Processed response with metadata
        """
        # Start with original response
        processed = response
        
        # 1. Linkify citations
        processed = self.linkify_citations(processed, citations)
        
        # 2. Format markdown
        processed = self.format_markdown(processed)
        
        # 3. Redact sensitive info if enabled
        if self.enable_redaction:
            processed, redactions = self.redact_pii(processed)
        else:
            redactions = []
        
        # 4. Add disclaimer
        should_add_disclaimer = (
            add_disclaimer if add_disclaimer is not None
            else self.enable_auto_disclaimer
        )
        if should_add_disclaimer:
            processed = self.add_disclaimer(processed, language)
        
        logger.info(
            f"Post-processed response "
            f"(citations={len(citations)}, redactions={len(redactions)})"
        )
        
        return {
            "content": processed,
            "has_disclaimer": should_add_disclaimer,
            "redaction_count": len(redactions),
            "citation_count": len(citations)
        }
    
    def linkify_citations(
        self,
        text: str,
        citations: List[Dict[str, Any]]
    ) -> str:
        """
        Convert citation markers to clickable links.
        
        Args:
            text: Text with citation markers like [1], [2]
            citations: Citation metadata with URLs
            
        Returns:
            Text with citation links
        """
        if not citations:
            return text
        
        # Build citation map
        citation_map = {c["id"]: c for c in citations}
        
        # Replace citation markers
        def replace_citation(match):
            citation_id = int(match.group(1))
            if citation_id in citation_map:
                citation = citation_map[citation_id]
                source = citation.get("source", "Unknown")
                url = citation.get("url")
                
                if url:
                    # Create markdown link
                    return f"[[{citation_id}]({url} \"{source}\")]"
                else:
                    # Just bold the citation number
                    return f"**[{citation_id}]**"
            return match.group(0)
        
        # Replace all [N] patterns
        linkified = re.sub(r'\[(\d+)\]', replace_citation, text)
        
        return linkified
    
    def format_markdown(self, text: str) -> str:
        """
        Apply markdown formatting enhancements.
        
        Args:
            text: Input text
            
        Returns:
            Formatted text
        """
        # Ensure proper spacing around headings
        text = re.sub(r'\n(#{1,6})\s+', r'\n\n\1 ', text)
        
        # Ensure proper list formatting
        text = re.sub(r'\n([*-])\s+', r'\n\1 ', text)
        text = re.sub(r'\n(\d+\.)\s+', r'\n\1 ', text)
        
        # Remove excessive blank lines (max 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Trim whitespace
        text = text.strip()
        
        return text
    
    def redact_pii(self, text: str) -> tuple[str, List[str]]:
        """
        Redact potential personally identifiable information.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (redacted_text, list of redaction types)
        """
        redactions = []
        redacted = text
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, redacted):
            redacted = re.sub(email_pattern, '[EMAIL REDACTED]', redacted)
            redactions.append("email")
        
        # Phone numbers (Philippine format)
        phone_pattern = r'\b(?:\+63|0)(?:9\d{9}|\d{2}[-\s]?\d{3}[-\s]?\d{4})\b'
        if re.search(phone_pattern, redacted):
            redacted = re.sub(phone_pattern, '[PHONE REDACTED]', redacted)
            redactions.append("phone")
        
        # SSS/TIN numbers (rough pattern)
        id_pattern = r'\b\d{2}-\d{7}-\d{1}\b|\b\d{3}-\d{3}-\d{3}\b'
        if re.search(id_pattern, redacted):
            redacted = re.sub(id_pattern, '[ID REDACTED]', redacted)
            redactions.append("id_number")
        
        if redactions:
            logger.warning(f"Redacted PII: {', '.join(set(redactions))}")
        
        return redacted, redactions
    
    def add_disclaimer(self, text: str, language: str = "en") -> str:
        """
        Add legal disclaimer to response.
        
        Args:
            text: Response text
            language: Language code
            
        Returns:
            Text with disclaimer appended
        """
        disclaimers = {
            "en": "\n\n---\n\n**⚠️ Disclaimer**: This information is for general guidance only and does not constitute legal advice. For specific legal concerns, please consult with a qualified labor law attorney or contact the Department of Labor and Employment (DOLE).",
            
            "fil": "\n\n---\n\n**⚠️ Paalala**: Ang impormasyong ito ay para sa pangkalahatang gabay lamang at hindi legal na payo. Para sa partikular na legal na usapin, makipag-ugnayan sa isang kwalipikadong abogado o sa Department of Labor and Employment (DOLE).",
            
            "ceb": "\n\n---\n\n**⚠️ Pahinumdom**: Kining impormasyon alang sa kinatibuk-ang giya lamang ug dili legal nga tambag. Para sa piho nga legal nga mga kabalaka, pakigsulti sa usa ka kwalipikado nga abogado o sa Department of Labor and Employment (DOLE)."
        }
        
        disclaimer = disclaimers.get(language, disclaimers["en"])
        return text + disclaimer
    
    def extract_key_points(self, text: str, max_points: int = 3) -> List[str]:
        """
        Extract key points from response for suggested actions.
        
        Args:
            text: Response text
            max_points: Maximum number of points to extract
            
        Returns:
            List of key points
        """
        # Simple extraction: look for numbered or bulleted lists
        key_points = []
        
        # Find numbered lists
        numbered = re.findall(r'\n\d+\.\s+(.+?)(?=\n|$)', text)
        key_points.extend(numbered[:max_points])
        
        # Find bulleted lists if not enough points
        if len(key_points) < max_points:
            bulleted = re.findall(r'\n[*-]\s+(.+?)(?=\n|$)', text)
            remaining = max_points - len(key_points)
            key_points.extend(bulleted[:remaining])
        
        # Clean up points
        key_points = [p.strip() for p in key_points]
        
        return key_points
    
    def generate_suggested_actions(
        self,
        response: str,
        citations: List[Dict[str, Any]],
        language: str = "en"
    ) -> List[str]:
        """
        Generate suggested follow-up actions based on response.
        
        Args:
            response: LLM response
            citations: Citation metadata
            language: Language code
            
        Returns:
            List of suggested actions
        """
        suggestions = []
        
        # Language-specific templates
        templates = {
            "en": {
                "learn_more": "Learn more about {topic}",
                "find_legal_aid": "Find legal aid near you",
                "file_complaint": "How to file a labor complaint",
                "contact_dole": "Contact DOLE for assistance"
            },
            "fil": {
                "learn_more": "Alamin pa ang tungkol sa {topic}",
                "find_legal_aid": "Maghanap ng legal aid malapit sa iyo",
                "file_complaint": "Paano mag-file ng labor complaint",
                "contact_dole": "Kontakin ang DOLE para sa tulong"
            },
            "ceb": {
                "learn_more": "Hibal-i pa ang mahitungod sa {topic}",
                "find_legal_aid": "Pangitaa ang legal aid duol kanimo",
                "file_complaint": "Unsaon pag-file og labor complaint",
                "contact_dole": "Kontaka ang DOLE alang sa tabang"
            }
        }
        
        lang_templates = templates.get(language, templates["en"])
        
        # Always suggest finding legal aid
        suggestions.append(lang_templates["find_legal_aid"])
        
        # Suggest based on keywords
        response_lower = response.lower()
        
        if any(word in response_lower for word in ["complaint", "file", "violation"]):
            suggestions.append(lang_templates["file_complaint"])
        
        # Add contact DOLE as final suggestion
        suggestions.append(lang_templates["contact_dole"])
        
        return suggestions[:3]  # Max 3 suggestions
