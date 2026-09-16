# Scenario catalogue

Every data defect deliberately planted in the sample files, why it matters, and
where to find examples.

The generator **knows** the right answer for every record, because it created
the mess. So `GROUND_TRUTH.csv` is correct by construction rather than by
someone's judgement — which is exactly what you never get on a real project,
and exactly what makes this useful for learning.

## The files

| File | Rows | Notes |
|---|---|---|
| `erp_customer_master.csv` | 63 | All caps, abbreviated, 30-char name field, holds the legacy id |
| `salesforce_accounts.csv` | 62 | Title case, some NPIs, ZIP+4 on some rows |
| `provider_reference.csv` | 61 | Licensed reference data. Two real customers are missing from it |
| `distributor_alpha_tracing_2026-03.csv` | 151 | Daily EDI drop. Dirtiest source |
| `distributor_beta_tracing_2026-03.csv` | 63 | Monthly manual drop. Different columns, combined city/state/ZIP, US dates |
| `distributor_gamma_tracing_2026-04-01.csv` | 27 | April file, for the incremental demo |
| `gpo_roster.csv` | 62 | Purchasing-organisation membership |
| `legacy_match_decisions.csv` | 214 | The human baseline — **deliberately imperfect** |
| `SCENARIO_CATALOGUE.csv` | 366 | record id → which defects it carries |
| `GROUND_TRUTH.csv` | 214 | record id → the customer it really is |

**63 real customers** hide in there. Everything else is a different spelling of
one of them.

## How to use the catalogue

```python
import pandas as pd
cat = pd.read_csv("SCENARIO_CATALOGUE.csv")

# all records carrying OCR damage
cat[cat.scenarios.str.contains("S05")]

# every defect on one record
cat[cat.source_record_id == "A-100042"]
```

After a pipeline run, `out/eval_scenario_scorecard.csv` gives you accuracy per
defect type. **That table is where you spend your time** — aggregate recall
tells you something is wrong, the scorecard tells you what.

---

## Text and formatting defects

| Code | Defect | Example | Why it matters |
|---|---|---|---|
| `S01_CLEAN` | No defect | — | Your control group. If these fail, something is badly wrong |
| `S02_ABBREVIATION` | `Hospital`→`Hosp`, `Medical Center`→`Med Ctr` | `MERCY GENERAL HOSP` | The single most common defect. Fixed by the abbreviation dictionary |
| `S03_SAINT_VARIANT` | `Saint`→`St` | `ST JOSEPH HOSPITAL` | `ST` is context-dependent: `SAINT` in a name, `STREET` in an address. Get it wrong and every Saint-something breaks |
| `S04_POSSESSIVE_PLURAL` | `Joseph`→`Josephs` | `ST JOSEPHS HOSPITAL` | Fixed by singularisation, applied symmetrically |
| `S15_LEGAL_SUFFIX` | `, Inc.` / ` LLC` / `, P.C.` | `Mercy General Hospital, Inc.` | Carries no identifying information. Drop as noise |
| `S16_AMPERSAND` | ` and `→` & ` | `Meadowbrook Cancer & Research` | Trivially fixed, easily forgotten |
| `S17_DBA` | Trading-as names | `X Hospital d/b/a X Health` | Doubles the name length and wrecks similarity scores. Needs explicit handling |
| `S32_WHITESPACE` | Leading, trailing, doubled spaces | `"  Mercy  General "` | Invisible in a spreadsheet, fatal to an exact match |
| `S33_CASE_VARIANT` | Lower case | `mercy general hospital` | Trivial — but only if you actually normalise case |
| `S34_ACCENT_STRIPPED` | `Peña`→`Pena` | Both forms appear | Encoding differences between systems. Normalise to NFD and strip marks |
| `S35_TRUNCATED_NAME` | ERP 30-char field limit | `Meadowbrook Cancer and Resea` | The name is *cut off*. No amount of cleaning recovers the missing characters — the match has to come from the address |

## Address defects

| Code | Defect | Why it matters |
|---|---|---|
| `S05_OCR_DAMAGE` | `400`→`4OO`, `1240`→`I240` | Hand-keyed and OCR'd files. Repair only inside mostly-numeric tokens so real words aren't damaged |
| `S09_SPACING_VARIANT` | `Lake Shore`→`Lakeshore` | Standardisation does **not** fix this. This is what the probabilistic pass is for |
| `S11_ZIP_PLUS_FOUR` | `97205-1142` vs `97205` | Split into ZIP5 and ZIP4; compare on ZIP5 |
| `S12_WRONG_ZIP` | Transposed digits | Your ZIP blocking key fails. This is why you need a name-prefix blocking key too |
| `S13_CITY_TYPO` | `PORTLND` | Harmless — nothing matches on city. Good demonstration that not every defect needs fixing |
| `S14_TRUNCATED_STREET` | `1240 Main Street`→`1240 Main` | Street similarity drops sharply. Recovered by house-number blocking |
| `S27_PO_BOX` | Billing is a PO Box, shipping is a street | Two legitimate addresses for one customer. Never merge them into one address |
| `S30_MISSING_ZIP` | Blank ZIP | Loses a blocking key. Must not crash, must not match everything |
| `S31_MISSING_STREET` | Blank street | Same |
| `S37_STREET_ABBREVIATION` | `Street`→`St`, `County Road`→`CR` | The address-side twin of S02 |

## Suite and co-location defects

The most consequential group. Read this section twice.

| Code | Defect | Why it matters |
|---|---|---|
| `S06_SUITE_IN_NAME` | `ST JOSEPH HOSPITAL STE 400` | The suite is in the **name** field. Extract it before comparing names, or the name never matches |
| `S08_SUITE_MISSING` | Suite dropped entirely | **The dangerous one.** "no suite" vs "suite 120" at the same street looks like a match on address evidence alone |
| `co_location` (structural) | Two unrelated businesses, one building, different suites | Three pairs in the data. Without the co-location guard these merge, and the client silently loses a customer |

Find them:

```python
cat[cat.scenarios.str.contains("S08")]
```

## Identity and structural defects

| Code | Defect | Why it matters |
|---|---|---|
| `S20` (implicit) | NPI present in only ~70% of Salesforce rows | You cannot rely on the strongest identifier being there |
| `S22_UNKNOWN_CUSTOMER` | 5 customers that exist nowhere but one tracing file | Must stay unmatched. Forcing them somewhere is a precision failure |
| `S24_INTRA_SOURCE_DUPLICATE` | The same hospital keyed twice in the ERP | Deduplication is not only cross-source. Two ERP rows must collapse into one customer |
| `S25_RENAMED` | Acquired and renamed; the ERP still has the old name | Same address, different name. Matching on name alone fails |
| `S26_RELOCATED` | Same customer, new address; the ERP is stale | **The hardest class of problem.** Same name, different address. Genuinely needs a human, and hints at why real MDM systems need a time dimension |
| `S28_DEPARTMENT_SHIPTO` | `... - PHARMACY DEPT`, `- RADIOLOGY` | Is a department a customer, or part of one? This is the "what is a customer?" question made concrete |
| `S47` (structural) | Two real customers absent from the reference dataset | They get no hierarchy. Must not break the pipeline |
| `npi_conflict` (structural) | Same street, different NPIs | Two distinct organisations sharing a building. The NPI is the proof they're different |
| `name_twin` (structural) | `Saint Mary Medical Center` in Portland **and** Orlando | Identical names, different cities. Must never merge |
| `two_campus` (structural) | `Summit Regional Hospital`, same city, two streets | Genuinely ambiguous. One customer with two sites, or two customers? A human decides |

## Transaction defects

| Code | Defect | Why it matters |
|---|---|---|
| `S38` (implicit) | Several sales per customer | The normal case. Identity is 1:1, sales are many:1 |
| `S39_NEGATIVE_AMOUNT` | Returns and credits | Must not be dropped. Roll-ups that ignore negatives overstate sales |
| `S40_NULL_MEASURES` | Blank quantity/amount | Must not crash aggregation |
| `S41_DUPLICATE_ROW` | The same sale delivered twice | Double-counts revenue if you don't catch it |
| `S50` (implicit) | `2026-03-02` vs `03/02/2026` | Two date formats across sources. Parse per source, never globally |

## Hierarchy structure

| Structure | Where | Why it matters |
|---|---|---|
| Facilities in multiple states under one system | `HS-500 Heartland Partners` (MN + IA) | Don't assume a health system lives in one place |
| Independent facilities | 2 customers, no IDN | The hierarchy must tolerate orphans |
| Two GPO memberships | Several customers | GPO is a **membership edge**, not a tree level. Model it as a level and a customer with two GPOs breaks it |
| No GPO | Several customers | Absence is normal |

## About the human baseline

`legacy_match_decisions.csv` is **deliberately imperfect**:

- ~4% of resolvable records were given up on and recorded `UNMATCHED`
- ~2% were matched to the **wrong** customer

This is realistic, and it matters for how you read your metrics. If your
matcher disagrees with a human, it is not automatically wrong — sometimes the
machine is right and the human was tired on a Friday afternoon.

Compare against `GROUND_TRUTH.csv` to see which is which. On a real project you
won't have that luxury, which is precisely why sampling disagreements by hand is
part of the method rather than an optional extra.

---

## Current results

From the run in `SAMPLE_RUN_OUTPUT.txt`:

| | Cold | Seeded |
|---|---|---|
| Precision | 92.3% | 92.1% |
| Recall | 85.7% | 88.8% |
| Canonical customers | 88 | 79 |
| Automation rate | 78.5% | 86.0% |

63 real customers, 79 canonical records. **There is real work left to do here**
— and that's on purpose. The earlier 12-record dataset hit 100% and taught you
nothing about debugging.

The scenario scorecard says where to start. At the time of writing the worst
offenders are `S17_DBA` (64%), `S30_MISSING_ZIP` (58%) and `S08_SUITE_MISSING`
(67%). Each one points at a different fix: a standardisation rule, a blocking
key, and a guard threshold respectively.

**That's your practice material.** Pick the worst row in the scorecard, work out
why it's failing, fix it, re-run, watch the number move.
