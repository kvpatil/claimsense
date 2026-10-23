"""Retrieval over the policy clause corpus."""

from .bm25 import Retriever, retrieve  # noqa: F401

__all__ = ["Retriever", "retrieve"]
