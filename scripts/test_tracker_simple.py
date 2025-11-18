#!/usr/bin/env python3
"""Simple sync test - no async."""
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("Imports starting...", flush=True)

try:
    from core import get_logger
    print("[OK] Core imported", flush=True)
    
    from kb.ingest.incremental_tracker import IngestionTracker
    print("[OK] Tracker imported", flush=True)
    
    logger = get_logger(__name__)
    print("[OK] Logger initialized", flush=True)
    
    print("\n" + "="*60, flush=True)
    print("Testing IngestionTracker", flush=True)
    print("="*60, flush=True)
    
    tracker = IngestionTracker()
    print("[OK] Tracker initialized", flush=True)
    
    # Test folder hash
    doc_folder = Path("kb/chunks/DOLE-Covid-Protocols")
    print(f"\nFolder: {doc_folder}", flush=True)
    print(f"Exists: {doc_folder.exists()}", flush=True)
    
    print("\nCalculating hash...", flush=True)
    folder_hash = tracker.calculate_folder_hash(doc_folder)
    print(f"[OK] Hash: {folder_hash[:16]}...", flush=True)
    
    # Get record
    print("\nGetting record...", flush=True)
    record = tracker.get_ingestion_record("DOLE-Covid-Protocols")
    if record:
        print(f"[OK] Found: status={record['status']}, hash={record['file_hash'][:16]}...", flush=True)
    else:
        print("[FAIL] No record", flush=True)
    
    # Test should_ingest
    print("\nTesting should_ingest()...", flush=True)
    should_ingest, reason = tracker.should_ingest(
        Path("kb/chunks/DOLE-Covid-Protocols"),
        force=False
    )
    
    print(f"Should ingest: {should_ingest}", flush=True)
    print(f"Reason: {reason}", flush=True)
    
    print("\n" + "="*60, flush=True)
    if not should_ingest:
        print("[PASS] WORKING: Will skip unchanged", flush=True)
    else:
        print("[FAIL] NOT WORKING: Will re-ingest", flush=True)
    print("="*60, flush=True)
    
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
