# Data issues

Defects found while profiling the source files. My own catalogue — IDs are mine.

**Status:** first pass, ERP and Salesforce only. Not complete. Add to this as
you profile the remaining six sources and as new defects surface during the
build.

Each entry: what it is, where, how often, and — the part that matters — what it
forces the design to do.

---

## D-001 — ERP name field truncated at 30 characters

**Source:** `erp_customer_master.customer_name`
**Frequency:** 1 of 63 sits at exactly 30; 2 sit at 28 or more
**Example:** `E1039` → `MEADOWBROOK CANCER AND RESEARC`

`max_len` is exactly 30 and the longest value ends mid-word. That's a database
field limit, not a naming style.

The same customers reach 45 characters in Salesforce, which confirms it: one
system can hold the full name, the other cannot.

**Impact:** the missing characters are gone permanently. No standardisation
recovers them. For these records the match has to come from the address, and a
name comparison will score low no matter how good the standardiser is. Low
frequency here, but on a real ERP extract this could be a large fraction.

---

## D-002 — ERP abbreviates, Salesforce spells words out

**Source:** `erp_customer_master` vs `salesforce_accounts`
**Frequency:** pervasive — shortest ERP name is 11 chars, shortest Salesforce
name is 16
**Example:** ERP `MERCY ORTHO` ↔ Salesforce `Mercy Orthopedics`

The ERP writes `HOSP`, `CTR`, `MED`, `ORTHO`. Salesforce writes `Hospital`,
`Center`, `Medical`, `Orthopedics`.

**Impact:** the core reason a deterministic name match fails across sources.
Every abbreviation pair is a rule the standardiser needs. The token-frequency
comparison between these two files is how to enumerate them — that list becomes
the abbreviation dictionary.

---

## D-003 — `address_line_2` is not a suite column

**Source:** `erp_customer_master.address_line_2`
**Frequency:** 15 of 63 populated, of which **only 4 are suites** — 11 are
delivery instructions
**Examples:** `C/O MATERIALS MGMT`, `ATTN RECEIVING`, `LOADING DOCK B`

The column is a free-text second address line. Most of what's in it has nothing
to do with a suite.

**Impact:** a suite extractor that trusts the column position would pull
`MATERIALS MGMT` out as a suite identifier and compare it against `400`. The
extractor must detect the **pattern** (`STE`, `SUITE`, `UNIT`, `#`, `RM`),
never the column. And it must scan line 1, line 2, line 3 and the name field,
because the suite turns up in all of them.

---

## D-004 — Suites are recorded for only ~13% of customers

**Source:** both
**Frequency:** ERP 8 of 63 (across lines 2 and 3); Salesforce 8 of 62
**Format differs:** ERP writes `STE 400`, Salesforce writes `Suite 400`

**Impact:** two consequences, pulling in opposite directions.

1. The extractor must handle both spellings.
2. More importantly — a **missing suite is not evidence of absence**. When one
   record has `Suite 120` and the other has nothing, that could be the same
   customer sloppily recorded, or two different tenants of one building. With
   only 13% coverage, this case will be common. It is the crux of the
   co-location problem and cannot be resolved by the score alone.

---

## D-005 — Mixed ZIP formats in one column

**Source:** `salesforce_accounts.billing_zip`
**Frequency:** 35 of 62 are 5 characters, 27 are 10 (ZIP+4)
**Example:** `61602-7896` and `61602` for the same city

**Impact:** direct and already demonstrated. A duplicate check on
`account_name` + `billing_zip` returned **0**; the same check on name + first 5
digits returned **1** — the two `Summit Regional Hospital` campuses. The raw
column silently hid a real pair.

Split into `zip5` and `zip4` and compare on `zip5`. Also a warning for
blocking: any key built on the raw ZIP will fail on a third of rows.

---

## D-006 — Names are not identifying

**Source:** `salesforce_accounts.account_name`
**Frequency:** 14 of 62 rows (7 pairs) share a name with another row
**Examples:**

| Name | Locations | Same customer? |
|---|---|---|
| `Saint Mary Medical Center` | Chicago 60611 / Orlando 32801 | **No** — unrelated |
| `Lakeview Hospital` | Portland 97205 / Denver 80202 | **No** — unrelated |
| `Summit Regional Hospital` | Peoria, two streets | Two campuses, two legacy IDs |
| `Willamette Outpatient Center` | Portland / Eugene | Unclear — check against ERP |

**Impact:** the most consequential finding so far. Eleven percent of CRM rows
share a name, and most of those pairs are genuinely different organisations.

- Name-only blocking would be useless
- Name-heavy scoring is dangerous — identical names deserve **less** weight
  than intuition suggests
- ZIP and street carry the discriminating power
- These pairs are the first things that will wrongly merge if the thresholds
  are ever loosened to chase recall. Use them as regression tests.

---

## D-007 — The same customer keyed twice in the ERP

**Source:** `erp_customer_master`
**Frequency:** 4 rows, 2 pairs
**Examples:**

```
E1004 / E2003   BROOKSIDE SURGERY CTR    L-0004
E1012 / E2011   WILLAMETTE CANCER INST   L-0012
```

Each pair shares a `legacy_customer_id`, so the client **already considers them
one customer**. Different ERP row IDs, same everything else.

**Impact:** deduplication is not only a cross-source problem. One system
contains the same customer twice, and the pipeline must collapse these.

Also useful as a free label: these are known-true pairs that cost nothing to
obtain, unlike the human match decisions.

---

## D-008 — NPI present on only 73% of CRM records

**Source:** `salesforce_accounts.npi_number`
**Frequency:** 45 of 62 populated; all 45 distinct

Where it exists the NPI is a perfect identifier — no collisions at all.

**Impact:** strong enough to be a top-priority deterministic rule, nowhere near
complete enough to be the backbone of the design. A pipeline built around NPI
as the primary key would silently drop a quarter of the CRM. It is also the
only join to `provider_reference` and therefore to the hierarchy — so records
without an NPI get no hierarchy unless matching supplies one.

---

## D-009 — The ERP abbreviates what every other source spells out

**Source:** `erp_customer_master` vs `salesforce_accounts`
**Method:** token frequency per source, then the tokens present in one file only
**Frequency:** pervasive — 7 distinct abbreviations covering 78 token
occurrences in the ERP

| ERP | count | Salesforce | count |
|---|---|---|---|
| `CTR` | 22 | `CENTER` | 21 |
| `HOSP` | 19 | `HOSPITAL` | 20 |
| `INST` | 11 | `INSTITUTE` | 11 |
| `ST` | 9 | `SAINT` | 9 |
| `ORTHO` | 7 | `ORTHOPEDICS` | 7 |
| `MED` | 7 | `MEDICAL` | 6 |
| `CLNC` | 3 | `CLINIC` | 3 |

The counts pair up almost exactly because it is the same word describing the
same customers, written two different ways.

**Noise tokens, Salesforce only:** `LLC` (5), `INC` (3). The ERP never carries
a legal suffix. These identify nothing and should be dropped before comparing.

**Impact:** this table **is** the abbreviation dictionary that
`standardize_name` needs. Without it, an ERP name will essentially never match
a Salesforce name — 78 token occurrences is most of the name text in the file.

**Note on `ST`:** it appears 9 times in ERP names and `SAINT` 9 times in
Salesforce, so the mapping is certain. But `ST` also means `STREET` in an
address. The rule has to be context-dependent — `SAINT` when it leads a name,
`STREET` in an address line. Getting this backwards breaks every
Saint-something hospital silently.

---

## D-010 — Punctuation splits tokens that should be identical

**Source:** `salesforce_accounts.account_name`
**Frequency:** low in this sample, but structural
**Example:** `SF-560` → `Silver Creek Hospital, Inc.`

Splitting on whitespace yields `['Silver', 'Creek', 'Hospital,', 'Inc.']`. The
token `Hospital,` — with a trailing comma — is a different string from
`Hospital`, so it never matches any rule looking for a clean token.

Found by accident: an Excel substring filter for "Hospital" returned 20 rows
while the token count returned 19. The missing one was the comma.

**Impact:** dictates the **order of operations** inside `standardize_name`:

1. upper-case
2. strip punctuation
3. *then* tokenise
4. *then* expand abbreviations
5. *then* drop noise tokens

Do it in any other order and `Hospital,` never reaches the `HOSP → HOSPITAL`
rule. Replace punctuation with a **space**, not an empty string, or
`Saint-Luke` becomes `SAINTLUKE` instead of two clean tokens.

---

## D-011 — Neither internal system holds the full customer population

**Source:** `erp_customer_master` vs `salesforce_accounts`
**Frequency:** 51 normalised names in both, 2 ERP-only, 4 Salesforce-only

Realistic: the CRM holds prospects who never bought anything; the ERP holds
customers who only ever came through a distributor and never got a CRM record.

**Impact:** neither source can be treated as the master list of who is a
customer. A record appearing in only one source is not automatically an error,
which matters for the exception queue — "matched nothing" has to distinguish
*genuinely new* from *we failed to match it*.

**Also:** `MEADOWBROOK CANCER AND RESEARC` shows as ERP-only while Salesforce
has `MEADOWBROOK CANCER AND RESEARCH INSTITUTE`. Same hospital. It fails to
match **purely because of the 30-character truncation in D-001** — concrete
proof that the truncation costs a match, not just a tidy name.

---

## D-012 — Tracing names carry suites, trading names and OCR damage

**Source:** `distributor_alpha_tracing_2026-03.ship_to_name`
**Method:** token comparison against ERP names; suite-pattern search per column

**Suite location — the decisive finding:**

| File | Column | Hits |
|---|---|---|
| erp | `address_line_2` | 4 |
| erp | `address_line_3` | 4 |
| alpha | `ship_to_name` | **4** |
| alpha | `ship_to_address` | 14 |

Examples from the name field:

```
A-100004  LAKEVIEW ORTHOPEDICS STE 210
A-100042  BROOKSIDE OUTPATIENT CTR STE 2B
A-100139  SAINT  JOSEPHS IMAGING CTR  STE 200
```

**Trading names:** `WILLAMETTE OUTPATIENT CENTER D/B/A WILLAMETTE HEALTH`.
Roughly doubles the string. The slashes shred into single-letter tokens —
`D` (26) and `B` (26) are among the most frequent tokens in the whole file.

**`P.C.`** does the same: `P` (11) and `C` (11).

**OCR damage, visible in the raw addresses:**

```
I240 CEDAR LANE    ← capital I instead of 1
18O2 CEDAR LANE    ← letter O instead of 0
```

**Stray suite numbers** left in names after the `STE` token: `210`, `330`,
`200`.

**Same abbreviation pairs as D-009, at larger volume:** `CENTER` 38,
`HOSPITAL` 37, `INSTITUTE` 25, `SAINT` 20, `ORTHOPEDICS` 18, `CLINIC` 9,
`MEDICAL` 8. The dictionary holds.

**Impact — three concrete design consequences:**

1. `extract_suite()` must accept **several candidate strings**, not a single
   address line. The name field is one of them. Every caller has to pass it.
2. `standardize_name()` must strip the `d/b/a` clause **before** tokenising,
   or the trading half of the name drowns the real half in any similarity
   score.
3. Digit/letter repair (`I`→`1`, `O`→`0`) is needed, but **only on tokens that
   are already mostly numeric** — otherwise it damages real words.

---

## Evidence for the "what is a customer?" question

Not a defect, but the profiling answered it. Recorded here, decision lives in
`docs/DECISIONS.md`.

```
E1026   SUMMIT REGIONAL HOSP   900 SUMMIT DR      L-0026
E1027   SUMMIT REGIONAL HOSP   1802 GRANT PKWY    L-0027
```

Same name, same ZIP, different streets — and **different legacy customer IDs**.
The client treats two campuses of one hospital as two customers.

If their grain were the legal entity, these would share an ID. They don't. So
the grain is closer to the **ship-to location**.

Contrast with D-007, where two rows describing the same physical place **do**
share an ID.

---

## Still to profile

- [ ] `provider_reference`
- [ ] `distributor_alpha_tracing_2026-03`
- [ ] `distributor_beta_tracing_2026-03`
- [ ] `distributor_gamma_tracing_2026-04-01`
- [ ] `gpo_roster`
- [ ] `legacy_match_decisions`

## Still to investigate

- [x] Token frequency on names, ERP vs Salesforce — done, see D-009
- [x] Same token comparison against the **tracing files** — done, see D-012
- [ ] Is `MERCY ORTHO` (11 chars) a genuinely short name or another truncation?
- [ ] Are the two `Willamette Outpatient Center` rows in Salesforce the same two
      that appear in the ERP?
- [x] How often does a suite appear inside the **name** field — done, see D-012
- [ ] Exact duplicate rows and negative amounts in the tracing files
