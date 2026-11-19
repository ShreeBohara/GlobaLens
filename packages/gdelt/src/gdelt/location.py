"""V2Locations: every mention of a place, and the one that stands for the article.

An entry is `type#name#country#adm1#adm2#lat#lon#featureID#offset`; entries are separated by
`;`. `type` is GDELT's Geo_Type:

    1 country   2 US state   3 US city   4 world city   5 world state (ADM1)

The primary location of an article (plan section 7):

1. the earliest city-level mention (Geo_Type 3 or 4), by character offset in the text;
2. otherwise the most specific area: the earliest ADM1-level mention (2 or 5), and failing
   that the earliest country (1);
3. otherwise none.

Selection is on Geo_Type and never on FeatureID. The codebook says FeatureID is blank for
types 1, 2 and 5; the live files disagree (types 1 and 2 carry text codes, type 5 carries
signed numeric IDs exactly like cities), so "has a FeatureID" does not mean "is a point".

Types 1, 2 and 5 carry the coordinates of a centroid. A centroid is not where anything
happened, so only a city-level primary location has `lat` and `lon`. `BLOCKLISTED_CENTROIDS`
is the second guard: whatever its type claims, an entry sitting on one of those coordinates
counts as country-level and is never a point.
"""

import re
from typing import NamedTuple

from glcore.untrusted import sanitize

__all__ = [
    "BLOCKLISTED_CENTROIDS",
    "Location",
    "PrimaryLocation",
    "parse_locations",
    "select_primary",
]

BLOCKLISTED_CENTROIDS: frozenset[tuple[float, float]] = frozenset(
    {
        (39.828175, -98.5795),  # the geographic centre of the contiguous United States, in Kansas
    }
)

_NUMBER = r"-?\d{1,3}(?:\.\d+)?"
_ENTRY = re.compile(
    r"([1-5])#([^#;]*)#([A-Za-z0-9]{0,3})#([A-Za-z0-9]{0,6})#([A-Za-z0-9]{0,8})#"
    rf"({_NUMBER})?#({_NUMBER})?#(-?[A-Za-z0-9]{{0,16}})#(\d{{1,9}})"
)
_NOT_PRINTABLE_ASCII = re.compile(r"[^\x20-\x7e]")


class Location(NamedTuple):
    """One mention of a place, as GDELT wrote it."""

    geo_type: int
    name: str
    country: str  # FIPS 10-4 country code
    adm1: str  # country code plus ADM1 code; the bare country code on a country entry
    adm2: str
    lat: float | None
    lon: float | None
    feature_id: str
    offset: int  # character offset of the mention in the article text


class PrimaryLocation(NamedTuple):
    """The location that stands for an article.

    `geo_type` is the precision it is used at: 3 or 4 is a point; 2 or 5 is an ADM1-level
    area; 1 is a country. `lat` and `lon` are set for points only.
    """

    geo_type: int
    name: str
    country: str
    adm1: str  # empty at country level
    lat: float | None
    lon: float | None
    feature_id: str  # empty when `demoted`
    offset: int
    demoted: bool  # a blocklisted centroid whose own type claimed more than country level

    @property
    def is_point(self) -> bool:
        return self.geo_type == 3 or self.geo_type == 4


def parse_locations(column: str) -> tuple[tuple[Location, ...], int]:
    """Parse a V2Locations column. Returns the well-formed entries in column order and the
    number of malformed entries, which are skipped."""
    if not column:
        return (), 0
    # Gazetteer names are almost always printable ASCII; only the others need the sanitizer.
    clean_names = _NOT_PRINTABLE_ASCII.search(column) is None
    locations: list[Location] = []
    malformed = 0
    for entry in column.split(";"):
        if not entry:
            continue
        match = _ENTRY.fullmatch(entry)
        if match is None:
            malformed += 1
            continue
        geo_type, name, country, adm1, adm2, lat_text, lon_text, feature_id, offset = match.groups()
        lat = float(lat_text) if lat_text else None
        lon = float(lon_text) if lon_text else None
        if (lat is not None and not -90.0 <= lat <= 90.0) or (
            lon is not None and not -180.0 <= lon <= 180.0
        ):
            malformed += 1
            continue
        if (lat is None) != (lon is None):
            malformed += 1
            continue
        locations.append(
            Location(
                int(geo_type),
                name if clean_names else sanitize(name),
                country,
                adm1,
                adm2,
                lat,
                lon,
                feature_id,
                int(offset),
            )
        )
    return tuple(locations), malformed


def select_primary(locations: tuple[Location, ...]) -> PrimaryLocation | None:
    """Apply the primary-location rule of the module docstring."""
    city: Location | None = None
    area: Location | None = None
    country: Location | None = None
    for loc in locations:
        geo_type = loc.geo_type
        if loc.lat is not None and (loc.lat, loc.lon) in BLOCKLISTED_CENTROIDS:
            if loc.country and (country is None or loc.offset < country.offset):
                country = loc
        elif geo_type == 3 or geo_type == 4:
            if loc.lat is not None and (city is None or loc.offset < city.offset):
                city = loc
        elif geo_type == 2 or geo_type == 5:
            if loc.adm1 and (area is None or loc.offset < area.offset):
                area = loc
        elif loc.country and (country is None or loc.offset < country.offset):
            country = loc
    if city is not None:
        return PrimaryLocation(
            city.geo_type, city.name, city.country, city.adm1, city.lat, city.lon,
            city.feature_id, city.offset, False,
        )  # fmt: skip
    if area is not None:
        return PrimaryLocation(
            area.geo_type, area.name, area.country, area.adm1, None, None,
            area.feature_id, area.offset, False,
        )  # fmt: skip
    if country is not None:
        demoted = country.geo_type != 1
        return PrimaryLocation(
            1, country.name, country.country, "", None, None,
            "" if demoted else country.feature_id, country.offset, demoted,
        )  # fmt: skip
    return None
