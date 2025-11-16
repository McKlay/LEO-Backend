# LLM Chunking System - Archived

**Archive Date**: November 13, 2024  
**Reason**: Replaced by Manual Chunking System  
**Status**: Archived for reference only - DO NOT USE

---

## Why This Was Archived

The LLM-driven automatic chunking system was replaced with a manual chunking workflow due to:

1. **Coverage Issues**: Only processed 35% of documents (2000/9731 chars for PD-No-851)
   - Token/character limits caused truncation
   - Large documents were incompletely processed

2. **Accuracy Concerns**: 
   - Incorrect hierarchical grouping (e.g., rules_sec1 created separately instead of under rules_preamble)
   - Non-deterministic behavior even at temperature 0.0
   - Difficulty validating correctness without human review

3. **Operational Complexity**:
   - High API costs for large document corpus
   - No incremental update capability (must re-chunk entire document)
   - Cannot track changes over time

---

## Replacement System

**Manual Chunking with Automated Ingestion**

- **Location**: `kb/chunks/`
- **Loader**: `kb/ingest/loaders/manual_chunk_loader.py`
- **Documentation**: `docs/database_ingestion/`
- **Benefits**:
  - 100% coverage guaranteed (human-verified)
  - Perfect semantic boundaries (legal expertise)
  - Git-trackable incremental updates
  - Zero API costs for chunking
  - Full control over chunk quality

---

## Archived Files

### Code
- `llm_chunker.py` (443 lines)
  - `LLMDrivenChunker` class
  - `LLMChunk` dataclass
  - Async chunk_document() method
  - Regex fallback mechanism

### Integration Points Removed
From `kb/ingest/sync_to_vectorstore.py`:
- Import statement: `from retrieval.llm_chunker import LLMDrivenChunker`
- Constructor parameter: `llm_chunker: Optional[LLMDrivenChunker]`
- Constructor parameter: `use_llm_chunking: bool = True`
- Instance variables: `self.use_llm_chunking`, `self.llm_chunker`
- Chunking logic: 100+ lines of LLM chunking workflow
- CLI arguments: `--use-regex` flag (no longer needed)

From `kb/ingest/incremental_tracker.py`:
- Method parameter: `ingestion_method: str = "llm_chunking"`
- Documentation references to LLM chunking

---

## Migration Path

If you need to restore LLM chunking (NOT RECOMMENDED):

1. Copy `llm_chunker.py` back to `retrieval/`
2. Restore removed code in `sync_to_vectorstore.py` (see git history)
3. Install OpenAI dependencies (already in requirements.txt)
4. Configure API keys in `.env`

However, **we strongly recommend continuing with manual chunking** for the reasons listed above.

---

## Performance Comparison

### LLM Chunking (Archived)
- Coverage: 35% (PD-No-851: 5/14 sections)
- Accuracy: 100% on processed content (but incomplete)
- Cost: ~$0.01-0.05 per document
- Speed: 5-15 seconds per document
- Incremental updates: ❌ Not supported

### Manual Chunking (Current)
- Coverage: 100% (PD-No-851: 14/14 sections, all content)
- Accuracy: 100% (human-verified)
- Cost: $0 (no API calls for chunking)
- Speed: Instant (pre-chunked)
- Incremental updates: ✅ Git-tracked, chunk-level updates

---

## Questions?

Refer to:
- `docs/database_ingestion/MANUAL_CHUNKING_DECISION.md` - Decision rationale
- `docs/database_ingestion/MANUAL_CHUNKING_ARCHITECTURE.md` - New system architecture
- `docs/database_ingestion/IMPLEMENTATION_GUIDE.md` - Implementation phases
