from pathlib import Path

from rscraper.cli import validate_csv
from rscraper.csv_writer import CSVWriter
from rscraper.normalize import ListingRow


def _write_csv(path: Path) -> None:
    rows = [
        ListingRow(
            source_url="http://example.com/1",
            mls_id="MLS1",
            address="123 Main St",
            city="Townsville",
            state="CA",
            zip="12345",
            beds=3,
            baths=2,
            sqft=1500,
            amenities=["garage", "solar"],
            description="Solar home",
        ),
        ListingRow(
            source_url="http://example.com/2",
            mls_id="MLS2",
            address="456 Oak Ave",
            city="Townsville",
            state="CA",
            zip="12345",
            sqft=1000,
            amenities=["EV charger"],
            description="EV ready",
        ),
        ListingRow(
            source_url="http://example.com/3",
            mls_id="MLS3",
            address="",
            city="",
            state="",
            zip="12345",
            beds=2,
            baths=1,
            description="No address",
        ),
    ]
    writer = CSVWriter(path)
    for r in rows:
        writer.write(r)
    writer.close()


def test_validate_csv(tmp_path, capsys):
    csv_path = tmp_path / "listings.csv"
    _write_csv(csv_path)
    validate_csv(csv_path)
    out = capsys.readouterr().out
    assert "Total rows: 3" in out
    assert "Beds present: 66.7%" in out
    assert "Amenities non-empty: 66.7%" in out
    assert "Top amenities" in out and "solar" in out and "EV charger" in out
    assert "Missing address or city/state: 1" in out
    assert "Example row with solar" in out
    assert "Example row with EV charger" in out
