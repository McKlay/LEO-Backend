"""
Source management for labor law knowledge base.

Handles creation and management of labor_law_sources records,
ensuring proper linking between documents and their metadata.
"""
import uuid
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

from core import get_logger
from core.config import settings

logger = get_logger(__name__)


class SourceManager:
    """Manages labor_law_sources table operations."""
    
    def __init__(self):
        """Initialize source manager with database connection."""
        self.db_url = settings.supabase_db_url
        if not self.db_url:
            raise ValueError("SUPABASE_DB_URL not configured")
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    def create_source(
        self,
        source_type: str,
        title: str,
        reference: str,
        url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> uuid.UUID:
        """
        Create or get existing source record.
        
        Args:
            source_type: Type of source ('statute', 'irr', 'order', 'primer', etc.)
            title: Full title of the document
            reference: Unique reference (e.g., 'PD 442', 'RA 11058')
            url: Optional URL to the source
            notes: Optional notes about the source
            
        Returns:
            UUID of the source record (new or existing)
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Try to insert, return existing if conflict
                cur.execute("""
                    INSERT INTO labor_law_sources (
                        source_type, title, reference, url
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (reference) DO UPDATE
                    SET 
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        updated_at = NOW()
                    RETURNING id
                """, (source_type, title, reference, url))
                
                source_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info(f"Source created/updated: {reference} (ID: {source_id})")
                return source_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create source {reference}: {e}")
            raise
        finally:
            conn.close()
    
    def get_source_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        """
        Get source by reference code.
        
        Args:
            reference: Reference code (e.g., 'PD 442')
            
        Returns:
            Source dict or None if not found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, source_type, title, reference, url, created_at, updated_at
                    FROM labor_law_sources
                    WHERE reference = %s
                """, (reference,))
                
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None
                
        finally:
            conn.close()
    
    def get_source_by_id(self, source_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get source by UUID.
        
        Args:
            source_id: UUID of the source
            
        Returns:
            Source dict or None if not found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, source_type, title, reference, url, created_at, updated_at
                    FROM labor_law_sources
                    WHERE id = %s
                """, (str(source_id),))
                
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None
                
        finally:
            conn.close()
    
    def list_all_sources(self) -> List[Dict[str, Any]]:
        """
        List all sources in the database.
        
        Returns:
            List of source dicts
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id, source_type, title, reference, url, 
                        created_at, updated_at,
                        (SELECT COUNT(*) FROM labor_law_sections WHERE source_id = labor_law_sources.id) as section_count
                    FROM labor_law_sources
                    ORDER BY reference
                """)
                
                return [dict(row) for row in cur.fetchall()]
                
        finally:
            conn.close()
    
    def delete_source(self, source_id: uuid.UUID) -> int:
        """
        Delete a source and all its sections (CASCADE).
        
        Args:
            source_id: UUID of the source to delete
            
        Returns:
            Number of sections deleted
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Count sections before deletion
                cur.execute("""
                    SELECT COUNT(*) FROM labor_law_sections
                    WHERE source_id = %s
                """, (str(source_id),))
                section_count = cur.fetchone()[0]
                
                # Delete source (CASCADE will delete sections)
                cur.execute("""
                    DELETE FROM labor_law_sources
                    WHERE id = %s
                """, (str(source_id),))
                
                conn.commit()
                logger.info(f"Deleted source {source_id} and {section_count} sections")
                return section_count
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to delete source {source_id}: {e}")
            raise
        finally:
            conn.close()
    
    def create_sources_from_registry(self, registry: Dict[str, Dict[str, Any]]) -> Dict[str, uuid.UUID]:
        """
        Batch create sources from document registry.
        
        Args:
            registry: Dict mapping filenames to metadata
            
        Returns:
            Dict mapping filenames to source UUIDs
        """
        source_map = {}
        
        for filename, metadata in registry.items():
            # Extract reference from source field
            # e.g., "Presidential Decree No. 442 (Labor Code)" -> "PD 442"
            source_name = metadata.get("source", "")
            short_name = metadata.get("short_name", filename)
            
            # Derive reference from source or short_name
            if "PD" in source_name or "Presidential Decree" in source_name:
                # Extract number
                import re
                match = re.search(r'(?:PD|Presidential Decree)\s*(?:No\.)?\s*(\d+)', source_name)
                if match:
                    reference = f"PD {match.group(1)}"
                else:
                    reference = short_name
            elif "RA" in source_name or "Republic Act" in source_name:
                import re
                match = re.search(r'(?:RA|Republic Act)\s*(?:No\.)?\s*(\d+)', source_name)
                if match:
                    reference = f"RA {match.group(1)}"
                else:
                    reference = short_name
            else:
                # Use short_name or filename
                reference = short_name or filename.replace('.txt', '')
            
            try:
                source_id = self.create_source(
                    source_type=metadata.get("doc_type", "statute"),
                    title=source_name,
                    reference=reference,
                    url=metadata.get("url")
                )
                source_map[filename] = source_id
                logger.info(f"✓ {filename} -> {reference} (ID: {source_id})")
                
            except Exception as e:
                logger.error(f"✗ Failed to create source for {filename}: {e}")
                continue
        
        return source_map
