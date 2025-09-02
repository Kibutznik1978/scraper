"""Amenity vocabulary utilities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set

import logging


logger = logging.getLogger(__name__)


def load_vocab(path: str | Path) -> Dict[str, List[str]]:
    """Load amenity vocabulary mapping canonical labels to synonyms."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sanitize(text: str) -> str:
    """Normalize whitespace and punctuation for matching."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _reverse_vocab(vocab: Dict[str, List[str]]) -> Dict[str, str]:
    """Build mapping from sanitized synonym to canonical label."""
    reverse: Dict[str, str] = {}
    for canon, syns in vocab.items():
        canonical = canon.strip()
        reverse[_sanitize(canonical)] = canonical
        for syn in syns:
            reverse[_sanitize(syn)] = canonical
    return reverse


def normalize_amenities(
    raw_tokens: Iterable[str],
    vocab: Dict[str, List[str]],
    description: str | None = None,
) -> List[str]:
    """Normalize raw amenity strings to canonical labels.

    Parameters
    ----------
    raw_tokens:
        Iterable of amenity strings scraped from structured fields.
    vocab:
        Mapping of canonical labels to lists of synonyms.
    description:
        Optional free-text description to scan for amenities.
    """
    reverse = _reverse_vocab(vocab)
    found: Set[str] = set()

    for token in raw_tokens:
        key = _sanitize(token)
        if key in reverse:
            canon = reverse[key]
            logger.debug("Amenity matched: %s -> %s", token, canon)
            found.add(canon)

    if description:
        text = _sanitize(description)
        for syn, canon in reverse.items():
            if re.search(rf"\b{re.escape(syn)}\b", text):
                logger.debug("Amenity matched from description: %s", canon)
                found.add(canon)

    return sorted(found)


__all__ = ["load_vocab", "normalize_amenities"]
