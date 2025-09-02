"""HTTP utilities for network access with rate limiting and caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from .config import settings

# ---------------------------------------------------------------------------
# HTTP client setup
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a singleton ``httpx.AsyncClient`` configured for the project."""

    global _client
    if _client is None:
        headers = {"User-Agent": settings.USER_AGENT}
        _client = httpx.AsyncClient(
            headers=headers,
            timeout=settings.TIMEOUT_S,
            follow_redirects=True,
            proxies=settings.PROXY_URL,
        )
    return _client


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_rate_lock = asyncio.Lock()
_last_request = 0.0


async def _rate_limit() -> None:
    """Throttle requests based on ``RATE_LIMIT_RPS`` and add jitter."""

    global _last_request
    async with _rate_lock:
        min_interval = 1.0 / settings.RATE_LIMIT_RPS if settings.RATE_LIMIT_RPS else 0
        elapsed = time.monotonic() - _last_request
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_request = time.monotonic()
    # random small sleep to desynchronise bursts
    await asyncio.sleep(random.uniform(0, 0.1))


# ---------------------------------------------------------------------------
# Response caching using ETag / Last-Modified headers
# ---------------------------------------------------------------------------

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)


def _cache_paths(url: str) -> Tuple[Path, Path]:
    key = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / key, CACHE_DIR / f"{key}.json"


# ---------------------------------------------------------------------------
# robots.txt handling
# ---------------------------------------------------------------------------

_robots: Dict[str, robotparser.RobotFileParser] = {}


async def is_allowed(url: str) -> bool:
    """Check robots.txt rules for the given URL, caching results per host."""

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots.get(base)
    if rp is None:
        robots_url = urljoin(base, "/robots.txt")
        client = _get_client()
        try:
            resp = await client.get(robots_url)
            text = resp.text if resp.status_code == 200 else ""
        except httpx.RequestError:
            text = ""
        rp = robotparser.RobotFileParser()
        rp.parse(text.splitlines())
        _robots[base] = rp
    return rp.can_fetch(settings.USER_AGENT, url)


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


def _retryable(exc: Exception) -> bool:
    """Return ``True`` if the exception warrants a retry."""

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return isinstance(exc, httpx.RequestError)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception(_retryable),
    wait=wait_random_exponential(multiplier=1, max=10),
    stop=stop_after_attempt(settings.RETRY_MAX),
    reraise=True,
)
async def fetch(url: str) -> Tuple[int, str, str, bool]:
    """Fetch ``url`` and return ``(status, text, final_url, from_cache)``."""

    if not await is_allowed(url):
        raise PermissionError(f"Disallowed by robots.txt: {url}")

    await _rate_limit()

    cache_file, meta_file = _cache_paths(url)
    headers = {}
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        if etag := meta.get("etag"):
            headers["If-None-Match"] = etag
        if last := meta.get("last_modified"):
            headers["If-Modified-Since"] = last

    client = _get_client()
    try:
        resp = await client.get(url, headers=headers)
    except httpx.RequestError as exc:  # retried via tenacity
        raise exc

    if resp.status_code in {429} or 500 <= resp.status_code < 600:
        raise httpx.HTTPStatusError(
            "retryable status", request=resp.request, response=resp
        )

    if resp.status_code == httpx.codes.NOT_MODIFIED and cache_file.exists():
        text = cache_file.read_text()
        return resp.status_code, text, str(resp.url), True

    text = resp.text
    if resp.status_code == 200:
        cache_file.write_text(text)
        meta: Dict[str, str] = {}
        if etag := resp.headers.get("ETag"):
            meta["etag"] = etag
        if last := resp.headers.get("Last-Modified"):
            meta["last_modified"] = last
        if meta:
            meta_file.write_text(json.dumps(meta))
    return resp.status_code, text, str(resp.url), False


__all__ = ["fetch", "is_allowed"]

