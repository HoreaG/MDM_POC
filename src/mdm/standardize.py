import re
import unicodedata
import pandas as pd


# =============================================================================
# THE RULES
#
# Plain lists of words. Each one comes from a finding in docs/DATA_ISSUES.md.
# To add a rule, add a line here — no other code changes.
# =============================================================================

# D-009 — short forms the ERP uses, and their full word.
# "ST" is NOT here: it means SAINT only at the START of a name (see standardize_name).
NAME_ABBREVIATIONS = {
    "HOSP": "HOSPITAL",
    "MED": "MEDICAL",
    "CTR": "CENTER",
    "INST": "INSTITUTE",
    "ORTHO": "ORTHOPEDICS",
    "CLNC": "CLINIC",
}

# D-009 — legal endings. They tell us nothing about WHO the customer is.
NAME_NOISE = ["INC", "LLC", "LLP", "PC", "CORP", "THE"]

# Street words. Here "ST" means STREET.
STREET_ABBREVIATIONS = {
    "ST": "STREET",
    "RD": "ROAD",
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "BLVD": "BOULEVARD",
    "DR": "DRIVE",
    "LN": "LANE",
    "CT": "COURT",
    "PL": "PLACE",
    "PKWY": "PARKWAY",
    "CR": "COUNTY ROAD",
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
}

# D-003, D-004, D-012 — a suite marker, then the suite number.
#   STE 400   SUITE 400   UNIT 400   RM 400   #400
# \b means "whole word only", so UNIT does NOT match inside COMMUNITY.
# The part in ( ) is the suite number — the bit we keep.
SUITE_PATTERN = r"(?:\b(?:STE|SUITE|UNIT|RM)\b\.?|#)\s*([A-Z0-9-]+)"

# D-012 — "D/B/A" (doing business as) and everything after it.
#   WILLAMETTE OUTPATIENT CENTER D/B/A WILLAMETTE HEALTH
#                                ^^^^^^^^^^^^^^^^^^^^^^^ removed
DBA_PATTERN = r"\bD\s*/?\s*B\s*/?\s*A\b.*"


# =============================================================================
# SMALL HELPERS
# =============================================================================

def clean_text(value):
    # Empty cells in a CSV arrive as NaN. Treat them as empty text.
    if pd.isna(value):
        return ""

    # D-013 — remove accents: PEÑA -> PENA.
    # Step 1 splits Ñ into N + ~.  Step 2 keeps only plain letters, so ~ is dropped.
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")

    return text.upper().strip()


def remove_punctuation(text):
    # D-010 — "HOSPITAL," must become "HOSPITAL".
    # Dots and apostrophes are DELETED, because they join letters:
    #     P.C.  -> PC        MARY'S -> MARYS
    # Every other symbol becomes a SPACE, because it separates words:
    #     SAINT-LUKE -> SAINT LUKE
    text = text.replace(".", "").replace("'", "")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(text.split())          # squash double spaces into one


def fix_ocr(word):
    # D-012 — a letter typed where a digit should be:
    #     4OO -> 400      I240 -> 1240      18O2 -> 1802
    # Only for words that HAVE a digit and are ONLY digits or O / I / L,
    # so real words like OIL or LOOP are never changed.
    has_digit = any(ch.isdigit() for ch in word)
    looks_like_number = all(ch in "0123456789OIL" for ch in word)

    if has_digit and looks_like_number:
        word = word.replace("O", "0").replace("I", "1").replace("L", "1")
    return word


def singularize(word):
    # D-012 — JOSEPHS -> JOSEPH,  LUKES -> LUKE,  MARYS -> MARY
    # Left alone: short words, words ending in SS (ACCESS),
    # and words ending in ICS (ORTHOPEDICS).
    if len(word) > 4 and word.endswith("S") and not word.endswith("SS") and not word.endswith("ICS"):
        word = word[:-1]
    return word


# =============================================================================
# NAMES
#
#   "St. Joseph's Hosp STE 4OO, Inc."
#
#   clean_text              ST. JOSEPH'S HOSP STE 4OO, INC.
#   remove d/b/a            (nothing to remove here)
#   remove suite            ST. JOSEPH'S HOSP , INC.
#   remove punctuation      ST JOSEPHS HOSP INC
#   split into words        ST  JOSEPHS  HOSP  INC
#   ST at start -> SAINT    SAINT  JOSEPHS  HOSP  INC
#   then word by word:
#       expand abbreviation     HOSP -> HOSPITAL
#       drop noise              INC  -> (gone)
#       singularize             JOSEPHS -> JOSEPH
#   join                    SAINT JOSEPH HOSPITAL
#
# The ORDER matters: d/b/a and suite come out BEFORE punctuation,
# because they need the / and # signs that punctuation removal deletes.
# =============================================================================

def standardize_name(name):
    text = clean_text(name)
    text = re.sub(DBA_PATTERN, "", text)
    text = re.sub(SUITE_PATTERN, "", text)
    text = remove_punctuation(text)
    words = text.split()

    if len(words) > 0 and words[0] == "ST":
        words[0] = "SAINT"

    new_words = []
    for word in words:
        word = NAME_ABBREVIATIONS.get(word, word)    # expand, or keep as it is
        if word in NAME_NOISE:
            continue                                 # skip this word
        word = singularize(word)
        new_words.append(word)

    return " ".join(new_words)


# =============================================================================
# STREETS
#
#   "I240 Main St. Ste 400"
#
#   clean_text              I240 MAIN ST. STE 400
#   remove suite            I240 MAIN ST.
#   remove punctuation      I240 MAIN ST
#   then word by word:
#       fix OCR                 I240 -> 1240
#       expand abbreviation     ST   -> STREET
#   join                    1240 MAIN STREET
#
# The suite is removed here and kept separately (extract_suite), because
# two different businesses can share the same street.
# =============================================================================

def standardize_street(street):
    text = clean_text(street)
    text = re.sub(SUITE_PATTERN, "", text)
    text = remove_punctuation(text)
    words = text.split()

    new_words = []
    for word in words:
        word = fix_ocr(word)
        word = STREET_ABBREVIATIONS.get(word, word)
        new_words.append(word)

    return " ".join(new_words)


# =============================================================================
# SUITES
#
# The suite can hide in many places (D-003, D-004, D-012), so this function
# takes ANY number of values and looks in each one, in order.
# The * in *values means "accept as many as you like".
#
#   extract_suite("1240 MAIN ST", "STE 400")              -> "400"
#   extract_suite("505 ELM ST", "LAKEVIEW ORTHO STE 210") -> "210"
#   extract_suite("ATTN RECEIVING")                       -> ""
# =============================================================================

def extract_suite(*values):
    for value in values:
        text = clean_text(value)
        found = re.search(SUITE_PATTERN, text)
        if found:
            return fix_ocr(found.group(1))      # group(1) = the part in ( ) — the number
    return ""


# =============================================================================
# ZIP CODES
#
# D-005 — some files write 97205, some write 97205-1142.
# We keep only the first 5 digits, so both compare as equal.
#
#   "97205-1142"  -> "97205"
#   "97205"       -> "97205"
#   "972"         -> ""         broken — better empty than a wrong guess
# =============================================================================

def standardize_zip(value):
    digits = re.sub(r"[^0-9]", "", clean_text(value))     # keep only the digits
    if len(digits) == 5 or len(digits) == 9:
        return digits[:5]
    return ""


def zip_from_city_state_zip(value):
    # Distributor Beta puts city, state and ZIP in one column.
    # We only need the ZIP, which is the 5 digits at the END.
    #
    #   "Chicago, IL 60611-2233"  -> "60611"
    #   "Boise, ID"               -> ""
    #
    # Pattern:  (\d{5})      five digits — the part we keep
    #           (-\d{4})?    optionally a dash and four more
    #           $            at the very end of the text
    text = clean_text(value)
    found = re.search(r"(\d{5})(-\d{4})?$", text)
    if found:
        return found.group(1)
    return ""
