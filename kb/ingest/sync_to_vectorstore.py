"""
Knowledge base ingestion CLI.

Chunks legal documents and syncs them to Supabase vector store
with embeddings and proper metadata for citation.

Usage:
    python -m kb.ingest.sync_to_vectorstore --help
    python -m kb.ingest.sync_to_vectorstore --file kb/docs/PD-No-442.txt
    python -m kb.ingest.sync_to_vectorstore --all
    python -m kb.ingest.sync_to_vectorstore --all --dry-run
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional
import argparse

from core import get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter
from retrieval.chunking import LegalDocumentChunker
from kb.ingest.loaders import TextFileLoader
from adapters.vectorstore.base import Document

logger = get_logger(__name__)


# Document metadata registry with canonical URLs
DOCUMENT_REGISTRY = {
    "PD-No-442.txt": {
        "source": "Presidential Decree No. 442 (Labor Code)",
        "doc_type": "statute",
        "year": "1974",
        "url": "https://lawphil.net/statutes/presdecs/pd1974/pd_442_1974.html",
        "short_name": "Labor Code"
    },
    "RA-No-11058.txt": {
        "source": "Republic Act No. 11058",
        "doc_type": "statute",
        "year": "2018",
        "url": "https://lawphil.net/statutes/repacts/ra2018/ra_11058_2018.html",
        "short_name": "OSH Standards Law"
    },
    "RA-No-11199.txt": {
        "source": "Republic Act No. 11199",
        "doc_type": "statute",
        "year": "2019",
        "url": "https://lawphil.net/statutes/repacts/ra2019/ra_11199_2019.html",
        "short_name": "Social Security Act"
    },
    "RA-No-10361.txt": {
        "source": "Republic Act No. 10361",
        "doc_type": "statute",
        "year": "2013",
        "url": "https://lawphil.net/statutes/repacts/ra2013/ra_10361_2013.html",
        "short_name": "Domestic Workers Act"
    },
    "PD-No-851.txt": {
        "source": "Presidential Decree No. 851",
        "doc_type": "statute",
        "year": "1975",
        "url": "https://lawphil.net/statutes/presdecs/pd1975/pd_851_1975.html",
        "short_name": "13th Month Pay Law"
    },
    "DOLE-Dep-Order-147-15.txt": {
        "source": "DOLE Department Order No. 147-15",
        "doc_type": "department_order",
        "year": "2015",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/71535",
        "short_name": "DO 147-15"
    },
    "SEnA.txt": {
        "source": "Single Entry Approach Rules",
        "doc_type": "procedural_rules",
        "year": "2011",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/5/92443",
        "short_name": "SEnA Rules"
    },
    "NLRC-Rules.txt": {
        "source": "NLRC Rules of Procedure",
        "doc_type": "procedural_rules",
        "year": "2011",
        "url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/57844",
        "short_name": "NLRC Rules"
    },
    "DOLE-Handbook.txt": {
        "source": "DOLE Handbook on Workers' Statutory Monetary Benefits",
        "doc_type": "handbook",
        "year": "2023",
        "url": "https://library.laborlaw.ph/resources/",
        "short_name": "DOLE Handbook"
    },
    "DOLE-Covid-Protocols.txt": {
        "source": "DOLE COVID-19 Workplace Protocols",
        "doc_type": "guidelines",
        "year": "2020",
        "url": "https://www.dole.gov.ph/covid-19-labor-advisories/",
        "short_name": "COVID-19 Protocols"
    }
}


class KnowledgeBaseIngester:
    """Handles ingestion of legal documents into vector store."""
    
    def __init__(
        self,
        embeddings_adapter,
        vectorstore_adapter,
        chunker: Optional[LegalDocumentChunker] = None,
        loader: Optional[TextFileLoader] = None
    ):
        """
        Initialize ingester.
        
        Args:
            embeddings_adapter: Embeddings adapter instance
            vectorstore_adapter: Vector store adapter instance
            chunker: Document chunker (optional)
            loader: Text file loader (optional)
        """
        self.embeddings = embeddings_adapter
        self.vectorstore = vectorstore_adapter
        self.chunker = chunker or LegalDocumentChunker(
            min_chunk_words=100,
            max_chunk_words=300,
            overlap_words=20
        )
        self.loader = loader or TextFileLoader()
    
    async def ingest_file(
        self,
        file_path: Path,
        dry_run: bool = False
    ) -> dict:
        """
        Ingest a single file into vector store.
        
        Args:
            file_path: Path to text file
            dry_run: If True, only simulate ingestion
            
        Returns:
            Dictionary with ingestion statistics
        """
        try:
            logger.info(f"Processing file: {file_path.name}")
            
            # Get metadata from registry
            metadata = DOCUMENT_REGISTRY.get(file_path.name)
            if not metadata:
                logger.warning(
                    f"No metadata found for {file_path.name}. "
                    "Using default metadata."
                )
                metadata = {
                    "source": file_path.stem,
                    "doc_type": "unknown",
                    "url": "",
                    "short_name": file_path.stem
                }
            
            # Load document
            content = self.loader.load(file_path)
            
            # Chunk document
            chunks = self.chunker.chunk_document(
                content=content,
                source=metadata["source"],
                doc_type=metadata["doc_type"],
                base_url=metadata.get("url"),
                year=metadata.get("year"),
                short_name=metadata.get("short_name")
            )
            
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would create {len(chunks)} chunks "
                    f"for {file_path.name}"
                )
                return {
                    "file": file_path.name,
                    "chunks": len(chunks),
                    "status": "dry_run"
                }
            
            # Generate embeddings in batches
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [chunk.content for chunk in chunks]
            
            batch_response = await self.embeddings.embed_batch(
                texts=texts,
                batch_size=100
            )
            
            # Create documents for vector store
            documents = []
            for chunk, embedding in zip(chunks, batch_response.embeddings):
                doc = Document(
                    id=chunk.id,
                    content=chunk.content,
                    embedding=embedding,
                    metadata=chunk.metadata
                )
                documents.append(doc)
            
            # Upsert to vector store
            logger.info(f"Upserting {len(documents)} documents to vector store...")
            await self.vectorstore.upsert(documents)
            
            logger.info(
                f"✓ Successfully ingested {file_path.name}: "
                f"{len(chunks)} chunks, {batch_response.total_tokens_used} tokens"
            )
            
            return {
                "file": file_path.name,
                "chunks": len(chunks),
                "tokens": batch_response.total_tokens_used,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest {file_path.name}: {str(e)}", exc_info=True)
            return {
                "file": file_path.name,
                "status": "failed",
                "error": str(e)
            }
    
    async def ingest_all(
        self,
        docs_dir: Path,
        dry_run: bool = False
    ) -> dict:
        """
        Ingest all registered documents from directory.
        
        Args:
            docs_dir: Directory containing documents
            dry_run: If True, only simulate ingestion
            
        Returns:
            Dictionary with overall statistics
        """
        results = []
        total_chunks = 0
        total_tokens = 0
        successful = 0
        failed = 0
        
        for filename in DOCUMENT_REGISTRY.keys():
            file_path = docs_dir / filename
            
            if not file_path.exists():
                logger.warning(f"File not found: {filename} (skipping)")
                results.append({
                    "file": filename,
                    "status": "not_found"
                })
                failed += 1
                continue
            
            result = await self.ingest_file(file_path, dry_run=dry_run)
            results.append(result)
            
            if result["status"] == "success":
                successful += 1
                total_chunks += result["chunks"]
                total_tokens += result.get("tokens", 0)
            elif result["status"] == "dry_run":
                total_chunks += result["chunks"]
            else:
                failed += 1
        
        summary = {
            "total_files": len(DOCUMENT_REGISTRY),
            "successful": successful,
            "failed": failed,
            "total_chunks": total_chunks,
            "total_tokens": total_tokens,
            "results": results
        }
        
        logger.info(
            f"\n{'='*60}\n"
            f"Ingestion Summary:\n"
            f"  Files processed: {successful}/{len(DOCUMENT_REGISTRY)}\n"
            f"  Total chunks: {total_chunks}\n"
            f"  Total tokens: {total_tokens}\n"
            f"  Failed: {failed}\n"
            f"{'='*60}"
        )
        
        return summary


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest Philippine labor law documents into vector store"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to single file to ingest"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all registered documents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate ingestion without writing to vector store"
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="kb/docs",
        help="Directory containing knowledge base documents (default: kb/docs)"
    )
    
    args = parser.parse_args()
    
    if not args.file and not args.all:
        parser.error("Must specify either --file or --all")
    
    try:
        # Initialize adapters
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        
        # Create ingester
        ingester = KnowledgeBaseIngester(
            embeddings_adapter=embeddings,
            vectorstore_adapter=vectorstore
        )
        
        docs_dir = Path(args.docs_dir)
        
        if args.file:
            # Ingest single file
            file_path = Path(args.file)
            if not file_path.exists():
                logger.error(f"File not found: {args.file}")
                sys.exit(1)
            
            result = await ingester.ingest_file(file_path, dry_run=args.dry_run)
            
            if result["status"] == "failed":
                sys.exit(1)
        else:
            # Ingest all
            summary = await ingester.ingest_all(docs_dir, dry_run=args.dry_run)
            
            if summary["failed"] > 0:
                sys.exit(1)
        
        logger.info("✓ Knowledge base ingestion completed successfully")
        
    except KeyboardInterrupt:
        logger.info("\nIngestion cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
