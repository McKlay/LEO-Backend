"""
KB Processing Module - Tools for offline knowledge base preparation.

This module contains components that run during KB ingestion/preparation,
not during runtime chat operations.
"""

from .summarizer import ChunkSummarizer, ChunkSummary

__all__ = ["ChunkSummarizer", "ChunkSummary"]
