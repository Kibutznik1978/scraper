"""Data normalization helpers and models."""

from __future__ import annotations

import logging
import re
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from .amenities import normalize_amenities

logger = logging.getLogger(__name__)


def parse_float(val: object) -> Optional[float]:
    """Safely parse a float from heterogeneous representations.

    Strings may contain commas or extra characters. Returns ``None`` when
    parsing fails.
    """

    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^0-9.\-]", "", val.replace(",", ""))
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def parse_int(val: object) -> Optional[int]:
    """Parse an integer, delegating to :func:`parse_float`."""

    num = parse_float(val)
    return int(num) if num is not None else None


def _search(obj: object, predicate) -> Optional[object]:
    """Recursively search ``obj`` for a key satisfying ``predicate``."""

    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if predicate(k):
                return v
            result = _search(v, predicate)
            if result is not None:
                return result
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        for item in obj:
            result = _search(item, predicate)
            if result is not None:
                return result
    return None


def _search_keys(obj: Mapping, keys: Sequence[str]) -> Optional[object]:
    keyset = {k.lower() for k in keys}
    return _search(obj, lambda k: k.replace("_", "").replace("-", "").lower() in keyset)


def parse_bedrooms(d: Mapping) -> Optional[float]:
    val = _search_keys(d, ["beds", "bedrooms", "bed"])
    return parse_float(val)


def parse_bathrooms(d: Mapping) -> Optional[float]:
    val = _search_keys(d, ["baths", "bathrooms", "bath"])
    return parse_float(val)


def parse_sqft(d: Mapping) -> Optional[int]:
    keys = [
        "sqft",
        "livingarea",
        "livingareasqft",
        "finishedsqft",
        "finishedarea",
        "grosslivingsqft",
    ]
    val = _search(d, lambda k: any(key in k.replace("_", "").lower() for key in keys))
    return parse_int(val)


def parse_lot_sizes(d: Mapping) -> Tuple[Optional[int], Optional[float]]:
    sqft_val = _search(d, lambda k: "lot" in k.lower() and any(s in k.lower() for s in ("sqft", "area")))
    acres_val = _search(d, lambda k: "acre" in k.lower())

    lot_size_sqft = parse_int(sqft_val)
    lot_size_acres = parse_float(acres_val)

    if lot_size_sqft is None and lot_size_acres is not None:
        lot_size_sqft = int(lot_size_acres * 43560)
    elif lot_size_acres is None and lot_size_sqft is not None:
        lot_size_acres = lot_size_sqft / 43560

    return lot_size_sqft, lot_size_acres


def parse_address_block(d: Mapping) -> Tuple[str, str, str, str]:
    addr_obj = _search_keys(d, ["address"])
    address = city = state = zip_code = ""

    if isinstance(addr_obj, Mapping):
        address = (_search_keys(addr_obj, ["line1", "street", "address1"]) or "")
        city = (_search_keys(addr_obj, ["city", "cityname"]) or "")
        state = (_search_keys(addr_obj, ["state", "statecode", "province"]) or "")
        zip_code = (
            _search_keys(addr_obj, ["postalcode", "zipcode", "zip", "postal"]) or ""
        )
    elif isinstance(addr_obj, str):
        address = addr_obj

    if not city:
        city = _search_keys(d, ["city", "cityname"]) or ""
    if not state:
        state = _search_keys(d, ["state", "statecode", "province"]) or ""
    if not zip_code:
        zip_code = _search_keys(d, ["postalcode", "zipcode", "zip", "postal"]) or ""

    return str(address), str(city), str(state), str(zip_code)


def parse_price(d: Mapping) -> Optional[int]:
    val = _search(d, lambda k: "price" in k.lower())
    return parse_int(val)


def parse_year_built(d: Mapping) -> Optional[int]:
    val = _search_keys(d, ["yearbuilt", "built", "constructionyear"])
    return parse_int(val)


def parse_property_type(d: Mapping) -> str:
    val = _search(d, lambda k: "propertytype" in k.replace("_", "").lower() or k.lower() == "type" or k.lower() == "hometype")
    return str(val) if val is not None else ""


def parse_description(d: Mapping) -> str:
    val = _search(d, lambda k: any(s in k.replace("_", "").lower() for s in ("description", "remarks", "summary")))
    return str(val) if val is not None else ""


def parse_rooms_total(d: Mapping) -> Optional[float]:
    val = _search(d, lambda k: "room" in k.lower() and "total" in k.lower())
    return parse_float(val)


def collect_raw_amenities(d: Mapping, description_text: str | None) -> List[str]:
    tokens: List[str] = []

    def _extract(obj: object):
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                kl = k.lower()
                if any(word in kl for word in ("amenit", "feature")):
                    _extract(v)
                else:
                    _extract(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item)
        elif isinstance(obj, str):
            for part in re.split(r"[;,\n]", obj):
                part = part.strip()
                if part:
                    tokens.append(part)

    _extract(d)

    if description_text:
        for part in re.split(r"[;,\n]", description_text):
            part = part.strip()
            if part:
                tokens.append(part)

    return tokens


class ListingRow(BaseModel):
    """Normalized representation of a property listing."""

    # Core identifiers and location
    source_url: str
    mls_id: str
    address: str
    city: str
    state: str
    zip: str

    # Basic details
    beds: Optional[float] = None
    baths: Optional[float] = None
    rooms_total: Optional[float] = None
    sqft: Optional[int] = None
    year_built: Optional[int] = None
    lot_size_sqft: Optional[int] = None
    lot_size_acres: Optional[float] = None
    property_type: str = ""
    price: Optional[int] = None

    # Extra info
    amenities: List[str] = Field(default_factory=list)
    description: str = ""


def to_listing_row(
    raw_dict: Mapping,
    source_url: str,
    vocab: Mapping[str, List[str]],
    fallbacks: Mapping[str, Optional[str]],
) -> ListingRow:
    """Transform a raw dictionary into a :class:`ListingRow`."""

    description = parse_description(raw_dict)
    raw_tokens = collect_raw_amenities(raw_dict, description)
    amenities = normalize_amenities(raw_tokens, vocab, description)

    lot_size_sqft, lot_size_acres = parse_lot_sizes(raw_dict)
    address, city, state, zip_code = parse_address_block(raw_dict)

    beds = parse_bedrooms(raw_dict)
    baths = parse_bathrooms(raw_dict)
    rooms_total = parse_rooms_total(raw_dict)
    sqft = parse_sqft(raw_dict)
    year_built = parse_year_built(raw_dict)
    property_type = parse_property_type(raw_dict)
    price = parse_price(raw_dict)

    logger.debug(
        "Parsed values beds=%s baths=%s rooms_total=%s sqft=%s lot_sqft=%s lot_acres=%s year_built=%s property_type=%s price=%s amenities=%s",
        beds,
        baths,
        rooms_total,
        sqft,
        lot_size_sqft,
        lot_size_acres,
        year_built,
        property_type,
        price,
        amenities,
    )

    return ListingRow(
        source_url=source_url,
        mls_id=str(
            _search(raw_dict, lambda k: k.lower() in {"mls_id", "mlsid", "listingid", "id"})
            or "",
        ),
        address=address,
        city=city or fallbacks.get("city", ""),
        state=state or fallbacks.get("state", ""),
        zip=zip_code,
        beds=beds,
        baths=baths,
        rooms_total=rooms_total,
        sqft=sqft,
        year_built=year_built,
        lot_size_sqft=lot_size_sqft,
        lot_size_acres=lot_size_acres,
        property_type=property_type,
        price=price,
        amenities=amenities,
        description=description,
    )


def normalize_records(records: Iterable[Mapping]):
    """Convert an iterable of mappings into a DataFrame using pandas."""
    import pandas as pd  # Imported lazily to avoid mandatory dependency

    return pd.DataFrame(list(records))


__all__ = [
    "ListingRow",
    "parse_float",
    "parse_int",
    "parse_bedrooms",
    "parse_bathrooms",
    "parse_sqft",
    "parse_lot_sizes",
    "parse_address_block",
    "parse_price",
    "parse_year_built",
    "parse_property_type",
    "parse_description",
    "parse_rooms_total",
    "collect_raw_amenities",
    "to_listing_row",
    "normalize_records",
]
