"""V2Locations parsing and the primary-location rule."""

from gdelt import (
    BLOCKLISTED_CENTROIDS,
    Location,
    PrimaryLocation,
    parse_locations,
    select_primary,
)

PARIS = "4#Paris, Ile-De-France, France#FR#FRA8#75#48.8667#2.33333#-1456928#640"
MARSEILLE = "4#Marseille, Provence-Alpes-Cote D'azur, France#FR#FRB8#13#43.3#5.4#-1449947#95"
FRANCE = "1#France#FR#FR##46#2#FR#12"
BAVARIA = "5#Bayern, Germany#GM#GM02##49#11.5#-1746443#200"
GERMANY = "1#Germany#GM#GM##51#9#GM#20"
OHIO = "2#Ohio, United States#US#USOH##40.3736#-82.7755#OH#150"
AUSTIN = "3#Austin, Texas, United States#US#USTX#TX453#30.2672#-97.7431#1384879#77"
UNITED_STATES = "1#United States#US#US##39.828175#-98.5795#US#5"
CENTROID_AS_CITY = "3#Somewhere, Kansas, United States#US#USKS#KS000#39.828175#-98.5795#999999#10"


def primary_of(column: str) -> PrimaryLocation | None:
    locations, malformed = parse_locations(column)
    assert malformed == 0
    return select_primary(locations)


def test_an_entry_is_read_field_by_field() -> None:
    locations, malformed = parse_locations(PARIS)
    assert malformed == 0
    assert locations == (
        Location(
            geo_type=4,
            name="Paris, Ile-De-France, France",
            country="FR",
            adm1="FRA8",
            adm2="75",
            lat=48.8667,
            lon=2.33333,
            feature_id="-1456928",
            offset=640,
        ),
    )


def test_an_empty_column_has_no_locations() -> None:
    assert parse_locations("") == ((), 0)
    assert select_primary(()) is None


def test_every_mention_is_kept_in_column_order() -> None:
    locations, _ = parse_locations(f"{FRANCE};{PARIS};{MARSEILLE};")
    assert [loc.offset for loc in locations] == [12, 640, 95]


def test_the_earliest_city_level_mention_is_primary() -> None:
    primary = primary_of(f"{FRANCE};{PARIS};{MARSEILLE}")
    assert primary is not None
    assert primary.name.startswith("Marseille")
    assert (primary.geo_type, primary.lat, primary.lon) == (4, 43.3, 5.4)
    assert (primary.country, primary.adm1) == ("FR", "FRB8")
    assert primary.is_point and not primary.demoted


def test_us_and_world_cities_are_both_city_level() -> None:
    primary = primary_of(f"{PARIS};{AUSTIN}")
    assert primary is not None and primary.geo_type == 3 and primary.name.startswith("Austin")


def test_equal_offsets_keep_column_order() -> None:
    dallas = "3#Dallas, Texas, United States#US#USTX#TX113#32.7831#-96.8067#1380944#77"
    primary = primary_of(f"{AUSTIN};{dallas}")
    assert primary is not None and primary.name.startswith("Austin")


def test_selection_is_on_geo_type_never_on_feature_id() -> None:
    """ADM1 entries (type 5) carry coordinates and a signed numeric FeatureID exactly like cities.
    They are areas all the same."""
    primary = primary_of(f"{GERMANY};{BAVARIA}")
    assert primary is not None
    assert primary.geo_type == 5 and primary.adm1 == "GM02" and primary.country == "GM"
    assert primary.lat is None and primary.lon is None
    assert not primary.is_point


def test_without_a_city_the_most_specific_area_wins() -> None:
    state = primary_of(f"{UNITED_STATES};{OHIO}")
    assert state is not None
    assert (state.geo_type, state.adm1, state.lat) == (2, "USOH", None)

    earliest_area = primary_of(f"{BAVARIA};{OHIO};{GERMANY}")
    assert earliest_area is not None and earliest_area.adm1 == "USOH"  # offset 150 before 200


def test_country_level_is_the_last_resort_and_never_a_point() -> None:
    primary = primary_of("1#Japan#JA#JA##36#138#JA#44;1#Brazil#BR#BR##-10#-55#BR#18")
    assert primary is not None
    assert (primary.geo_type, primary.country, primary.adm1) == (1, "BR", "")
    assert primary.lat is None and primary.lon is None and not primary.is_point


def test_a_country_without_coordinates_is_still_a_country() -> None:
    primary = primary_of("1#Aruba#AA#AA####AA#15")
    assert primary is not None and (primary.geo_type, primary.country) == (1, "AA")


def test_the_kansas_centroid_is_blocklisted() -> None:
    assert (39.828175, -98.5795) in BLOCKLISTED_CENTROIDS


def test_the_centroid_as_a_country_entry_is_country_level() -> None:
    primary = primary_of(UNITED_STATES)
    assert primary is not None
    assert (primary.geo_type, primary.country, primary.lat, primary.lon) == (1, "US", None, None)
    assert not primary.demoted  # it already was country-level


def test_a_city_level_entry_on_the_centroid_counts_as_country_level() -> None:
    primary = primary_of(CENTROID_AS_CITY)
    assert primary is not None
    assert (primary.geo_type, primary.country, primary.adm1) == (1, "US", "")
    assert primary.lat is None and primary.lon is None
    assert primary.demoted and not primary.is_point


def test_a_real_city_beats_the_centroid_even_when_mentioned_later() -> None:
    wichita = "3#Wichita, Kansas, United States#US#USKS#KS173#37.6922#-97.3375#473862#500"
    primary = primary_of(f"{CENTROID_AS_CITY};{wichita}")
    assert primary is not None and primary.name.startswith("Wichita") and primary.is_point


def test_an_adm1_area_beats_the_centroid() -> None:
    primary = primary_of(f"{CENTROID_AS_CITY};{OHIO}")
    assert primary is not None and (primary.geo_type, primary.adm1) == (2, "USOH")


def test_malformed_entries_are_skipped_and_counted_never_repaired() -> None:
    column = ";".join(
        [
            "0#Georgia, , Georgia#GG#GG##42#.5#1#GG#51",  # ten fields, as real files have it
            "4#Eight fields#XX#XX00##10#20#-1",
            "9#Unknown type#XX#XX00##10#20#-1#5",
            "0#Type zero#XX#XX00##10#20#-1#5",
            "4#Latitude out of range#XX#XX00##95.5#10#-1#20",
            "4#Longitude out of range#XX#XX00##10#181#-1#20",
            "4#Offset is not a number#XX#XX00##10#20#-2#abc",
            "4#Latitude is not a number#XX#XX00##1e1#20#-2#7",
            "4#Underscore number#XX#XX00##1_0#20#-2#7",
            PARIS,
        ]
    )
    locations, malformed = parse_locations(column)
    assert malformed == 9
    assert [loc.name for loc in locations] == ["Paris, Ile-De-France, France"]


def test_a_city_level_entry_without_coordinates_is_no_candidate() -> None:
    locations, malformed = parse_locations("4#Ghost Town, Nowhere#XX#XX00####-5#9")
    assert malformed == 0 and len(locations) == 1 and locations[0].lat is None
    assert select_primary(locations) is None


def test_an_area_without_its_code_is_no_candidate() -> None:
    locations, _ = parse_locations("5#No code####10#20#-5#9;1#No country code#####XX#3")
    assert select_primary(locations) is None


def test_place_names_are_sanitized() -> None:
    locations, _ = parse_locations(
        "4#Par\u202eis\u200b, France#FR#FRA8#75#48.8667#2.33333#-1456928#1"
    )
    assert locations[0].name == "Paris, France"
