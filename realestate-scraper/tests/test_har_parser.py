from pathlib import Path

from rscraper.har_parser import iter_har_entries, candidate_json_bodies, extract_listings_from_json

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.har"


def test_har_parser_finds_many_listings():
    entries = list(iter_har_entries(FIXTURE))
    bodies = list(candidate_json_bodies(entries))
    assert len(bodies) == 1
    url, obj = bodies[0]
    listings = extract_listings_from_json(url, obj)
    assert len(listings) >= 10
    first = listings[0]
    assert "address" in first and "beds" in first
