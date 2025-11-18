"""
Incremental Ingestion Tracker for Day 4 KB Enhancement.

Tracks file ingestion using SHA-256 hashes to detect new/modified files
and avoid re-processing unchanged content.
"""
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class IngestionTracker:
    """
    Tracks file ingestion history to enable incremental updates.
    
    Uses SHA-256 file hashing to detect changes and avoid
    re-ingesting unchanged documents.
    """
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize the tracker with database connection.
        
        Args:
            db_url: PostgreSQL connection URL (uses settings.supabase_db_url if None)
        """
        self.db_url = db_url or settings.supabase_db_url
        if not self.db_url:
            raise ValueError("Database URL not provided and SUPABASE_DB_URL not set")
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal SHA-256 hash string
        """
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files efficiently
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            hash_value = sha256_hash.hexdigest()
            logger.debug(f"Calculated hash for {file_path.name}: {hash_value[:16]}...")
            return hash_value
            
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            raise
    
    def get_ingestion_record(self, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve ingestion history record for a file.
        
        Args:
            file_name: Name of the file
            
        Returns:
            Dictionary with ingestion record or None if not found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        id, file_name, file_path, file_hash, 
                        chunk_count, token_count, ingestion_method,
                        status, error_message, created_at, updated_at
                    FROM ingestion_history
                    WHERE file_name = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (file_name,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
        finally:
            conn.close()
    
    def should_ingest(
        self, 
        file_path: Path, 
        force: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if file should be ingested based on history.
        
        Args:
            file_path: Path to file
            force: If True, always return True (force re-ingestion)
            
        Returns:
            Tuple of (should_ingest: bool, reason: str)
        """
        file_name = file_path.name
        
        if force:
            logger.info(f"Force flag set - will ingest {file_name}")
            return True, "Force flag enabled"
        
        # Calculate current file hash
        try:
            current_hash = self.calculate_file_hash(file_path)
        except Exception as e:
            logger.error(f"Failed to hash {file_name}: {e}")
            return False, f"Hash calculation failed: {e}"
        
        # Check ingestion history
        record = self.get_ingestion_record(file_name)
        
        if not record:
            logger.info(f"New file detected: {file_name}")
            return True, "File not previously ingested"
        
        # Compare hashes
        stored_hash = record.get("file_hash")
        if stored_hash != current_hash:
            logger.info(f"File modified: {file_name} (hash changed)")
            logger.debug(f"  Old hash: {stored_hash[:16]}...")
            logger.debug(f"  New hash: {current_hash[:16]}...")
            return True, "File content changed"
        
        # Check if previous ingestion failed
        if record.get("status") == "failed":
            logger.info(f"Previous ingestion failed for {file_name} - retrying")
            return True, "Previous ingestion failed"
        
        # Hash matches and ingestion succeeded - verify chunks exist in DB
        # This handles the case where chunks were manually deleted
        if not self._verify_chunks_exist(file_name):
            logger.info(f"Chunks missing in DB for {file_name} - re-ingesting")
            return True, "Chunks missing in database"
        
        logger.info(f"File unchanged: {file_name} (skipping)")
        return False, "File unchanged since last ingestion"
    
    def _verify_chunks_exist(self, file_name: str) -> bool:
        """
        Verify that chunks from this file actually exist in the database.
        
        This prevents skipping ingestion when chunks were manually deleted
        from labor_law_sections but history still shows successful ingestion.
        
        Args:
            file_name: Name of the file (e.g., "01-decree-main.md")
            
        Returns:
            True if chunks exist, False if missing
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Extract file stem (filename without extension)
                # e.g., "01-decree-main.md" -> "01-decree-main"
                file_stem = file_name.replace('.md', '').replace('.txt', '')
                
                # Query labor_law_sections for chunks from this file
                # The file_stem is stored in metadata->file_stem
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM labor_law_sections 
                    WHERE metadata->>'file_stem' = %s
                """, (file_stem,))
                
                count = cursor.fetchone()[0]
                
                if count > 0:
                    logger.debug(f"Found {count} chunks for {file_name} in database")
                    return True
                else:
                    logger.warning(f"No chunks found for {file_name} in database")
                    return False
                    
        except Exception as e:
            # If verification fails, err on the side of re-ingesting
            logger.warning(f"Failed to verify chunks for {file_name}: {e}")
            return False
        finally:
            conn.close()
    
    def record_ingestion(
        self,
        file_path: Path,
        file_hash: str,
        chunk_count: int,
        token_count: Optional[int] = None,
        ingestion_method: str = "regex_chunking",
        status: str = "success",
        error_message: Optional[str] = None
    ) -> str:
        """
        Record successful ingestion in database.
        
        Args:
            file_path: Path to ingested file
            file_hash: SHA-256 hash of file content
            chunk_count: Number of chunks created
            token_count: Total tokens processed (optional)
            ingestion_method: Method used ('manual_chunking', 'regex_chunking', etc.)
            status: Ingestion status ('success', 'failed', 'in_progress')
            error_message: Error message if status is 'failed'
            
        Returns:
            Record ID (UUID)
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ingestion_history (
                        file_name, file_path, file_hash, chunk_count,
                        token_count, ingestion_method, status, error_message
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (file_name) DO UPDATE SET
                        file_path = EXCLUDED.file_path,
                        file_hash = EXCLUDED.file_hash,
                        chunk_count = EXCLUDED.chunk_count,
                        token_count = EXCLUDED.token_count,
                        ingestion_method = EXCLUDED.ingestion_method,
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        updated_at = NOW()
                    RETURNING id
                """, (
                    file_path.name,
                    str(file_path),
                    file_hash,
                    chunk_count,
                    token_count,
                    ingestion_method,
                    status,
                    error_message
                ))
                
                record_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(
                    f"Recorded ingestion: {file_path.name} "
                    f"({chunk_count} chunks, status: {status})"
                )
                
                return str(record_id)
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to record ingestion for {file_path.name}: {e}")
            raise
        finally:
            conn.close()
    
    def delete_old_chunks(self, file_name: str) -> int:
        """
        Delete old sections for a file before re-ingestion.
        
        This is called when a file is modified or force re-ingested.
        Uses labor_law_sections (new schema).
        
        Args:
            file_name: Name of the file
            
        Returns:
            Number of sections deleted
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Delete from labor_law_sections (new schema table)
                # Match by article_number containing the cleaned file stem
                # The article_number format is: "{clean_source}_{hash}"
                # e.g., "presidential_decree_no_851_abc123"
                # where clean_source comes from the full document name in DOCUMENT_REGISTRY
                
                # Extract patterns to match various document naming conventions
                # Examples:
                #   PD-No-442.txt -> match "presidential_decree%" AND "%442%"
                #   RA-No-11058.txt -> match "republic_act%" AND "%11058%"
                file_stem = file_name.replace('.txt', '')
                
                # Pattern 1: Direct file stem (e.g., pd_no_442)
                pattern_direct = f"%{file_stem.replace('-', '_').lower()}%"
                
                # Pattern 2: Expanded form for decree/act documents
                pattern_expanded = None
                if '-No-' in file_stem or '-no-' in file_stem:
                    parts = file_stem.split('-')
                    if len(parts) >= 3:
                        doc_type = parts[0].lower()  # "PD", "RA", etc.
                        doc_number = parts[2]  # "442", "11058", "851" etc.
                        
                        # Map abbreviations to full names
                        type_map = {
                            'pd': 'presidential_decree',
                            'ra': 'republic_act',
                            'eo': 'executive_order',
                            'ao': 'administrative_order'
                        }
                        
                        full_type = type_map.get(doc_type, doc_type)
                        # Combine type and number in single pattern
                        pattern_expanded = f"%{full_type}_no_{doc_number}%"
                
                # Try patterns in order of specificity
                patterns_to_try = [p for p in [pattern_expanded, pattern_direct] if p]
                
                total_deleted = 0
                for pattern in patterns_to_try:
                    cursor.execute("""
                        DELETE FROM labor_law_sections
                        WHERE LOWER(article_number) LIKE %s
                        RETURNING id
                    """, (pattern,))
                    
                    deleted = cursor.rowcount
                    if deleted > 0:
                        total_deleted = deleted
                        logger.info(f"Pattern '{pattern}' matched {deleted} sections")
                        # Break after first successful match
                        break
                
                conn.commit()
                
                if total_deleted > 0:
                    logger.info(f"Deleted {total_deleted} old sections from labor_law_sections for {file_name}")
                else:
                    logger.warning(f"No sections found to delete for {file_name} (tried patterns: {patterns_to_try})")
                
                return total_deleted
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to delete old sections for {file_name}: {e}")
            # Don't raise - allow ingestion to continue
            return 0
        finally:
            conn.close()
    
    def get_all_ingested_files(self) -> list[Dict[str, Any]]:
        """
        Get list of all successfully ingested files.
        
        Returns:
            List of ingestion records
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        file_name, file_path, chunk_count, 
                        token_count, ingestion_method, status,
                        created_at, updated_at
                    FROM ingestion_history
                    WHERE status = 'success'
                    ORDER BY updated_at DESC
                """)
                
                return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get overall ingestion statistics.
        
        Returns:
            Dictionary with stats (total_files, total_chunks, success_rate, etc.)
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_files,
                        SUM(chunk_count) as total_chunks,
                        SUM(token_count) as total_tokens,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM ingestion_history
                """)
                
                result = cursor.fetchone()
                stats = dict(result) if result else {}
                
                # Calculate success rate
                total = stats.get('total_files', 0)
                successful = stats.get('successful', 0)
                stats['success_rate'] = (successful / total * 100) if total > 0 else 0
                
                return stats
        finally:
            conn.close()
