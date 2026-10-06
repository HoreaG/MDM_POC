from mdm.standardize import (
    standardize_name,
    standardize_street,
    extract_suite,
    standardize_zip,
    zip_from_city_state_zip,
)

# Each test: give the function a real value from the sample files,
# and check it returns what we expect.  "assert A == B" means A must equal B.
# Run them all with:   pytest -v


# ----- NAMES -----------------------------------------------------------------

def test_d009_abbreviations_are_expanded():
    assert standardize_name("ST JOSEPH HOSP") == "SAINT JOSEPH HOSPITAL"
    assert standardize_name("OAKMONT IMAGING CTR") == "OAKMONT IMAGING CENTER"
    assert standardize_name("MERCY ORTHO") == "MERCY ORTHOPEDICS"

def test_d009_erp_and_salesforce_now_agree():
    assert standardize_name("OAKMONT IMAGING CTR") == standardize_name("Oakmont Imaging Center")

def test_d009_st_is_saint_only_at_the_start():
    assert standardize_name("ST LUKE HOSP") == "SAINT LUKE HOSPITAL"
    assert standardize_name("MAIN ST CLINIC") == "MAIN ST CLINIC"

def test_d009_legal_endings_are_dropped():
    assert standardize_name("Cedar Ridge Hospital LLC") == "CEDAR RIDGE HOSPITAL"
    assert standardize_name("Silver Creek Hospital, Inc.") == "SILVER CREEK HOSPITAL"

def test_d010_comma_does_not_change_the_word():
    assert standardize_name("Silver Creek Hospital,") == "SILVER CREEK HOSPITAL"

def test_d010_pc_with_dots_is_dropped():
    assert standardize_name("Granite Falls Clinic, P.C.") == "GRANITE FALL CLINIC"

def test_d012_suite_inside_the_name_is_removed():
    assert standardize_name("LAKEVIEW ORTHOPEDICS STE 210") == "LAKEVIEW ORTHOPEDICS"

def test_d012_dba_is_removed():
    assert standardize_name("WILLAMETTE OUTPATIENT CENTER D/B/A WILLAMETTE HEALTH") == "WILLAMETTE OUTPATIENT CENTER"

def test_d012_possessives_are_removed():
    assert standardize_name("ST JOSEPHS HOSPITAL") == "SAINT JOSEPH HOSPITAL"
    assert standardize_name("St. Joseph's Hospital") == "SAINT JOSEPH HOSPITAL"

def test_d012_orthopedics_keeps_its_s():
    assert standardize_name("Lakeview Orthopedics") == "LAKEVIEW ORTHOPEDICS"

def test_d013_accents_are_removed():
    assert standardize_name("Peña Blanca Family Clinic") == "PENA BLANCA FAMILY CLINIC"

def test_extra_spaces_are_ignored():
    assert standardize_name("  SAINT  JOSEPHS IMAGING CTR ") == "SAINT JOSEPH IMAGING CENTER"

def test_empty_name_gives_empty_text():
    assert standardize_name("") == ""
    assert standardize_name(None) == ""


# ----- STREETS ---------------------------------------------------------------

def test_street_abbreviations_are_expanded():
    assert standardize_street("88 River Rd") == "88 RIVER ROAD"
    assert standardize_street("505 Oak Av") == "505 OAK AVENUE"

def test_st_is_street_in_an_address():
    assert standardize_street("1240 MAIN ST") == "1240 MAIN STREET"

def test_d012_ocr_damage_is_fixed():
    assert standardize_street("I240 CEDAR LANE") == "1240 CEDAR LANE"
    assert standardize_street("18O2 CEDAR LANE") == "1802 CEDAR LANE"

def test_suite_is_removed_from_the_street():
    assert standardize_street("900 Harbor Blvd Suite 300") == "900 HARBOR BOULEVARD"


# ----- SUITES ----------------------------------------------------------------

def test_d004_both_spellings_are_found():
    assert extract_suite("STE 400") == "400"
    assert extract_suite("Suite 400") == "400"

def test_d003_delivery_notes_are_not_suites():
    assert extract_suite("ATTN RECEIVING") == ""
    assert extract_suite("LOADING DOCK B") == ""
    assert extract_suite("C/O MATERIALS MGMT") == ""

def test_d012_suite_found_inside_the_name():
    assert extract_suite("505 ELM STREET", "", "LAKEVIEW ORTHOPEDICS STE 210") == "210"

def test_suite_ocr_damage_is_fixed():
    assert extract_suite("STE 4OO") == "400"

def test_community_is_not_a_suite():
    assert extract_suite("PRAIRIE COMMUNITY HOSPITAL") == ""


# ----- ZIP CODES -------------------------------------------------------------

def test_d005_zip_plus_four_keeps_first_five():
    assert standardize_zip("97205-1142") == "97205"
    assert standardize_zip("97205") == "97205"

def test_broken_zip_is_empty():
    assert standardize_zip("972") == ""
    assert standardize_zip("") == ""

def test_beta_zip_comes_out_of_the_combined_column():
    assert zip_from_city_state_zip("Chicago, IL 60611-2233") == "60611"
    assert zip_from_city_state_zip("Des Moines, IA 50309") == "50309"
    assert zip_from_city_state_zip("Boise, ID") == ""
