import json
from pathlib import Path

from rscraper.cli import export_sft_dpo
from rscraper.csv_writer import CSVWriter
from rscraper.normalize import ListingRow


def _write_sample_csv(path: Path) -> None:
    row = ListingRow(
        source_url="http://example.com/1",
        mls_id="MLS1",
        address="123 Main St",
        city="Townsville",
        state="CA",
        zip="12345",
        beds=3,
        baths=2,
        sqft=1500,
        lot_size_sqft=5000,
        year_built=2000,
        property_type="single family",
        price=350000,
        amenities=["garage", "solar"],
        description="Nice home",
    )
    writer = CSVWriter(path)
    writer.write(row)
    writer.close()


def test_export_sft_dpo(tmp_path):
    csv_path = tmp_path / "listings.csv"
    _write_sample_csv(csv_path)
    sft_path = tmp_path / "sft.jsonl"
    dpo_path = tmp_path / "dpo.jsonl"
    export_sft_dpo(csv_path, sft_path, dpo_path)
    sft_lines = sft_path.read_text().strip().splitlines()
    dpo_lines = dpo_path.read_text().strip().splitlines()
    assert len(sft_lines) == 1
    assert len(dpo_lines) == 1
    sft_obj = json.loads(sft_lines[0])
    assert sft_obj["messages"][0]["role"] == "system"
    assistant = sft_obj["messages"][2]["content"]
    assert "123 Main St" in assistant
    assert "ocean view" not in assistant
    dpo_obj = json.loads(dpo_lines[0])
    assert set(dpo_obj.keys()) == {"prompt", "chosen", "rejected"}
    assert "ocean view" in dpo_obj["rejected"]
    assert "ocean view" not in dpo_obj["chosen"]
