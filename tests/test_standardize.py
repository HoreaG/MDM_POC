"""
Tests for standardize.py.

HOW TO READ A TEST
    def test_something():
        assert standardize_name("INPUT") == "EXPECTED"

    "assert A == B" means: A must equal B, or the test fails.
    Each function whose name starts with test_ is one check. pytest finds and
    runs all of them.

WHERE THE EXAMPLES COME FROM
    Real values copied out of the sample files, so every test proves the code
    handles something that actually exists in the data. The D-number in each
    test name points to the finding in docs/DATA_ISSUES.md.

RUN THEM
    pytest              all tests
    pytest -v           all tests, one line each
"""

from mdm.standardize import (
    build_match_keys,
    extract_suite,
    parse_city_state_zip,
    standardize_name,
    standardize_street,
    standardize_zip,
)


# =============================================================================
# NAMES
# =============================================================================

def test_d009_abbreviations_are_expanded():
    assert standardize_name("ST JOSEPH HOSP") == "SAINT JOSEPH HOSPITAL"
    assert standardize_name("OAKMONT IMAGING CTR") == "OAKMONT IMAGING CENTER"
    assert standardize_name("MERCY ORTHO") == "MERCY ORTHOPEDICS"


def test_d009_erp_and_salesforce_now_agree():
    # The whole point: two systems, one hospital, same result
    assert standardize_name("OAKMONT IMAGING CTR") == standardize_name("Oakmont Imaging Center")


def test_d009_st_means_saint_only_at_the_start():
    assert standardize_name("ST LUKE HOSP") == "SAINT LUKE HOSPITAL"
    # "ST" anywhere else is left alone — it is not a name word there
    assert standardize_name("MAIN ST CLINIC").startswith("MAIN ST")


def test_d009_legal_endings_are_dropped():
    assert standardize_name("Cedar Ridge Hospital LLC") == "CEDAR RIDGE HOSPITAL"
    assert standardize_name("Silver Creek Hospital, Inc.") == "SILVER CREEK HOSPITAL"


def test_d010_punctuation_does_not_split_words():
    # The comma that made Excel show 20 hospitals and the code show 19
    assert standardize_name("Silver Creek Hospital,") == "SILVER CREEK HOSPITAL"


def test_d010_pc_with_dots_is_dropped_as_one_word():
    # "P.C." must become PC (then dropped), not the two letters P and C
    assert standardize_name("Granite Falls Clinic, P.C.") == "GRANITE FALL CLINIC"


def test_d012_suite_inside_the_name_is_removed():
    assert standardize_name("LAKEVIEW ORTHOPEDICS STE 210") == "LAKEVIEW ORTHOPEDICS"


def test_d012_dba_clause_is_removed():
    assert (standardize_name("WILLAMETTE OUTPATIENT CENTER D/B/A WILLAMETTE HEALTH")
            == "WILLAMETTE OUTPATIENT CENTER")


def test_d012_possessives_are_removed():
    assert standardize_name("ST JOSEPHS HOSPITAL") == "SAINT JOSEPH HOSPITAL"
    assert standardize_name("St. Joseph's Hospital") == "SAINT JOSEPH HOSPITAL"


def test_d012_orthopedics_is_not_singularised():
    # Ends in ICS — must survive, or the name would read ORTHOPEDIC
    assert standardize_name("Lakeview Orthopedics") == "LAKEVIEW ORTHOPEDICS"


def test_d013_accents_are_removed():
    # Without this, PEÑA splits into PE and A
    assert standardize_name("Peña Blanca Family Clinic") == "PENA BLANCA FAMILY CLINIC"


def test_extra_spaces_are_ignored():
    assert standardize_name("  SAINT  JOSEPHS IMAGING CTR ") == "SAINT JOSEPH IMAGING CENTER"


def test_empty_name_gives_empty_text():
    assert standardize_name("") == ""
    assert standardize_name(None) == ""


# =============================================================================
# STREETS
# =============================================================================

def test_street_abbreviations_are_expanded():
    assert standardize_street("88 River Rd") == "88 RIVER ROAD"
    assert standardize_street("505 Oak Av") == "505 OAK AVENUE"


def test_st_means_street_in_an_address():
    # The opposite of a name — this is why there are two dictionaries
    assert standardize_street("1240 MAIN ST") == "1240 MAIN STREET"


def test_d012_ocr_damage_in_house_numbers_is_fixed():
    assert standardize_street("I240 CEDAR LANE") == "1240 CEDAR LANE"
    assert standardize_street("18O2 CEDAR LANE") == "1802 CEDAR LANE"


def test_suite_is_removed_from_the_street():
    assert standardize_street("900 Harbor Blvd Suite 300") == "900 HARBOR BOULEVARD"


# =============================================================================
# SUITES
# =============================================================================

def test_d004_both_suite_spellings_are_found():
    assert extract_suite("STE 400") == "400"
    assert extract_suite("Suite 400") == "400"


def test_d003_delivery_notes_are_not_suites():
    # address_line_2 often holds these — they must NOT be read as a suite
    assert extract_suite("ATTN RECEIVING") == ""
    assert extract_suite("LOADING DOCK B") == ""
    assert extract_suite("C/O MATERIALS MGMT") == ""


def test_d012_suite_is_found_inside_the_name():
    street, line_2, name = "505 ELM STREET", "", "LAKEVIEW ORTHOPEDICS STE 210"
    assert extract_suite(street, line_2, name) == "210"


def test_suite_ocr_damage_is_fixed():
    assert extract_suite("STE 4OO") == "400"


def test_community_is_not_a_suite():
    # UNIT is inside COMMUNITY — the word boundary stops a false match
    assert extract_suite("PRAIRIE COMMUNITY HOSPITAL") == ""


# =============================================================================
# ZIP CODES
# =============================================================================

def test_d005_zip_plus_four_is_split():
    assert standardize_zip("97205-1142") == ("97205", "1142")
    assert standardize_zip("97205") == ("97205", "")


def test_broken_zip_is_empty_not_a_guess():
    assert standardize_zip("972") == ("", "")
    assert standardize_zip("") == ("", "")


def test_beta_combined_column_is_split():
    assert parse_city_state_zip("Chicago, IL 60611-2233") == ("CHICAGO", "IL", "60611", "2233")
    assert parse_city_state_zip("Des Moines, IA 50309") == ("DES MOINES", "IA", "50309", "")


def test_beta_column_with_missing_zip():
    assert parse_city_state_zip("Boise, ID") == ("BOISE", "ID", "", "")


# =============================================================================
# MATCH KEYS
# =============================================================================

def test_match_keys_are_built():
    keys = build_match_keys("SAINT JOSEPH HOSPITAL", "1240 MAIN STREET", "400", "97205")
    assert keys["mk_name_zip"] == "SAINT JOSEPH HOSPITAL|97205"
    assert keys["block_zip5"] == "97205"
    assert keys["block_streetnum_zip3"] == "1240|972"
    assert keys["block_name_prefix"] == "SAINT "


def test_match_key_is_empty_when_a_piece_is_missing():
    # Otherwise every nameless record in 97205 would "match" every other one
    keys = build_match_keys("", "1240 MAIN STREET", "", "97205")
    assert keys["mk_name_zip"] == ""
    assert keys["mk_name_address"] == ""
