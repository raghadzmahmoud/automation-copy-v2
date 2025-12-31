#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Minimal Content Extractor stub

This file provides a lightweight `ContentExtractor`, `ExtractionResult`, and
`extract_and_prepare_news` so imports succeed while developing or testing.

This is intentionally simple — it treats the provided `content` as plain text
and returns one or more lightweight news dicts. Replace with a proper
implementation (LLM or heuristics) as needed.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ExtractionResult:
    success: bool
    title: Optional[str] = None
    clean_text: Optional[str] = None
    images: Optional[List[str]] = None
    error_message: Optional[str] = None


class ContentExtractor:
    """Simple extractor that returns the whole input as cleaned text."""

    def __init__(self):
        pass

    def extract(self, content: str) -> ExtractionResult:
        if not content:
            return ExtractionResult(success=False, error_message="Empty content")

        # Basic title heuristic: first non-empty line
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        title = lines[0] if lines else None

        return ExtractionResult(
            success=True,
            title=title,
            clean_text=content,
            images=[]
        )


def extract_and_prepare_news(
    content: str,
    source_url: str,
    source_id: int,
    language_id: int = 1,
    available_images: Optional[List[str]] = None,
    max_articles: int = 10,
) -> List[Dict]:
    """
    Very small heuristic to split the combined content into news items.

    - If the content contains multiple paragraphs separated by blank lines,
      treat each paragraph as a candidate article, up to `max_articles`.
    - Returns a list of dicts compatible with `save_news_to_db` usage in
      `manual_scraper.py` (keys: title, content_text, tags, source_id, etc.).
    """
    if not content:
        return []

    chunks = [p.strip() for p in content.split('\n\n') if p.strip()]
    if not chunks:
        chunks = [content.strip()]

    news_items: List[Dict] = []
    for chunk in chunks[:max_articles]:
        title = chunk.splitlines()[0][:120] if chunk else ''
        news = {
            'title': title,
            'content_text': chunk,
            'content_img': available_images[0] if available_images else '',
            'content_video': '',
            'tags': '',
            'source_id': source_id,
            'language_id': language_id,
            'category_name': 'General',
        }
        news_items.append(news)

    return news_items