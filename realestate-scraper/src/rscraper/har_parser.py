"""Utilities to parse HAR files and extract listing candidates."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterable, Iterator, Tuple, Any, Dict, List

import logging

# Prefer orjson for speed; fall back to json if unavailable
try:  # pragma: no cover - fallback only when orjson missing
    import orjson  # type: ignore
except Exception:  # pragma: no cover
    import json as orjson  # type: ignore


# ---------------------------------------------------------------------------
# HAR parsing
# ---------------------------------------------------------------------------

def iter_har_entries(path: str | Path) -> Iterator[Dict[str, Any]]:
    """Yield entries from a HAR file located at ``path``."""

    with open(path, "rb") as f:
        data = orjson.loads(f.read())
    for entry in data.get("log", {}).get("entries", []):
        yield entry


# ---------------------------------------------------------------------------
# Candidate JSON bodies
# ---------------------------------------------------------------------------

_KEYWORDS = ["api", "graphql", "property", "detail", "results", "search"]

logger = logging.getLogger(__name__)


def candidate_json_bodies(entries: Iterable[Dict[str, Any]]) -> Iterator[Tuple[str, Any]]:
    """Yield ``(url, json_obj)`` pairs for interesting entries."""

    for entry in entries:
        req = entry.get("request", {})
        method = req.get("method")
        if method not in {"GET", "POST"}:
            continue
        url: str = req.get("url", "")
        if not any(kw in url.lower() for kw in _KEYWORDS):
            continue
        content = entry.get("response", {}).get("content", {})
        mime = (content.get("mimeType") or "").lower()
        if "json" not in mime and "javascript" not in mime:
            continue
        text = content.get("text")
        if not text:
            continue
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode()
            except Exception:
                continue
        try:
            obj = orjson.loads(text)
        except Exception:
            continue
        logger.debug("Matched JSON body from %s", url)
        yield url, obj


# ---------------------------------------------------------------------------
# Extract listings
# ---------------------------------------------------------------------------

_ADDR_KEYS = {"address", "street", "city", "state", "postal", "zip", "zipcode"}
_LISTING_KEYS = {
    "beds",
    "bedrooms",
    "baths",
    "bathrooms",
    "sqft",
    "area",
    "lot",
    "yearbuilt",
    "propertytype",
    "price",
    "description",
    "remarks",
}


def extract_listings_from_json(url: str, obj: Any) -> List[Dict[str, Any]]:
    """Return a list of dicts that look like property listings."""

    found: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            keys = {k.lower() for k in node.keys()}
            if keys & _ADDR_KEYS and keys & _LISTING_KEYS:
                logger.debug("Extracted keys %s from %s", sorted(keys), url)
                found.append(node)
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found
