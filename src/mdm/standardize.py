"""
standardize.py — make messy names and addresses comparable.

WHY THIS FILE EXISTS
    The same hospital is written differently in every system:

        ERP          ST JOSEPH HOSP
        Salesforce   Saint Joseph Hospital
        Distributor  ST JOSEPHS HOSPITAL STE 4OO

    A computer sees three different strings. After standardisation all three
    become SAINT JOSEPH HOSPITAL, and now they can be matched.

HOW IT IS BUILT
    Every function takes ONE value and returns ONE value. No pandas here.
    That keeps each function easy to test, and lets the same code run in
    pandas (df.col.apply(...)) and in Spark (as a UDF) without changes.

    Every rule comes from a numbered finding in docs/DATA_ISSUES.md.
    The D-numbers in the comments say which one.

WHAT IS IN HERE
    standardize_name      a customer name   -> comparable name
    standardize_street    a street line     -> comparable street, suite removed
    extract_suite         several strings   -> just the suite, e.g. "400"
    standardize_zip       a postal code     -> (zip5, zip4)
    parse_city_state_zip  "Chicago, IL 60611" -> (city, state, zip5, zip4)
    build_match_keys      cleaned pieces    -> keys for matching and blocking
"""

import math
import re
import unicodedata


# =============================================================================
# THE RULES
# Kept at the top as plain dictionaries so anyone can read them without
# reading the code. Later these move into conf/ files that the business can
# edit without a code change.
# =============================================================================

# D-009 — found by comparing ERP and Salesforce word counts.
# "ST" is NOT in here on purpose: it means SAINT only at the START of a name,
# so it gets its own rule inside standardize_name.
NAME_ABBREVIATIONS = {
    "HOSP": "HOSPITAL",
    "MED": "MEDICAL",
    "CTR": "CENTER",
    "INST": "INSTITUTE",
    "ORTHO": "ORTHOPEDICS",
    "CLNC": "CLINIC",
}

# D-009 — legal endings. They identify nothing, so we drop them.
NAME_NOISE = {"INC", "LLC", "LLP", "PC", "CORP", "THE"}

# Street words. Here "ST" means STREET — the opposite of a name.
# The official full list is USPS Publication 28; this covers what is in the data.
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

# D-003, D-004, D-012 — a suite marker followed by its number.
#   (?: ... )          group the alternatives
#   \b ... \b          word boundary, so UNIT does not match inside COMMUNITY
#   \.?                an optional dot, for "STE. 400"
#   |#                 or a hash sign, for "#400"
#   \s*                any spaces
#   ([A-Z0-9-]+)       the suite number itself — the part we keep
SUITE_PATTERN = re.compile(r"(?:\b(?:STE|SUITE|UNIT|RM)\b\.?|#)\s*([A-Z0-9-]+)")

# D-012 — "d/b/a" (doing business as) and everything after it.
#   D\s*/?\s*B\s*/?\s*A   matches DBA, D/B/A, D / B / A
#   .*                    and everything to the end of the string
DBA_PATTERN = re.compile(r"\bD\s*/?\s*B\s*/?\s*A\b.*")


# =============================================================================
# SMALL HELPERS
# Used by the main functions below.
# =============================================================================

def to_text(value):
    """
    Turn any value into clean upper-case text. Empty stays empty.

    Handles three things that would otherwise crash or mislead:
      None or NaN   -> ""          (empty cells in a CSV arrive as NaN)
      accents       -> removed     PEÑA -> PENA   (D-013)
      case          -> upper       Mercy -> MERCY
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""

    # Split each accented letter into "letter + accent mark", then drop the marks.
    # Ñ becomes N + ~, and we keep only the N.
    # Without this, the punctuation step below would treat Ñ as "not a letter"
    # and split PEÑA into PE and A.
    decomposed = unicodedata.normalize("NFKD", str(value))
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))

    return no_accents.upper().strip()


def strip_punctuation(text):
    """
    Remove punctuation so "Hospital," and "Hospital" become the same word.  (D-010)

      step                               "ST. MARY'S CLINIC, P.C."
      1. delete dots and apostrophes     "ST MARYS CLINIC, PC"
      2. other symbols -> space          "ST MARYS CLINIC  PC"
      3. squash spaces                   "ST MARYS CLINIC PC"

    Why dots and apostrophes are DELETED but other symbols become a SPACE:
      they JOIN letters  — "P.C." should become "PC", "MARY'S" -> "MARYS"
      other symbols SEPARATE words — "SAINT-LUKE" should become "SAINT LUKE"
    """
    text = text.replace(".", "").replace("'", "")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(text.split())


def fix_ocr(word):
    """
    Repair letters typed where digits should be.  (D-012)

      4OO  -> 400      letter O instead of zero
      I240 -> 1240     letter I instead of one
      18O2 -> 1802

    Only touches a word that HAS at least one digit and is made ONLY of digits
    plus O / I / L. So real words like OIL or LOOP are never changed.
    """
    looks_numeric = re.fullmatch(r"[0-9OIL]+", word) and re.search(r"[0-9]", word)
    if looks_numeric:
        return word.replace("O", "0").replace("I", "1").replace("L", "1")
    return word


def singularize(word):
    """
    Remove a plural or possessive S.  (D-012)

      JOSEPHS -> JOSEPH     LUKES -> LUKE     MARYS -> MARY

    Left alone:
      short words (4 letters or fewer)    so "ICS" style fragments are safe
      words ending in SS                  ACCESS stays ACCESS
      words ending in ICS                 ORTHOPEDICS stays ORTHOPEDICS

    It is applied to EVERY source the same way, so it can never make two
    different names look alike on its own.
    """
    if len(word) > 4 and word.endswith("S") and not word.endswith(("SS", "ICS")):
        return word[:-1]
    return word


# =============================================================================
# NAMES
# =============================================================================

def standardize_name(name):
    """
    Turn a customer name into a form that can be compared.

    Example: "St. Joseph's Hosp STE 4OO, Inc."

      step                         result
      1. text, no accents, upper   ST. JOSEPH'S HOSP STE 4OO, INC.
      2. drop d/b/a clause         (nothing to drop here)
      3. drop the suite            ST. JOSEPH'S HOSP , INC.
      4. drop punctuation          ST JOSEPHS HOSP INC
      5. split into words          [ST, JOSEPHS, HOSP, INC]
      6. ST at the start -> SAINT  [SAINT, JOSEPHS, HOSP, INC]
      7. expand abbreviations      [SAINT, JOSEPHS, HOSPITAL, INC]
      8. drop noise words          [SAINT, JOSEPHS, HOSPITAL]
      9. singularise               [SAINT, JOSEPH, HOSPITAL]
     10. join                      SAINT JOSEPH HOSPITAL

    THE ORDER MATTERS:
      - the suite and d/b/a come out BEFORE punctuation, because their
        patterns need the slashes and # signs that step 4 removes
      - punctuation comes out BEFORE splitting, or "HOSP," never matches HOSP
      - singularise comes AFTER expanding, so both ORTHO and ORTHOPEDICS
        end up as the same word
    """
    text = to_text(name)                              # 1  D-013
    text = DBA_PATTERN.sub("", text)                  # 2  D-012
    text = SUITE_PATTERN.sub("", text)                # 3  D-012
    text = strip_punctuation(text)                    # 4  D-010
    words = text.split()                              # 5

    if words and words[0] == "ST":                    # 6  D-009
        words[0] = "SAINT"

    words = [NAME_ABBREVIATIONS.get(w, w) for w in words]   # 7  D-009
    words = [w for w in words if w not in NAME_NOISE]       # 8  D-009
    words = [singularize(w) for w in words]                 # 9  D-012

    return " ".join(words)                            # 10


# =============================================================================
# ADDRESSES
# =============================================================================

def standardize_street(street):
    """
    Turn a street line into a form that can be compared. The suite is removed —
    it is compared separately, because two businesses can share a street.

    Example: "I240 Main St. Ste 400"

      step                          result
      1. text, upper                I240 MAIN ST. STE 400
      2. drop the suite             I240 MAIN ST.
      3. drop punctuation           I240 MAIN ST
      4. split into words           [I240, MAIN, ST]
      5. fix OCR                    [1240, MAIN, ST]
      6. expand street words        [1240, MAIN, STREET]
      7. join                       1240 MAIN STREET

    Note step 6: here ST becomes STREET. In a name it becomes SAINT.
    That is why names and streets have separate dictionaries.
    """
    text = to_text(street)                            # 1
    text = SUITE_PATTERN.sub("", text)                # 2  D-003
    text = strip_punctuation(text)                    # 3  D-010
    words = text.split()                              # 4
    words = [fix_ocr(w) for w in words]               # 5  D-012
    words = [STREET_ABBREVIATIONS.get(w, w) for w in words]  # 6
    return " ".join(words)                            # 7


def extract_suite(*values):
    """
    Find the suite number, wherever it is hiding.

    The * in *values means "accept any number of arguments". So you can pass
    every place a suite might be:

        extract_suite(street, address_line_2, address_line_3, name)

    It checks each one in order and returns the first suite it finds.

      extract_suite("1240 MAIN ST", "STE 400")              -> "400"
      extract_suite("", "", "LAKEVIEW ORTHO STE 210")        -> "210"
      extract_suite("ATTN RECEIVING")                        -> ""

    WHY SEVERAL PLACES (D-003, D-004, D-012):
      ERP          address_line_2 OR address_line_3 — and line 2 is often a
                   delivery note like "ATTN RECEIVING", not a suite
      Salesforce   its own billing_suite column
      Distributor  in the address, or typed into the NAME field

    So we look for the PATTERN, never trust the column.
    """
    for value in values:
        found = SUITE_PATTERN.search(to_text(value))
        if found:
            return fix_ocr(found.group(1))            # STE 4OO -> 400
    return ""


def street_number(street):
    """The house number at the start of a street: "1240 MAIN STREET" -> "1240"."""
    found = re.match(r"(\d+)", street)
    return found.group(1) if found else ""


def standardize_zip(value):
    """
    Split a postal code into (zip5, zip4).  (D-005)

      "97205-1142"  -> ("97205", "1142")
      "97205"       -> ("97205", "")
      "972"         -> ("", "")        too short to trust
      ""            -> ("", "")

    Why split: Salesforce mixes 5-digit and 9-digit ZIPs in one column, so
    "61602-7896" and "61602" never compare as equal. Matching uses zip5.

    A broken ZIP returns EMPTY rather than a guess. An empty ZIP just means
    "can't use this key". A wrong ZIP would block the record into the wrong
    group, where its real match is never even looked at.
    """
    digits = re.sub(r"[^0-9]", "", to_text(value))
    if len(digits) >= 9:
        return digits[:5], digits[5:9]
    if len(digits) == 5:
        return digits, ""
    return "", ""


def parse_city_state_zip(value):
    """
    Split Distributor Beta's combined column into its parts.

      "Chicago, IL 60611-2233"  -> ("CHICAGO", "IL", "60611", "2233")
      "Portland, OR 97205"      -> ("PORTLAND", "OR", "97205", "")
      "Boise, ID"               -> ("BOISE", "ID", "", "")      ZIP missing

    The pattern, piece by piece:
      ^(.*?)                 the city — as few characters as possible
      ,?\\s+                 an optional comma, then spaces
      ([A-Z]{2})             the state — exactly two letters
      (?:\\s+(\\d{5}...))?    optionally, spaces then the ZIP
      $                      end of the text

    TRAP (D-010 / caught by a test): do NOT strip punctuation first. That
    removes the comma and hyphen this pattern needs, and every ZIP silently
    comes back empty. Nothing errors — a blocking key just disappears.
    """
    text = to_text(value)
    found = re.match(r"^(.*?),?\s+([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?$", text)
    if not found:
        return strip_punctuation(text), "", "", ""

    city, state, zip_raw = found.groups()
    zip5, zip4 = standardize_zip(zip_raw)
    return strip_punctuation(city), state, zip5, zip4


# =============================================================================
# MATCH KEYS
# =============================================================================

def build_match_keys(name_std, street_std, suite, zip5):
    """
    Build the keys that matching and blocking use. All inputs must ALREADY
    be standardised.

    The "|" is just a separator, so the parts can't run into each other.

      key                    example                                  used for
      mk_name_address        SAINT JOSEPH HOSPITAL|1240 MAIN STREET|400|97205   exact match, rule 3
      mk_name_zip            SAINT JOSEPH HOSPITAL|97205              exact match, rule 4
      block_zip5             97205                                    blocking
      block_streetnum_zip3   1240|972                                 blocking
      block_name_prefix      SAINT                                    blocking

    An exact-match key is EMPTY if a piece is missing. Otherwise every record
    with a blank name and ZIP 97205 would "match" every other one.

    Several blocking keys, because each catches a different kind of dirt:
      block_zip5             same ZIP
      block_streetnum_zip3   same house number, survives a wrong last ZIP digit
      block_name_prefix      first 6 letters, survives a completely wrong ZIP
    """
    number = street_number(street_std)

    return {
        "mk_name_address": f"{name_std}|{street_std}|{suite}|{zip5}" if name_std and street_std and zip5 else "",
        "mk_name_zip": f"{name_std}|{zip5}" if name_std and zip5 else "",
        "block_zip5": zip5,
        "block_streetnum_zip3": f"{number}|{zip5[:3]}" if number and zip5 else "",
        "block_name_prefix": name_std[:6],
    }
