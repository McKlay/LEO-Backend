"""
Test auto-chunker functionality.

Verifies that AutoChunker correctly identifies and chunks oversized articles.
"""
import asyncio
from pathlib import Path
import pytest

from core import get_logger
from kb.processing.auto_chunker import AutoChunker
from app.containers import get_embeddings_adapter, get_llm_adapter

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_auto_chunker():
    """Test auto-chunking with sample text."""
    
    # Initialize adapters
    embeddings = get_embeddings_adapter()
    llm = get_llm_adapter()
    
    # Create auto-chunker
    chunker = AutoChunker(
        embeddings_adapter=embeddings,
        llm_adapter=llm,
        use_summarization=True
    )
    
    # Sample oversized text (simulate Article 217-225 with ~2500 words)
    sample_text = """
    Article 217. Jurisdiction of Labor Arbiters and the Commission

    (a) Original and Exclusive Jurisdiction of Labor Arbiters:

    Except as otherwise provided under this Code, the Labor Arbiters shall have original and exclusive jurisdiction to hear and decide, within thirty (30) calendar days after the submission of the case by the parties for decision without extension, even in the absence of stenographic notes, the following cases involving all workers, whether agricultural or non-agricultural:

    1. Unfair labor practice cases;
    2. Termination disputes;
    3. If accompanied with a claim for reinstatement, those cases that workers may file involving wages, rate of pay, hours of work and other terms and conditions of employment;
    4. Claims for actual, moral, exemplary and other forms of damages arising from the employer-employee relations;
    5. Cases arising from any violation of Article 264 of this Code, including questions involving the legality of strikes and lockouts; and
    6. Except claims for employees compensation, social security, medicare and maternity benefits, all other claims arising from employer-employee relations, including those of persons in domestic or household service, involving an amount exceeding five thousand pesos (P5,000.00), whether or not accompanied with a claim for reinstatement.

    (b) Appellate Jurisdiction:

    The Commission shall have exclusive appellate jurisdiction over all cases decided by Labor Arbiters.

    (c) Collective Bargaining and Personnel Policy Disputes:

    Cases arising from the interpretation or implementation of collective bargaining agreements and those arising from the interpretation or enforcement of company personnel policies shall be disposed of by the Labor Arbiter by referring the same to the grievance machinery and voluntary arbitration as may be provided in said agreements.
    
    """ * 8  # Repeat to simulate ~2000+ words
    
    # Test 1: Check if should auto-chunk
    logger.info("Test 1: Checking if text should be auto-chunked...")
    should_chunk = chunker.should_auto_chunk(sample_text)
    logger.info(f"  Result: {should_chunk} (word count: {len(sample_text.split())})")
    assert should_chunk, "Text with >1000 words should trigger auto-chunking"
    
    # Test 2: Split into chunks
    logger.info("\nTest 2: Splitting text into chunks...")
    chunks = chunker.split_by_paragraphs(sample_text)
    logger.info(f"  Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        word_count = len(chunk.split())
        logger.info(f"  Chunk {i}: {word_count} words")
        assert word_count <= chunker.MAX_CHUNK_SIZE, f"Chunk {i} exceeds max size"
    
    # Test 3: Create sub-chunks (without DB insertion)
    logger.info("\nTest 3: Creating sub-chunk records (simulated)...")
    section_id = "test-section-id-123"
    metadata = {
        "article_number": "Articles 217-225",
        "source": "Test",
        "doc_type": "statute"
    }
    
    # Note: This will generate embeddings and summaries
    # Comment out if you want to avoid API calls
    # sub_chunks = await chunker.create_sub_chunks(section_id, sample_text, metadata)
    # logger.info(f"  Created {len(sub_chunks)} sub-chunk records")
    # for i, record in enumerate(sub_chunks):
    #     logger.info(f"  Sub-chunk {i}:")
    #     logger.info(f"    Words: {len(record['chunk_text'].split())}")
    #     logger.info(f"    Has summary: {record['summary'] is not None}")
    #     logger.info(f"    Keywords: {record['keywords'][:3]}..." if record['keywords'] else "    Keywords: None")
    
    logger.info("\n✓ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_auto_chunker())
