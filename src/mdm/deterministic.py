import itertools
import pandas as pd


# =============================================================================
# make_key — glue several columns into one matching key
#
#   name_std               street_std        zip5     ->  key
#   SAINT JOSEPH HOSPITAL  1240 MAIN STREET  97205    ->  SAINT JOSEPH HOSPITAL|1240 MAIN STREET|97205
#   SAINT JOSEPH HOSPITAL  (empty)           97205    ->  (empty)
#
# If ANY piece is empty, the whole key is empty. Otherwise
# "SAINT JOSEPH HOSPITAL||97205" would not count as empty, and every record
# with that name, no street and that ZIP would "match" each other.
# =============================================================================

def make_key(df: pd.DataFrame, columns: list):
    key = df[columns].agg("|".join, axis=1)           # glue the columns with |, row by row
    key[(df[columns] == "").any(axis=1)] = ""         # blank it if any piece is empty
    return key


# =============================================================================
# matching — every pair of records that share the same key
#
#   1. drop empty keys      empty means "unknown", not "the same"
#   2. group by the key     records with the same value land together
#   3. sort the IDs         so a pair always comes out the same way round
#   4. every pair           3 records -> 3 pairs:  A-B, A-C, B-C
#
# A group of ONE record gives no pairs — combinations of one item is nothing.
# =============================================================================

def matching(df: pd.DataFrame, key: str, rule: str):
    df = df[df[key] != ""]                                        # 1

    rows = []
    for value, group in df.groupby(key):                          # 2
        uids = sorted(group["record_uid"])                        # 3
        for left, right in itertools.combinations(uids, 2):       # 4
            rows.append((left, right, rule))

    return pd.DataFrame(rows, columns=["record_uid_l", "record_uid_r", "rule"])


# =============================================================================
# run_deterministic — run every rule, strongest first
#
#   R1  same NPI                     the official healthcare ID
#   R2  same legacy customer ID      the ERP's own number (D-007 duplicates)
#   R3  same name + street + ZIP     both name AND address must agree
#
# Why R3 is name + street + ZIP, and not something shorter:
#   name + ZIP     merges two campuses of one hospital    (Summit Regional, D-006)
#   street + ZIP   merges two tenants of one building     (co-location, D-004)
#   name + street + ZIP needs both to agree, so neither mistake gets through.
#
# The same pair can be found by more than one rule. We keep the FIRST one,
# so each pair is labelled with the strongest rule that found it.
# =============================================================================

def run_deterministic(records: pd.DataFrame):
    records = records.copy()                         # don't change the caller's table
    records["name_street_zip"] = make_key(records, ["name_std", "street_std", "zip5"])

    pairs = pd.concat([
        matching(records, "npi",                "R1_SHARED_NPI"),
        matching(records, "legacy_customer_id", "R2_SHARED_LEGACY_ID"),
        matching(records, "name_street_zip",    "R3_NAME_STREET_ZIP"),
    ], ignore_index=True)

    return pairs.drop_duplicates(subset=["record_uid_l", "record_uid_r"], keep="first")


# =============================================================================
# show_pairs — put the actual record details next to each pair, so you can
# READ the matches instead of looking at IDs
#
#   record_uid_l  record_uid_r  rule   name_raw_l      name_raw_r       street_std_l  street_std_r ...
#   erp::E1004    erp::E2003    R2...  BROOKSIDE ...   BROOKSIDE ...    ...           ...
# =============================================================================

def show_pairs(pairs: pd.DataFrame, records: pd.DataFrame, columns=["name_raw", "street_std", "zip5", "source_system"]):
    view = pairs.copy()
    lookup = records.set_index("record_uid")                         # ID -> its whole row

    for col in columns:
        view[col + "_l"] = view["record_uid_l"].map(lookup[col])     # details of the left record
        view[col + "_r"] = view["record_uid_r"].map(lookup[col])     # details of the right record

    return view