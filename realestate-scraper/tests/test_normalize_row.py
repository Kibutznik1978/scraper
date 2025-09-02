from pathlib import Path
import json

from rscraper.amenities import load_vocab
from rscraper.normalize import to_listing_row

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
VOCAB_PATH = Path(__file__).resolve().parent.parent / "data" / "amenity_vocab.json"


def test_to_listing_row_normalizes_fields():
    vocab = load_vocab(VOCAB_PATH)
    raw = json.loads((FIXTURE_DIR / "listing_raw.json").read_text())
    fallbacks = {"city": "FallbackVille", "state": "CA"}

    row = to_listing_row(raw, "http://example.com/1", vocab, fallbacks)

    assert row.mls_id == "MLS123"
    assert row.address == "123 Main St"
    assert row.city == "FallbackVille"
    assert row.state == "CA"
    assert row.zip == "12345"
    assert row.beds == 3
    assert row.baths == 2.5
    assert row.sqft == 1234
    assert row.lot_size_acres == 0.5
    assert row.lot_size_sqft == 21780
    assert row.price == 350000
    assert row.year_built == 1999
    assert row.property_type == "Single Family"
    assert row.amenities == ["garage", "pool", "solar"]
    assert "solar panels" in row.description.lower()
