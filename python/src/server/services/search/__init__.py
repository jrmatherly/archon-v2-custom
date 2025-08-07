"""
Search Services

Handles vector search operations for documents and code.
"""

from .search_services import SearchService
from .vector_search_service import search_code_examples, search_documents

__all__ = [
    # Service classes
    "SearchService",
    # Search utilities
    "search_documents",
    "search_code_examples",
]
