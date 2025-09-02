"""HTML parsing utilities using Selectolax."""

from selectolax.parser import HTMLParser


def parse_html(html: str) -> HTMLParser:
    """Parse raw HTML into a Selectolax tree."""
    return HTMLParser(html)
