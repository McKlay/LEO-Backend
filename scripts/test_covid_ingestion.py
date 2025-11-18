"""Quick test script for COVID protocols ingestion."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Test COVID protocols ingestion."""
    try:
        # Initialize adapters
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        llm = get_llm_adapter()
        
        # Create ingester
        ingester = KnowledgeBaseIngester(
            embeddings_adapter=embeddings,
            vectorstore_adapter=vectorstore,
            llm_adapter=llm,
            use_summarization=False
        )
        
        # Test dry run
        print("=" * 60)
        print("Testing DOLE-Covid-Protocols dry-run ingestion...")
        print("(Re-chunked into 3 contextually complete chunks)")
        print("=" * 60)
        
        result = await ingester.ingest_manual_chunks(
            document_name="DOLE-Covid-Protocols",
            single_file=None,
            dry_run=True,
            force=False
        )
        
        print(f"\nResult: {result}")
        print("\nDry run completed successfully!")
        print(f"  - Status: {result['status']}")
        print(f"  - Chunks to ingest: {result.get('chunks', 0)}")
        print(f"  - Document: {result.get('document', 'N/A')}")
        
        if result['status'] == 'failed':
            print(f"  - Error: {result.get('error', 'Unknown')}")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
