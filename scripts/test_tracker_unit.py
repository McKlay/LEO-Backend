#!/usr/bin/env python3
"""
Unit test for incremental tracker - tests core logic without external dependencies.

This test verifies that:
1. File hashes are calculated correctly
2. should_ingest() returns correct values
3. File-level tracking works as expected
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kb.ingest.incremental_tracker import IngestionTracker
from core.logging import get_logger

logger = get_logger(__name__)


def test_file_hash_calculation():
    """Test that file hash is calculated correctly."""
    logger.info("Test 1: File hash calculation")
    
    # Create a test file in temp directory
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test content for hashing")
        test_file = Path(f.name)
    
    try:
        # Mock the database connection
        with patch('kb.ingest.incremental_tracker.psycopg2.connect'):
            tracker = IngestionTracker()
            
            # Calculate hash
            hash_value = tracker.calculate_file_hash(test_file)
            
            # Hash should be a 64-character hex string (SHA-256)
            assert len(hash_value) == 64, f"Hash should be 64 chars, got {len(hash_value)}"
            assert all(c in '0123456789abcdef' for c in hash_value), "Hash should be hex"
            
            logger.info(f"  ✓ Hash calculated: {hash_value[:16]}...")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


def test_should_ingest_new_file():
    """Test should_ingest() for new file (no record)."""
    logger.info("\nTest 2: should_ingest() - new file (no database record)")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("New file content")
        test_file = Path(f.name)
    
    try:
        with patch('kb.ingest.incremental_tracker.psycopg2.connect') as mock_connect:
            # Mock: cursor returns None (no record found)
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.__enter__.return_value = mock_cursor
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            tracker = IngestionTracker()
            should_ingest, reason = tracker.should_ingest(test_file, force=False)
            
            assert should_ingest is True, f"New file should be ingested, got {should_ingest}"
            assert "not previously ingested" in reason, f"Unexpected reason: {reason}"
            
            logger.info(f"  ✓ Returns True: {reason}")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


def test_should_ingest_unchanged_file():
    """Test should_ingest() for unchanged file (matching hash)."""
    logger.info("\nTest 3: should_ingest() - unchanged file (hash matches)")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("Unchanged content")
        test_file = Path(f.name)
    
    try:
        # Calculate the file hash first
        with patch('kb.ingest.incremental_tracker.psycopg2.connect'):
            tracker = IngestionTracker()
            current_hash = tracker.calculate_file_hash(test_file)
        
        # Mock database to return matching hash
        with patch('kb.ingest.incremental_tracker.psycopg2.connect') as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'file_name': test_file.name,
                'file_hash': current_hash,  # Same hash!
                'status': 'success'
            }
            mock_cursor.__enter__.return_value = mock_cursor
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            tracker = IngestionTracker()
            should_ingest, reason = tracker.should_ingest(test_file, force=False)
            
            assert should_ingest is False, f"Unchanged file should NOT be ingested, got {should_ingest}"
            assert "unchanged" in reason.lower(), f"Unexpected reason: {reason}"
            
            logger.info(f"  ✓ Returns False: {reason}")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


def test_should_ingest_changed_file():
    """Test should_ingest() for changed file (hash mismatch)."""
    logger.info("\nTest 4: should_ingest() - changed file (hash mismatch)")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("New content")
        test_file = Path(f.name)
    
    try:
        # Calculate current hash
        with patch('kb.ingest.incremental_tracker.psycopg2.connect'):
            tracker = IngestionTracker()
            current_hash = tracker.calculate_file_hash(test_file)
        
        # Mock database to return different hash (simulating change)
        old_hash = "0" * 64  # Fake old hash
        
        with patch('kb.ingest.incremental_tracker.psycopg2.connect') as mock_connect:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'file_name': test_file.name,
                'file_hash': old_hash,  # Different hash!
                'status': 'success'
            }
            mock_cursor.__enter__.return_value = mock_cursor
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            tracker = IngestionTracker()
            should_ingest, reason = tracker.should_ingest(test_file, force=False)
            
            assert should_ingest is True, f"Changed file should be ingested, got {should_ingest}"
            assert "changed" in reason.lower(), f"Unexpected reason: {reason}"
            
            logger.info(f"  ✓ Returns True: {reason}")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


def test_should_ingest_force_flag():
    """Test should_ingest() with force=True."""
    logger.info("\nTest 5: should_ingest() - force flag")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("Force content")
        test_file = Path(f.name)
    
    try:
        with patch('kb.ingest.incremental_tracker.psycopg2.connect') as mock_connect:
            # Even with matching hash in database
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'file_name': test_file.name,
                'file_hash': 'a' * 64,  # Fake hash
                'status': 'success'
            }
            mock_cursor.__enter__.return_value = mock_cursor
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            tracker = IngestionTracker()
            should_ingest, reason = tracker.should_ingest(test_file, force=True)
            
            assert should_ingest is True, f"Force flag should override, got {should_ingest}"
            assert "force" in reason.lower(), f"Unexpected reason: {reason}"
            
            logger.info(f"  ✓ Returns True: {reason}")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False
    finally:
        if test_file.exists():
            test_file.unlink()


def main():
    """Run all tests."""
    logger.info("="*70)
    logger.info("FILE-LEVEL INCREMENTAL TRACKING - UNIT TESTS")
    logger.info("="*70)
    
    tests = [
        test_file_hash_calculation,
        test_should_ingest_new_file,
        test_should_ingest_unchanged_file,
        test_should_ingest_changed_file,
        test_should_ingest_force_flag,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"Test error: {e}", exc_info=True)
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    logger.info("\n" + "="*70)
    logger.info(f"RESULTS: {passed}/{total} tests passed")
    logger.info("="*70)
    
    if all(results):
        logger.info("✅ ALL TESTS PASSED - File-level tracking is working correctly")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED - Check implementation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
