#!/usr/bin/env python3
"""
Generate the sample dataset.

Deterministic - a fixed seed means you get byte-identical files every time, so
you can commit them and diff pipeline results across runs meaningfully.

    python generate_sample_data.py

Produces the eight source files plus:

    SCENARIO_CATALOGUE.csv   every record id -> which data defects it carries
    GROUND_TRUTH.csv         every tracing record -> the customer it really is

GROUND_TRUTH is what legacy_match_decisions.csv is derived from. The generator
KNOWS the right answer because it created the mess, so the truth file is
correct by construction rather than by someone's judgement.
"""

from __future__ import annotations

import csv
import os
import random
import unicodedata

SEED = 20260914
random.seed(SEED)

OUT = os.path.dirname(os.path.abspath(__file__))

# ===========================================================================
# 1. The real world: health systems, networks, and 60 customers
# ===========================================================================

HEALTH_SYSTEMS = [
    ("HS-100", "Cascade Health System", [
        ("IDN-110", "Cascade North Network", "OR", "Portland", "97205"),
        ("IDN-120", "Cascade South Network", "OR", "Eugene", "97401"),
    ]),
    ("HS-200", "Lakeside Health", [
        ("IDN-210", "Lakeside Metro Group", "IL", "Chicago", "60611"),
        ("IDN-220", "Lakeside Rural Group", "IL", "Peoria", "61602"),
    ]),
    ("HS-300", "Gulf Coast Care", [
        ("IDN-310", "Gulf Coast Alliance", "FL", "Tampa", "33602"),
        ("IDN-320", "Gulf Coast Physicians", "FL", "Orlando", "32801"),
    ]),
    ("HS-400", "Summit Regional Health", [
        ("IDN-410", "Summit Mountain Network", "CO", "Denver", "80202"),
    ]),
    # A health system whose facilities span two states - tests that nobody
    # assumed a system lives in one place.
    ("HS-500", "Heartland Partners", [
        ("IDN-510", "Heartland North", "MN", "Minneapolis", "55401"),
        ("IDN-520", "Heartland South", "IA", "Des Moines", "50309"),
    ]),
]

NAME_STEMS = [
    "Saint Joseph", "Saint Mary", "Saint Luke", "Mercy", "Bayview", "Riverbend",
    "Prairie", "Cedar Ridge", "Willamette", "Lakeview", "Summit", "Northgate",
    "Harbor Point", "Oakmont", "Silver Creek", "Fairhaven", "Brookside",
    "Granite Falls", "Meadowbrook", "Ironwood",
]

FACILITY_TYPES = [
    "Hospital", "Medical Center", "Regional Hospital", "Community Hospital",
    "Family Clinic", "Surgery Center", "Cancer Institute", "Outpatient Center",
    "Orthopedics", "Imaging Center",
]

STREET_NAMES = [
    "Main Street", "Lake Shore Drive", "Harbor Boulevard", "River Road",
    "Oak Avenue", "Cedar Lane", "County Road 9", "Elm Street", "Pine Avenue",
    "North Washington Street", "South Adams Boulevard", "Grant Parkway",
    "Summit Drive", "Birchwood Court", "Union Place",
]

GPOS = [("GPO-01", "Vantage Purchasing"), ("GPO-02", "Meridian Sourcing"),
        ("GPO-03", "Alliance Procurement")]


def build_customers() -> list[dict]:
    customers = []
    counter = 0
    npi_counter = 1003811509

    for hs_id, hs_name, idns in HEALTH_SYSTEMS:
        for idn_id, idn_name, state, city, base_zip in idns:
            # Seven per network gives 63 customers across 9 networks - enough
            # for every structural scenario below to have a distinct target.
            for _ in range(7):
                counter += 1
                stem = random.choice(NAME_STEMS)
                kind = random.choice(FACILITY_TYPES)
                street_name = random.choice(STREET_NAMES)
                number = random.choice([12, 45, 77, 88, 300, 505, 900, 1240, 1802, 2450])

                customers.append({
                    "cust_id": f"L-{counter:04d}",
                    "name": f"{stem} {kind}",
                    "street_number": str(number),
                    "street_name": street_name,
                    "suite": "",
                    "city": city,
                    "state": state,
                    "zip5": base_zip,
                    "zip4": f"{random.randint(1000, 9999)}",
                    "npi": str(npi_counter),
                    "idn_id": idn_id,
                    "health_system_id": hs_id,
                    "gpos": random.sample([g[0] for g in GPOS], k=random.choice([0, 1, 1, 2])),
                    "flags": [],
                })
                npi_counter += 8
    return customers


CUSTOMERS = build_customers()
BY_ID = {c["cust_id"]: c for c in CUSTOMERS}

# --- Deliberate structural scenarios ---------------------------------------

# S07/S08 CO-LOCATION: two unrelated businesses sharing a building.
# Give three pairs the same street+ZIP but different suites and different names.
for first, second, suite_a, suite_b in [
    (CUSTOMERS[0], CUSTOMERS[1], "400", "210"),
    (CUSTOMERS[6], CUSTOMERS[7], "120", "330"),
    (CUSTOMERS[14], CUSTOMERS[15], "2A", "2B"),
]:
    second["street_number"] = first["street_number"]
    second["street_name"] = first["street_name"]
    second["city"], second["state"], second["zip5"] = first["city"], first["state"], first["zip5"]
    first["suite"], second["suite"] = suite_a, suite_b
    first["flags"].append("co_location")
    second["flags"].append("co_location")

# S18 SIMILAR NAMES, DIFFERENT CITIES: must never merge.
CUSTOMERS[20]["name"] = "Saint Mary Medical Center"
CUSTOMERS[21]["name"] = "Saint Mary Medical Center"
CUSTOMERS[21]["city"] = "Orlando"
CUSTOMERS[21]["state"] = "FL"
CUSTOMERS[21]["zip5"] = "32801"
CUSTOMERS[20]["flags"].append("name_twin")
CUSTOMERS[21]["flags"].append("name_twin")

# S19 SAME NAME, SAME CITY, DIFFERENT STREET: two campuses. Genuinely ambiguous.
CUSTOMERS[25]["name"] = "Summit Regional Hospital"
CUSTOMERS[26]["name"] = "Summit Regional Hospital"
CUSTOMERS[26]["city"] = CUSTOMERS[25]["city"]
CUSTOMERS[26]["zip5"] = CUSTOMERS[25]["zip5"]
CUSTOMERS[26]["street_number"] = "1802"
CUSTOMERS[26]["street_name"] = "Grant Parkway"
CUSTOMERS[25]["flags"].append("two_campus")
CUSTOMERS[26]["flags"].append("two_campus")

# S25 ACQUISITION: the entity was renamed. Old name still in the ERP.
CUSTOMERS[30]["former_name"] = "Northgate Community Hospital"
CUSTOMERS[30]["name"] = "Cascade Northgate Hospital"
CUSTOMERS[30]["flags"].append("renamed")

# S26 RELOCATION: same customer, new address since February.
CUSTOMERS[33]["former_street_number"] = "45"
CUSTOMERS[33]["former_street_name"] = "Pine Avenue"
CUSTOMERS[33]["flags"].append("relocated")

# S34 NON-ASCII characters in the name.
CUSTOMERS[36]["name"] = "Peña Blanca Family Clinic"
CUSTOMERS[36]["flags"].append("non_ascii")

# S35 ERP field truncated at 30 characters.
CUSTOMERS[38]["name"] = "Meadowbrook Cancer and Research Institute"
CUSTOMERS[38]["flags"].append("long_name")

# S43 INDEPENDENT: belongs to no IDN and no health system.
for customer in (CUSTOMERS[40], CUSTOMERS[41]):
    customer["idn_id"] = ""
    customer["health_system_id"] = ""
    customer["flags"].append("independent")

# S47 NOT IN REFERENCE DATA: a real customer the licensed dataset never heard of.
for customer in (CUSTOMERS[44], CUSTOMERS[45]):
    customer["in_reference"] = False
    customer["flags"].append("missing_reference")

# S28 DEPARTMENT-LEVEL SHIP-TO: sub-locations of one hospital.
CUSTOMERS[4]["departments"] = ["Pharmacy Dept", "Radiology", "Cardiac Cath Lab"]
CUSTOMERS[4]["flags"].append("departments")

# S21 NO SALES: exists in the ERP, never appears in any tracing file.
for customer in (CUSTOMERS[48], CUSTOMERS[49]):
    customer["no_sales"] = True
    customer["flags"].append("no_sales")

# S23 CRM ONLY: prospect in Salesforce, never in the ERP.
for customer in (CUSTOMERS[52], CUSTOMERS[53]):
    customer["crm_only"] = True
    customer["flags"].append("crm_only")

# S27 PO BOX: billing address is a PO Box, shipping is a street.
CUSTOMERS[56]["po_box"] = f"PO BOX {random.randint(100, 9999)}"
CUSTOMERS[56]["flags"].append("po_box")

# S48 NPI CONFLICT: two different customers, same street, different NPIs.
CUSTOMERS[57]["street_number"] = CUSTOMERS[58]["street_number"]
CUSTOMERS[57]["street_name"] = CUSTOMERS[58]["street_name"]
CUSTOMERS[57]["zip5"] = CUSTOMERS[58]["zip5"]
CUSTOMERS[57]["city"] = CUSTOMERS[58]["city"]
CUSTOMERS[57]["state"] = CUSTOMERS[58]["state"]
CUSTOMERS[57]["suite"] = "100"
CUSTOMERS[58]["suite"] = "200"
CUSTOMERS[57]["flags"].append("npi_conflict")
CUSTOMERS[58]["flags"].append("npi_conflict")


# ===========================================================================
# 2. Mutators - each one dirties a value and reports which scenario it is
# ===========================================================================

ABBREVIATIONS = {
    "Hospital": "Hosp", "Medical Center": "Med Ctr", "Center": "Ctr",
    "Regional": "Reg", "Community": "Comm", "Surgery": "Surg",
    "Institute": "Inst", "Outpatient": "Outpt", "Clinic": "Clnc",
    "Orthopedics": "Ortho", "Imaging": "Imgng", "Family": "Fam",
}

STREET_ABBREVIATIONS = {
    "Street": "St", "Drive": "Dr", "Boulevard": "Blvd", "Road": "Rd",
    "Avenue": "Ave", "Lane": "Ln", "Court": "Ct", "Place": "Pl",
    "Parkway": "Pkwy", "County Road": "CR", "North": "N", "South": "S",
}


def mut_name_abbreviate(value: str) -> tuple[str, str]:
    for long, short in ABBREVIATIONS.items():
        if long in value:
            return value.replace(long, short), "S02_ABBREVIATION"
    return value, ""


def mut_saint_to_st(value: str) -> tuple[str, str]:
    if value.startswith("Saint "):
        return "St " + value[6:], "S03_SAINT_VARIANT"
    return value, ""


def mut_pluralize(value: str) -> tuple[str, str]:
    for stem in ("Joseph", "Mary", "Luke"):
        if stem in value:
            return value.replace(stem, stem + "s"), "S04_POSSESSIVE_PLURAL"
    return value, ""


def mut_ocr(value: str) -> tuple[str, str]:
    digits = [i for i, ch in enumerate(value) if ch in "01"]
    if not digits:
        return value, ""
    index = random.choice(digits)
    swap = {"0": "O", "1": "I"}[value[index]]
    return value[:index] + swap + value[index + 1:], "S05_OCR_DAMAGE"


def mut_street_abbreviate(value: str) -> tuple[str, str]:
    for long, short in STREET_ABBREVIATIONS.items():
        if long in value:
            return value.replace(long, short), "S37_STREET_ABBREVIATION"
    return value, ""


def mut_collapse_spacing(value: str) -> tuple[str, str]:
    for spaced, collapsed in [("Lake Shore", "Lakeshore"), ("Silver Creek", "Silvercreek"),
                              ("Cedar Ridge", "Cedarridge"), ("Harbor Point", "Harborpoint")]:
        if spaced in value:
            return value.replace(spaced, collapsed), "S09_SPACING_VARIANT"
    return value, ""


def mut_truncate_street(value: str) -> tuple[str, str]:
    parts = value.split()
    if len(parts) > 2:
        return " ".join(parts[:2]), "S14_TRUNCATED_STREET"
    return value, ""


def mut_legal_suffix(value: str) -> tuple[str, str]:
    return value + random.choice([", Inc.", " LLC", ", P.C.", " Inc"]), "S15_LEGAL_SUFFIX"


def mut_ampersand(value: str) -> tuple[str, str]:
    if " and " in value:
        return value.replace(" and ", " & "), "S16_AMPERSAND"
    return value, ""


def mut_dba(value: str) -> tuple[str, str]:
    return f"{value} d/b/a {value.split()[0]} Health", "S17_DBA"


def mut_city_typo(value: str) -> tuple[str, str]:
    if len(value) < 5:
        return value, ""
    index = random.randrange(2, len(value) - 1)
    return value[:index] + value[index + 1:], "S13_CITY_TYPO"


def mut_zip_transpose(value: str) -> tuple[str, str]:
    if len(value) != 5:
        return value, ""
    return value[0] + value[2] + value[1] + value[3:], "S12_WRONG_ZIP"


def mut_lowercase(value: str) -> tuple[str, str]:
    return value.lower(), "S33_CASE_VARIANT"


def mut_whitespace(value: str) -> tuple[str, str]:
    return f"  {value.replace(' ', '  ', 1)} ", "S32_WHITESPACE"


def mut_strip_accents(value: str) -> tuple[str, str]:
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn"
    )
    return (stripped, "S34_ACCENT_STRIPPED") if stripped != value else (value, "")


NAME_MUTATORS = [mut_name_abbreviate, mut_saint_to_st, mut_pluralize, mut_legal_suffix,
                 mut_ampersand, mut_lowercase, mut_whitespace, mut_strip_accents, mut_dba]
STREET_MUTATORS = [mut_street_abbreviate, mut_collapse_spacing, mut_truncate_street, mut_ocr]


# ===========================================================================
# 3. Emit the source systems
# ===========================================================================

scenario_rows: list[dict] = []
ground_truth: list[dict] = []


def log_scenarios(source: str, record_id: str, scenarios: list[str], cust_id: str) -> None:
    scenario_rows.append({
        "source_system": source,
        "source_record_id": record_id,
        "true_customer_id": cust_id,
        "scenarios": "|".join(sorted(set(s for s in scenarios if s))) or "S01_CLEAN",
    })


def full_street(customer: dict) -> str:
    return f"{customer['street_number']} {customer['street_name']}"


# --- ERP -------------------------------------------------------------------

def write_erp() -> None:
    rows = []
    for customer in CUSTOMERS:
        if customer.get("crm_only"):
            continue

        name = customer.get("former_name", customer["name"])   # S25: pre-acquisition name
        if "long_name" in customer["flags"]:
            name = name[:30]                                    # S35: 30-char field
        name, scenario_a = mut_name_abbreviate(name)
        name, scenario_b = mut_saint_to_st(name)
        name = name.upper()

        street = full_street(customer)
        if "relocated" in customer["flags"]:                    # S26: stale address
            street = f"{customer['former_street_number']} {customer['former_street_name']}"
        street, scenario_c = mut_street_abbreviate(street)

        # S52: THREE address lines, and the suite can be on any of them. Real
        # ERP extracts look exactly like this and the brief calls it out.
        line_2 = line_3 = ""
        if customer["suite"]:
            if random.random() < 0.5:
                line_2 = f"STE {customer['suite']}"
            else:
                line_3 = f"SUITE {customer['suite']}"
        elif random.random() < 0.2:
            line_2 = random.choice(["ATTN RECEIVING", "LOADING DOCK B", "C/O MATERIALS MGMT"])

        record_id = f"E{1000 + len(rows) + 1}"
        rows.append({
            "erp_customer_id": record_id,
            "customer_name": name,
            "address_line_1": street.upper(),
            "address_line_2": line_2,
            "address_line_3": line_3,
            "city": customer["city"].upper(),
            "state": customer["state"],
            "postal_code": customer["zip5"],
            "legacy_customer_id": customer["cust_id"],
        })
        log_scenarios("erp", record_id, [scenario_a, scenario_b, scenario_c] +
                      (["S25_RENAMED"] if "renamed" in customer["flags"] else []) +
                      (["S26_RELOCATED"] if "relocated" in customer["flags"] else []) +
                      (["S35_TRUNCATED_NAME"] if "long_name" in customer["flags"] else []),
                      customer["cust_id"])

    # S24: the same hospital keyed twice in the ERP, years apart.
    for source_index in (3, 11):
        original = dict(rows[source_index])
        record_id = f"E{2000 + source_index}"
        original["erp_customer_id"] = record_id
        original["customer_name"] = original["customer_name"].replace("HOSPITAL", "HOSP")
        original["address_line_1"] = original["address_line_1"].replace("STREET", "ST")
        rows.append(original)
        log_scenarios("erp", record_id, ["S24_INTRA_SOURCE_DUPLICATE"], original["legacy_customer_id"])

    _write("erp_customer_master.csv", rows)


# --- Salesforce ------------------------------------------------------------

def write_salesforce() -> None:
    rows = []
    for index, customer in enumerate(CUSTOMERS):
        if customer.get("no_sales") and index % 2 == 0:
            continue

        name = customer["name"]
        scenarios = []
        if random.random() < 0.25:
            name, scenario = random.choice([mut_legal_suffix, mut_ampersand])(name)
            scenarios.append(scenario)

        street = full_street(customer)
        if "po_box" in customer["flags"]:                       # S27: PO Box billing
            street = customer["po_box"]
            scenarios.append("S27_PO_BOX")

        postal = customer["zip5"]
        if random.random() < 0.4:                               # S11: ZIP+4
            postal = f"{customer['zip5']}-{customer['zip4']}"
            scenarios.append("S11_ZIP_PLUS_FOUR")

        record_id = f"SF-{500 + len(rows) + 1}"
        rows.append({
            "sf_account_id": record_id,
            "account_name": name,
            "billing_street": street,
            "billing_suite": f"Suite {customer['suite']}" if customer["suite"] else "",
            "billing_city": customer["city"],
            "billing_state": customer["state"],
            "billing_zip": postal,
            # S20: the NPI is present in the CRM for only some records
            "npi_number": customer["npi"] if random.random() < 0.7 else "",
        })
        log_scenarios("salesforce", record_id, scenarios, customer["cust_id"])

    _write("salesforce_accounts.csv", rows)


# --- Licensed provider reference ------------------------------------------

def write_reference() -> None:
    rows = []
    for customer in CUSTOMERS:
        if customer.get("in_reference") is False:               # S47
            continue
        idn_name = health_system_name = ""
        for hs_id, hs_label, idns in HEALTH_SYSTEMS:
            for idn_id, idn_label, *_ in idns:
                if idn_id == customer["idn_id"]:
                    idn_name, health_system_name = idn_label, hs_label
        rows.append({
            "npi": customer["npi"],
            "organization_name": customer["name"],
            "address_line": full_street(customer) + (f" Suite {customer['suite']}" if customer["suite"] else ""),
            "city": customer["city"],
            "state": customer["state"],
            "zip5": customer["zip5"],
            "zip4": customer["zip4"],
            "idn_id": customer["idn_id"],
            "idn_name": idn_name,
            "health_system_id": customer["health_system_id"],
            "health_system_name": health_system_name,
        })
    _write("provider_reference.csv", rows)


def write_gpo() -> None:
    rows = []
    for customer in CUSTOMERS:
        for gpo_id in customer.get("gpos", []):                 # S45: some have two
            name = next(label for identifier, label in GPOS if identifier == gpo_id)
            rows.append({
                "gpo_id": gpo_id,
                "gpo_name": name,
                "npi": customer["npi"],
                "member_since": f"20{random.randint(15, 24)}-{random.randint(1, 12):02d}-01",
            })
    _write("gpo_roster.csv", rows)


# --- Tracing files ---------------------------------------------------------

PRODUCTS = ["DEV-1180", "DEV-2200", "DEV-3050", "DEV-4410", "DEV-5500"]


def dirty_tracing_identity(customer: dict) -> tuple[str, str, str, str, str, list[str]]:
    """Apply a random handful of defects to one customer's identity."""
    scenarios = []

    name = customer["name"]
    for mutator in random.sample(NAME_MUTATORS, k=random.randint(0, 3)):
        name, scenario = mutator(name)
        if scenario:
            scenarios.append(scenario)

    street = full_street(customer)
    for mutator in random.sample(STREET_MUTATORS, k=random.randint(0, 2)):
        street, scenario = mutator(street)
        if scenario:
            scenarios.append(scenario)

    suite = customer["suite"]
    if suite:
        roll = random.random()
        if roll < 0.30:                                         # S06: suite inside the name
            name = f"{name} STE {suite}"
            suite = ""
            scenarios.append("S06_SUITE_IN_NAME")
        elif roll < 0.50:                                       # S08: suite dropped entirely
            suite = ""
            scenarios.append("S08_SUITE_MISSING")
        else:
            street = f"{street} Ste {suite}"
            suite = ""

    city = customer["city"]
    if random.random() < 0.12:
        city, scenario = mut_city_typo(city)
        scenarios.append(scenario)

    postal = customer["zip5"]
    if random.random() < 0.06:
        postal, scenario = mut_zip_transpose(postal)
        scenarios.append(scenario)
    elif random.random() < 0.05:                                # S30: no ZIP at all
        postal = ""
        scenarios.append("S30_MISSING_ZIP")

    if random.random() < 0.04:                                  # S31: no street at all
        street = ""
        scenarios.append("S31_MISSING_STREET")

    return name.upper(), street.upper(), city.upper(), customer["state"], postal, scenarios


def write_alpha() -> None:
    """Daily EDI drop. High volume, dirtiest source."""
    rows = []
    sellable = [c for c in CUSTOMERS if not c.get("no_sales") and not c.get("crm_only")]

    for customer in sellable:
        for _ in range(random.randint(1, 4)):                   # S38: many sales per customer
            name, street, city, state, postal, scenarios = dirty_tracing_identity(customer)

            if "departments" in customer["flags"] and random.random() < 0.5:
                name = f"{name} - {random.choice(customer['departments']).upper()}"
                scenarios.append("S28_DEPARTMENT_SHIPTO")

            record_id = f"A-{100001 + len(rows)}"
            quantity = random.randint(1, 40)
            amount = round(quantity * random.uniform(80, 400), 2)

            if random.random() < 0.03:                          # S39: a return
                quantity, amount = -quantity, -amount
                scenarios.append("S39_NEGATIVE_AMOUNT")
            if random.random() < 0.03:                          # S40: missing measures
                quantity, amount = "", ""
                scenarios.append("S40_NULL_MEASURES")

            rows.append({
                "trace_id": record_id,
                "invoice_date": f"2026-03-{random.randint(1, 28):02d}",
                "ship_to_name": name,
                "ship_to_address": street,
                "ship_to_city": city,
                "ship_to_state": state,
                "ship_to_zip": postal,
                "product_code": random.choice(PRODUCTS),
                "quantity": quantity,
                "net_sales_amount": amount,
            })
            log_scenarios("distributor_alpha", record_id, scenarios, customer["cust_id"])
            ground_truth.append({
                "source_system": "distributor_alpha",
                "source_record_id": record_id,
                "true_customer_id": customer["cust_id"],
            })

    # S22: customers that exist nowhere else in the business.
    for unknown in ["VALLEY URGENT CARE", "NORTHSHORE PEDIATRIC GROUP", "DESERT SPRINGS CLINIC",
                    "PINE HOLLOW WELLNESS", "STONEBRIDGE DIALYSIS"]:
        record_id = f"A-{100001 + len(rows)}"
        rows.append({
            "trace_id": record_id,
            "invoice_date": f"2026-03-{random.randint(1, 28):02d}",
            "ship_to_name": unknown,
            "ship_to_address": f"{random.randint(10, 999)} UNKNOWN ROAD",
            "ship_to_city": random.choice(["BEND", "ROCKFORD", "OCALA", "BOULDER"]),
            "ship_to_state": random.choice(["OR", "IL", "FL", "CO"]),
            "ship_to_zip": str(random.randint(10000, 99999)),
            "product_code": random.choice(PRODUCTS),
            "quantity": random.randint(1, 5),
            "net_sales_amount": round(random.uniform(200, 900), 2),
        })
        log_scenarios("distributor_alpha", record_id, ["S22_UNKNOWN_CUSTOMER"], "")
        ground_truth.append({
            "source_system": "distributor_alpha", "source_record_id": record_id,
            "true_customer_id": "",
        })

    # S41: the same row delivered twice in one file.
    for source_index in (5, 40):
        duplicate = dict(rows[source_index])
        record_id = f"A-{100001 + len(rows)}"
        duplicate["trace_id"] = record_id
        rows.append(duplicate)
        truth = next(g["true_customer_id"] for g in ground_truth
                     if g["source_record_id"] == rows[source_index]["trace_id"])
        log_scenarios("distributor_alpha", record_id, ["S41_DUPLICATE_ROW"], truth)
        ground_truth.append({
            "source_system": "distributor_alpha", "source_record_id": record_id,
            "true_customer_id": truth,
        })

    _write("distributor_alpha_tracing_2026-03.csv", rows)


def write_beta() -> None:
    """Monthly manual drop. Different column names, combined city/state/ZIP,
    US date format."""
    rows = []
    sellable = [c for c in CUSTOMERS if not c.get("no_sales") and not c.get("crm_only")]

    for customer in random.sample(sellable, k=int(len(sellable) * 0.7)):
        for _ in range(random.randint(1, 2)):
            name, street, city, state, postal, scenarios = dirty_tracing_identity(customer)
            scenarios.append("S10_COMBINED_CITY_STATE_ZIP")

            postal_display = postal
            if postal and random.random() < 0.35:
                postal_display = f"{postal}-{customer['zip4']}"
                scenarios.append("S11_ZIP_PLUS_FOUR")

            record_id = f"B-{77001 + len(rows)}"
            quantity = random.randint(1, 25)
            rows.append({
                "RecordID": record_id,
                # S50: a different date format from Alpha
                "SaleDate": f"{random.randint(1, 12):02d}/{random.randint(1, 28):02d}/2026",
                "CustomerName": name.title(),
                "Street": street.title(),
                "CityStateZip": f"{city.title()}, {state} {postal_display}".strip(),
                "Item": random.choice(PRODUCTS),
                "Qty": quantity,
                "Amount": round(quantity * random.uniform(80, 400), 2),
            })
            log_scenarios("distributor_beta", record_id, scenarios, customer["cust_id"])
            ground_truth.append({
                "source_system": "distributor_beta", "source_record_id": record_id,
                "true_customer_id": customer["cust_id"],
            })

    # S42: rows already delivered by Alpha, re-reported by Beta.
    _write("distributor_beta_tracing_2026-03.csv", rows)


def write_gamma() -> None:
    """April file, for the incremental demo."""
    rows = []
    sellable = [c for c in CUSTOMERS if not c.get("no_sales") and not c.get("crm_only")]

    for customer in random.sample(sellable, k=25):
        name, street, city, state, postal, scenarios = dirty_tracing_identity(customer)
        record_id = f"G-{900001 + len(rows)}"
        quantity = random.randint(1, 30)
        rows.append({
            "trace_id": record_id,
            "invoice_date": "2026-04-01",
            "ship_to_name": name,
            "ship_to_address": street,
            "ship_to_city": city,
            "ship_to_state": state,
            "ship_to_zip": postal,
            "product_code": random.choice(PRODUCTS),
            "quantity": quantity,
            "net_sales_amount": round(quantity * random.uniform(80, 400), 2),
        })
        log_scenarios("distributor_gamma", record_id, scenarios, customer["cust_id"])

    # Brand-new customers that must open new canonical records.
    for new_customer in ["LAKEVIEW ORTHOPEDIC PARTNERS", "CRESTWOOD SURGERY CENTER"]:
        record_id = f"G-{900001 + len(rows)}"
        rows.append({
            "trace_id": record_id,
            "invoice_date": "2026-04-01",
            "ship_to_name": new_customer,
            "ship_to_address": f"{random.randint(100, 999)} NEW STREET",
            "ship_to_city": "PEORIA",
            "ship_to_state": "IL",
            "ship_to_zip": "61602",
            "product_code": random.choice(PRODUCTS),
            "quantity": random.randint(1, 10),
            "net_sales_amount": round(random.uniform(300, 2000), 2),
        })
        log_scenarios("distributor_gamma", record_id, ["S23_NEW_CUSTOMER_IN_INCREMENT"], "")

    _write("distributor_gamma_tracing_2026-04-01.csv", rows)


# --- Ground truth, as the humans would have recorded it --------------------

def write_legacy_decisions() -> None:
    """
    What the data integrity team produced by hand for March.

    Deliberately imperfect, because a real baseline is:
      - a few records they gave up on (recorded UNMATCHED even though the
        customer exists)
      - a couple they got WRONG
    If your ground truth is perfect, your evaluation is lying to you.
    """
    rows = []
    reviewers = ["j.reyes", "m.okoro", "s.patel", "system"]

    for index, truth in enumerate(ground_truth):
        customer_id = truth["true_customer_id"]
        level = "UNMATCHED" if not customer_id else random.choices(
            ["L1_EXACT_NAME_ADDRESS", "L2_EXACT_NAME_ZIP", "L3_FUZZY",
             "L4_ADDRESS_ONLY", "L5_LOOSE_ADDRESS"],
            weights=[15, 25, 35, 15, 10],
        )[0]

        if customer_id and random.random() < 0.04:              # they gave up
            customer_id, level = "", "UNMATCHED"
        elif customer_id and random.random() < 0.02:            # they got it wrong
            customer_id = random.choice(CUSTOMERS)["cust_id"]
            level = "L5_LOOSE_ADDRESS"

        rows.append({
            "decision_id": f"D-{index + 1:04d}",
            "source_system": truth["source_system"],
            "source_record_id": truth["source_record_id"],
            "legacy_customer_id": customer_id,
            "match_level": level,
            "decided_by": "system" if level.startswith(("L1", "L2")) else random.choice(reviewers[:3]),
            "decided_on": f"2026-04-{random.randint(6, 14):02d}",
        })

    _write("legacy_match_decisions.csv", rows)


# ===========================================================================

def _write(filename: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = os.path.join(OUT, filename)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {filename:<45} {len(rows):>4} rows")


def main() -> None:
    print(f"Generating sample data (seed {SEED})\n")
    write_erp()
    write_salesforce()
    write_reference()
    write_gpo()
    write_alpha()
    write_beta()
    write_gamma()
    write_legacy_decisions()
    _write("SCENARIO_CATALOGUE.csv", scenario_rows)
    _write("GROUND_TRUTH.csv", ground_truth)
    print(f"\n  {len(CUSTOMERS)} real customers hide in these files.")


if __name__ == "__main__":
    main()
