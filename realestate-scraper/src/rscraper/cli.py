"""Command-line interface for converting HAR files into normalized listings."""

from __future__ import annotations

import ast
import csv
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Mapping

import typer

from .amenities import load_vocab
from .config import settings
from .csv_writer import CSVWriter
from .har_parser import (
    candidate_json_bodies,
    extract_listings_from_json,
    iter_har_entries,
)
from .normalize import ListingRow, to_listing_row

app = typer.Typer(name="har2listings", help="Parse HAR files into CSV listings")

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )


def _process_har(
    har_path: Path,
    writer: CSVWriter,
    vocab,
    fallbacks,
) -> tuple[int, int, int]:
    """Parse a single HAR file and append listings to ``writer``.

    Returns a tuple of ``(candidates, written, deduped)``.
    """
    candidates = written = deduped = 0
    entries = iter_har_entries(har_path)
    for url, obj in candidate_json_bodies(entries):
        for raw in extract_listings_from_json(url, obj):
            candidates += 1
            try:
                row: ListingRow = to_listing_row(raw, url, vocab, fallbacks)
                if writer.write(row):
                    written += 1
                else:
                    deduped += 1
            except Exception:
                logger.exception("Normalization failed for %s", url)
    return candidates, written, deduped


@app.command()
def parse(
    har: Path = typer.Option(..., help="Path to a HAR file"),
    out: Path = typer.Option(
        settings.OUTPUT_CSV, "--out", help="Output CSV path"
    ),
    log_level: str = typer.Option(settings.LOG_LEVEL, "--log-level", help="Logging level"),
) -> None:
    """Parse a single HAR file into a CSV (append-safe)."""
    _setup_logging(log_level)
    vocab = load_vocab(settings.AMENITY_VOCAB_PATH)
    fallbacks = {"city": settings.CITY_FALLBACK, "state": settings.STATE_FALLBACK}
    writer = CSVWriter(out)
    try:
        cand, written, deduped = _process_har(har, writer, vocab, fallbacks)
        logger.info(
            "Processed %s: candidates=%s written=%s deduped=%s",
            har,
            cand,
            written,
            deduped,
        )
    finally:
        writer.close()


@app.command("parse-dir")
def parse_dir(
    har_dir: Path = typer.Option(
        settings.INPUT_HAR_DIR, "--har-dir", help="Directory containing HAR files"
    ),
    out: Path = typer.Option(
        settings.OUTPUT_CSV, "--out", help="Output CSV path"
    ),
    log_level: str = typer.Option(settings.LOG_LEVEL, "--log-level", help="Logging level"),
) -> None:
    """Parse all ``.har`` files in a directory."""
    _setup_logging(log_level)
    vocab = load_vocab(settings.AMENITY_VOCAB_PATH)
    fallbacks = {"city": settings.CITY_FALLBACK, "state": settings.STATE_FALLBACK}
    writer = CSVWriter(out)
    total_cand = total_written = total_dedup = files = 0
    try:
        for har in sorted(Path(har_dir).glob("*.har")):
            files += 1
            cand, written, dedup = _process_har(har, writer, vocab, fallbacks)
            total_cand += cand
            total_written += written
            total_dedup += dedup
        logger.info(
            "Processed %s files: candidates=%s written=%s deduped=%s",
            files,
            total_cand,
            total_written,
            total_dedup,
        )
    finally:
        writer.close()


@app.command()
def sample(
    har: Path = typer.Option(..., help="Path to a HAR file"),
    limit: int = typer.Option(3, help="Number of raw listings to show"),
    log_level: str = typer.Option(settings.LOG_LEVEL, "--log-level", help="Logging level"),
) -> None:
    """Print the first few candidate raw listing dictionaries."""
    _setup_logging(log_level)
    count = 0
    for url, obj in candidate_json_bodies(iter_har_entries(har)):
        for raw in extract_listings_from_json(url, obj):
            typer.echo(json.dumps(raw, indent=2, sort_keys=True))
            typer.echo()
            count += 1
            if count >= limit:
                return


@app.command("validate-csv")
def validate_csv(
    csv_path: Path = typer.Option(
        settings.OUTPUT_CSV, "--csv", help="Listings CSV path"
    ),
    log_level: str = typer.Option(settings.LOG_LEVEL, "--log-level", help="Logging level"),
) -> None:
    """Print basic quality-control stats for a listings CSV."""
    _setup_logging(log_level)
    total = 0
    counts = {"beds": 0, "baths": 0, "sqft": 0, "amenities": 0}
    amenity_counter: Counter[str] = Counter()
    missing: list[dict] = []
    solar_example: dict | None = None
    ev_example: dict | None = None

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if row.get("beds"):
                counts["beds"] += 1
            if row.get("baths"):
                counts["baths"] += 1
            if row.get("sqft"):
                counts["sqft"] += 1

            tokens: list[str] = []
            am_raw = row.get("amenities")
            if am_raw:
                try:
                    parsed = ast.literal_eval(am_raw)
                    if isinstance(parsed, list):
                        tokens = [str(t) for t in parsed]
                except Exception:
                    tokens = []
            if tokens:
                counts["amenities"] += 1
                for t in tokens:
                    amenity_counter[t] += 1
                if solar_example is None and "solar" in tokens:
                    solar_example = row
                if ev_example is None and "EV charger" in tokens:
                    ev_example = row

            if not row.get("address") or not (row.get("city") and row.get("state")):
                missing.append(row)

    typer.echo(f"Total rows: {total}")
    if total == 0:
        return
    for field in ("beds", "baths", "sqft"):
        pct = counts[field] / total * 100
        typer.echo(f"{field.capitalize()} present: {pct:.1f}%")
    pct_am = counts["amenities"] / total * 100
    typer.echo(f"Amenities non-empty: {pct_am:.1f}%")

    typer.echo("Top amenities:")
    for amenity, count in amenity_counter.most_common(10):
        typer.echo(f"- {amenity}: {count}")

    if missing:
        typer.echo(f"Missing address or city/state: {len(missing)} rows")
        for row in missing[:5]:
            typer.echo(
                f"  - source_url={row.get('source_url')} address={row.get('address')} city={row.get('city')} state={row.get('state')}"
            )
    else:
        typer.echo("No missing address or city/state")

    if solar_example:
        typer.echo("Example row with solar:")
        typer.echo(json.dumps(solar_example, indent=2))
    if ev_example:
        typer.echo("Example row with EV charger:")
        typer.echo(json.dumps(ev_example, indent=2))


SFT_SYSTEM = (
    "Write a real estate listing using only the provided fields. If a detail isn't provided, omit it."
)


def _user_content(row: Mapping) -> str:
    parts: List[str] = []
    for key in [
        "address",
        "city",
        "state",
        "beds",
        "baths",
        "sqft",
        "lot_size_sqft",
        "year_built",
        "property_type",
    ]:
        val = row.get(key)
        if val not in (None, ""):
            parts.append(f"{key}={val}")
    am = row.get("amenities")
    if am:
        parts.append(f"amenities={am}")
    return "; ".join(parts)


def _assistant_text(row: Mapping) -> str:
    """Generate a simple grounded paragraph from ``row``."""
    sentences: List[str] = []
    addr_bits = []
    if row.get("property_type"):
        addr_bits.append(f"This {row['property_type']}")
    else:
        addr_bits.append("This property")
    if row.get("address") and row.get("city") and row.get("state"):
        addr_bits.append(
            f"is located at {row['address']}, {row['city']}, {row['state']}"
        )
    elif row.get("address"):
        addr_bits.append(f"is located at {row['address']}")
    bedbath = []
    if row.get("beds"):
        bedbath.append(f"{row['beds']} beds")
    if row.get("baths"):
        bedbath.append(f"{row['baths']} baths")
    if bedbath:
        addr_bits.append("offering " + " and ".join(bedbath))
    if addr_bits:
        sentences.append(" ".join(addr_bits) + ".")
    feat_bits = []
    if row.get("sqft"):
        feat_bits.append(f"{row['sqft']} sqft")
    if row.get("lot_size_sqft"):
        feat_bits.append(f"on a {row['lot_size_sqft']} sqft lot")
    if row.get("year_built"):
        feat_bits.append(f"built in {row['year_built']}")
    if feat_bits:
        sentences.append("It features " + ", ".join(feat_bits) + ".")
    if row.get("amenities"):
        sentences.append(
            "Amenities include " + ", ".join(row["amenities"]) + "."
        )
    if not sentences:
        sentences.append("Details forthcoming.")
    return " ".join(sentences)


INVENTED = [
    "ocean view",
    "chef's kitchen",
    "spa-like baths",
    "home theater",
    "rooftop deck",
]


def _make_rejected(chosen: str, row: Mapping) -> str | None:
    amenities = set(row.get("amenities") or [])
    for detail in INVENTED:
        if detail not in amenities:
            return chosen + f" It also has {detail}."
    if row.get("sqft"):
        try:
            sqft = int(float(row["sqft"]))
            return chosen.replace(f"{sqft} sqft", f"{sqft + 30} sqft")
        except Exception:
            return None
    return None


@app.command("export-sft-dpo")
def export_sft_dpo(
    csv_path: Path = typer.Option(
        settings.OUTPUT_CSV, "--csv", help="Input listings CSV"
    ),
    sft: Path = typer.Option(Path("./out/sft.jsonl"), help="Output SFT JSONL path"),
    dpo: Path = typer.Option(Path("./out/dpo.jsonl"), help="Output DPO JSONL path"),
    log_level: str = typer.Option(settings.LOG_LEVEL, "--log-level", help="Logging level"),
) -> None:
    """Export SFT and DPO datasets from a listings CSV."""
    _setup_logging(log_level)
    sft.parent.mkdir(parents=True, exist_ok=True)
    dpo.parent.mkdir(parents=True, exist_ok=True)
    with (
        csv_path.open("r", newline="", encoding="utf-8") as f,
        sft.open("w", encoding="utf-8") as sft_f,
        dpo.open("w", encoding="utf-8") as dpo_f,
    ):
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            amenities = []
            am = row.get("amenities")
            if am:
                try:
                    amenities = ast.literal_eval(am)
                except Exception:
                    amenities = []
            row["amenities"] = amenities
            user = _user_content(row)
            chosen = _assistant_text(row)
            rejected = _make_rejected(chosen, row)
            if rejected is None or rejected == chosen:
                continue
            sft_obj = {
                "messages": [
                    {"role": "system", "content": SFT_SYSTEM},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": chosen},
                ]
            }
            dpo_obj = {
                "prompt": f"{SFT_SYSTEM}\n{user}",
                "chosen": chosen,
                "rejected": rejected,
            }
            sft_f.write(json.dumps(sft_obj, ensure_ascii=False) + "\n")
            dpo_f.write(json.dumps(dpo_obj, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    app()
