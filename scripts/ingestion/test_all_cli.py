#!/usr/bin/env python3
"""
Comprehensive CLI test suite for ingestion commands.
Tests all CLI options WITHOUT deleting existing data.

SAFE: Does NOT clean database before testing.
"""
import subprocess
import sys
from pathlib import Path

def run_command(cmd: str, description: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"CMD: {cmd}")
    print('='*80)
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='replace'  # Replace unencodable characters instead of failing
        )
        
        output = result.stdout + result.stderr
        print(output)
        
        success = result.returncode == 0
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"\n{status} - {description}")
        
        return success, output
    except subprocess.TimeoutExpired:
        print(f"\n✗ TIMEOUT - {description}")
        return False, "Command timed out"
    except Exception as e:
        print(f"\n✗ ERROR - {description}: {e}")
        return False, str(e)


def main():
    """Test all CLI commands."""
    print("\n" + "="*80)
    print("CLI COMMAND TEST SUITE")
    print("="*80)
    print("SAFETY: This script does NOT delete existing data")
    print("="*80)
    
    tests = []
    
    # Test 1: Help command
    tests.append((
        "python -m kb.ingest.sync_to_vectorstore --help",
        "Show help message"
    ))
    
    # Test 2: Dry run for single chunk (SAFE - no database changes)
    tests.append((
        "python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-442/00-preliminary-title-preamble.md --dry-run",
        "Dry run - Single chunk from PD-442"
    ))
    
    # Test 3: Dry run for entire folder
    tests.append((
        "python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-851 --dry-run",
        "Dry run - Entire PD-851 folder"
    ))
    
    # Test 4: Check ingestion status
    tests.append((
        "python scripts/check_ingestion_status.py",
        "Check current ingestion status"
    ))
    
    # Test 5: Validate chunks
    tests.append((
        "python scripts/ingestion/validate_chunks.py --document PD-No-442",
        "Validate PD-442 chunks"
    ))
    
    # Test 6: Verify single chunk
    tests.append((
        "python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-442/00-preliminary-title-preamble.md",
        "Verify single chunk file"
    ))
    
    # Test 7: List documents
    tests.append((
        "python scripts/ingestion/list_documents.py",
        "List all chunked documents"
    ))
    
    # Test 8: Check ingestion for specific document
    tests.append((
        "python scripts/ingestion/check_ingestion.py --document PD-No-442",
        "Check PD-442 ingestion status"
    ))
    
    # Run all tests
    results = []
    for cmd, desc in tests:
        success, output = run_command(cmd, desc)
        results.append((desc, success, output))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for desc, success, _ in results:
        status = "✓" if success else "✗"
        print(f"{status} {desc}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
