"""High-level scraping pipeline."""

import asyncio
from typing import Any

from .config import Settings
from .http import fetch
from .parser import parse_html
from .normalize import normalize_records


async def run_pipeline(url: str) -> Any:
    """Fetch, parse, and normalize data from a URL."""
    html = await fetch(url)
    tree = parse_html(html)
    # Placeholder extraction logic
    data = [{"raw_html_length": len(tree.html)}]
    df = normalize_records(data)
    return df


def run(url: str) -> Any:
    """Synchronous wrapper around ``run_pipeline``."""
    return asyncio.run(run_pipeline(url))
