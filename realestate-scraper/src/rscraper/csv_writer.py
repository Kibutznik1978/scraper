"""CSV writer with deduplication support."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Tuple, Set, Mapping, TextIO

from .normalize import ListingRow

logger = logging.getLogger(__name__)

# Ordered list of ListingRow fields
FIELDS = [
    "source_url",
    "mls_id",
    "address",
    "city",
    "state",
    "zip",
    "beds",
    "baths",
    "rooms_total",
    "sqft",
    "year_built",
    "lot_size_sqft",
    "lot_size_acres",
    "property_type",
    "price",
    "amenities",
    "description",
]


def ensure_parent(path: Path) -> None:
    """Ensure the parent directory of ``path`` exists."""
    path.parent.mkdir(parents=True, exist_ok=True)


def open_writer(path: Path) -> Tuple[TextIO, csv.DictWriter]:
    """Open ``path`` for appending and return a DictWriter.

    The header is written if the file did not previously exist.
    """
    ensure_parent(path)
    exists = path.exists()
    fh = path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=FIELDS)
    if not exists:
        writer.writeheader()
    return fh, writer


class CSVWriter:
    """Append :class:`ListingRow` items to a CSV file with deduplication."""

    def __init__(self, path: Path, seen_path: Path | None = None):
        self.path = Path(path)
        self.seen_path = Path(seen_path) if seen_path else None
        self.fh, self.writer = open_writer(self.path)
        self.seen: Set[Tuple[str, str, str, str, str]] = set()
        # Load existing keys from CSV
        if self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.seen.add(self._key(row))
        # Load persisted seen keys if provided
        if self.seen_path and self.seen_path.exists():
            with self.seen_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        self.seen.add(tuple(row))
        elif self.seen_path:
            ensure_parent(self.seen_path)

    @staticmethod
    def _key(row: Mapping) -> Tuple[str, str, str, str, str]:
        return (
            row.get("address", ""),
            row.get("city", ""),
            row.get("state", ""),
            row.get("zip", ""),
            row.get("source_url", ""),
        )

    def write(self, listing: ListingRow) -> bool:
        """Write ``listing`` if not already seen.

        Returns ``True`` if the row was written, ``False`` if it was skipped.
        """
        data = listing.model_dump()
        key = self._key(data)
        if key in self.seen:
            logger.debug("Deduped row %s", key)
            return False
        self.seen.add(key)
        self.writer.writerow(data)
        logger.debug("Wrote row %s", key)
        if self.seen_path:
            with self.seen_path.open("a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(key)
        return True

    def close(self) -> None:
        self.fh.close()


__all__ = ["ensure_parent", "open_writer", "CSVWriter", "FIELDS"]
