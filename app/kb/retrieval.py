"""Retrieval subsystem for Knowledge Base (Level A LLM linking + keyword fallback).

Unified entry point: find_related().
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AIClient, AIResult
from app.ai.prompts.link import PROMPT_VERSION, build_prompt, build_system_prompt
from app.ai.schemas import LinkResult
from app.config import get_settings
from app.logging_config import log_event
from app.models.kb import KBDocument

logger = logging.getLogger("app.kb")


@dataclass
class KBMatch:
    document_id: int
    chunk_id: int | None
    score: float  # 0..1
    reason: str
    method: Literal["llm", "vector", "keyword", "manual"]


def find_related(
    db: Session,
    text: str,
    *,
    entity_type: str,
    entity_id: int | None = None,
    limit: int = 3,
) -> list[KBMatch]:
    """Retrieve relevant KB documents using the configured retriever chain.

    Fallback chain: vector (if configured) -> llm -> keyword.
    """
    settings = get_settings()
    retriever_name = settings.retriever.lower()
    start = time.monotonic()

    # Get candidate documents
    docs = list(
        db.scalars(select(KBDocument).order_by(KBDocument.updated_at.desc()).limit(50)).all()
    )

    if not docs:
        return []

    matches: list[KBMatch] = []
    active_retriever = "llm"

    # 1. Level A: LLM Summary Retriever (default)
    if retriever_name in ("llm", "vector"):
        try:
            matches = _llm_retrieve(text, entity_type=entity_type, docs=docs, limit=limit)
            active_retriever = "llm"
        except Exception as exc:
            logger.warning("LLM retrieval failed: %s; falling back to keyword", exc)
            matches = []

    # 2. Fallback to Keyword Retriever if LLM produced no matches or failed
    if not matches:
        matches = _keyword_retrieve(text, docs=docs, limit=limit)
        active_retriever = "keyword"

    latency = int((time.monotonic() - start) * 1000)
    log_event(
        logger,
        "kb.retrieval",
        retriever=active_retriever,
        matches=len(matches),
        latency_ms=latency,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return matches


def _llm_retrieve(
    text: str,
    *,
    entity_type: str,
    docs: list[KBDocument],
    limit: int,
) -> list[KBMatch]:
    """Link entity to documents using LLM summary catalogue matching."""
    catalogue = [
        {
            "id": doc.id,
            "title": doc.title,
            "summary": (doc.summary or doc.content[:300])[:300],
        }
        for doc in docs
    ]
    valid_ids = {d.id for d in docs}

    system = build_system_prompt()
    prompt = build_prompt(
        entity_text=text,
        entity_type=entity_type,
        catalogue=catalogue,
    )

    result: AIResult[LinkResult] = AIClient.run_structured(
        "link",
        system=system,
        prompt=prompt,
        model_cls=LinkResult,
        prompt_version=PROMPT_VERSION,
    )

    if not result.ok or not result.data:
        return []

    matches: list[KBMatch] = []
    for m in result.data.matches:
        if m.document_id in valid_ids and m.relevance >= 0.5:
            matches.append(
                KBMatch(
                    document_id=m.document_id,
                    chunk_id=None,
                    score=round(float(m.relevance), 2),
                    reason=m.reason or "AI suggested match based on context",
                    method="llm",
                )
            )
        if len(matches) >= limit:
            break

    return matches


_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "in",
        "out",
        "on",
        "off",
        "over",
        "under",
        "again",
        "further",
        "once",
        "here",
        "there",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "this",
        "that",
        "these",
        "those",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
    }
)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
    return {w for w in words if w not in _STOP_WORDS}


def _keyword_retrieve(
    text: str,
    *,
    docs: list[KBDocument],
    limit: int,
) -> list[KBMatch]:
    """Deterministic token overlap matching as a robust offline fallback."""
    query_tokens = _tokenize(text)
    if not query_tokens:
        return []

    scored: list[tuple[float, KBDocument, str]] = []

    for doc in docs:
        title_tokens = _tokenize(doc.title)
        summary_tokens = _tokenize(doc.summary or "")
        content_tokens = _tokenize(doc.content[:1000])

        doc_tokens = title_tokens | summary_tokens | content_tokens
        overlap = query_tokens & doc_tokens

        if overlap:
            # Title matches have higher weight
            title_overlap = query_tokens & title_tokens
            score = (len(overlap) + len(title_overlap) * 2.0) / (len(query_tokens) + 2.0)
            score = min(round(score, 2), 1.0)
            reason = f"Keyword match on: {', '.join(sorted(list(overlap))[:3])}"
            scored.append((score, doc, reason))

    scored.sort(key=lambda x: x[0], reverse=True)

    matches: list[KBMatch] = []
    for score, doc, reason in scored[:limit]:
        matches.append(
            KBMatch(
                document_id=doc.id,
                chunk_id=None,
                score=score,
                reason=reason,
                method="keyword",
            )
        )

    return matches
