from pathlib import Path

from rscraper.amenities import load_vocab, normalize_amenities


VOCAB_PATH = Path(__file__).resolve().parent.parent / "data" / "amenity_vocab.json"


def test_normalize_from_tokens() -> None:
    vocab = load_vocab(VOCAB_PATH)
    raw = ["Two car garage", "chef’s kitchen", "Solar Panels"]
    assert normalize_amenities(raw, vocab) == ["garage", "solar"]


def test_extract_from_description() -> None:
    vocab = load_vocab(VOCAB_PATH)
    raw: list[str] = []
    description = "Enjoy the balcony and in-unit laundry with a rooftop deck." \
        " Extra storage provided."
    assert normalize_amenities(raw, vocab, description) == [
        "balcony",
        "in-unit laundry",
        "rooftop deck",
    ]


def test_logging_matches(caplog) -> None:
    vocab = load_vocab(VOCAB_PATH)
    with caplog.at_level("DEBUG"):
        normalize_amenities(["Two car garage", "Solar Panels"], vocab)
    assert "Amenity matched" in caplog.text
