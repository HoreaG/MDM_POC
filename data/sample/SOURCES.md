# The source files

What you'd receive at handover on the real project, what each one represents,
and how they connect.

This is the document to read before you write any code — and it's deliberately
written the way a handover actually arrives: describing the *systems*, not the
answers.

---

## What you get, and what you don't

Eight files. All eight are things the client (or a data vendor) genuinely
produces. Nothing here is a hint.

| File | Who produces it | Rows |
|---|---|---|
| `erp_customer_master.csv` | The client's ERP (IBM i / DB2 for i) | 63 |
| `salesforce_accounts.csv` | The client's CRM | 62 |
| `provider_reference.csv` | A licensed healthcare data vendor | 61 |
| `gpo_roster.csv` | Purchasing organisations / the vendor | 62 |
| `distributor_alpha_tracing_2026-03.csv` | Distributor A, daily EDI | 151 |
| `distributor_beta_tracing_2026-03.csv` | Distributor B, monthly upload | 63 |
| `distributor_gamma_tracing_2026-04-01.csv` | Distributor C, April | 27 |
| `legacy_match_decisions.csv` | The client's data integrity team | 214 |

**Two files are sealed** in `_sealed/` and you should not open them until Part D:
`GROUND_TRUTH.csv` and `SCENARIO_CATALOGUE.csv`, plus the generator that
produced everything. They are artefacts of how the data was made. **No such
thing exists on a real project** — if it did, there'd be no project.

---

## How the business works

Read this first; the file structure only makes sense once you have it.

The client **manufactures medical devices**. They mostly don't sell to hospitals
directly. They sell in bulk to **distributors**, who warehouse the product and
resell it to hospitals and clinics.

This creates the problem the whole POC exists to solve:

> **The manufacturer cannot see who their end customers are.**

They know they sold 5,000 units to Distributor Alpha. They don't know that 40 of
them went to Saint Joseph Hospital in Portland — unless Alpha tells them.

Alpha does tell them, in a **tracing file** (it "traces" the sale back to the end
customer). But that file contains only a shipping name and address, typed by
whoever picked the order. No customer number. Nothing that joins.

Why it matters commercially — four separate reasons, each worth money:

1. **Contract pricing.** Saint Joseph negotiated a discount. The manufacturer
   pays the distributor the difference (a **chargeback**). If you can't identify
   the hospital, you can't validate the claim.
2. **Rebates.** Purchasing organisations earn rebates on member volume. You need
   to know which members bought what.
3. **Sales commission.** A rep's territory is defined by customers. Unattributed
   sales pay nobody.
4. **Analytics.** "How are we doing in the Pacific Northwest?" is unanswerable
   if a third of your sales aren't attached to a customer.

Today a small team resolves these **by hand**, thousands per month, working down
a five-level match ladder.

---

## The files, one by one

### 1. `erp_customer_master.csv` — the system of record

```
erp_customer_id, customer_name, address_line_1, address_line_2,
address_line_3, city, state, postal_code, legacy_customer_id
```

The client's ERP. Old, probably IBM i / DB2 for i. Every customer they have ever
invoiced directly.

**What to expect from a system like this:** upper case throughout. Heavy
abbreviation, because fields are short — a name field capped at 30 characters
will simply cut off a long hospital name, and no cleaning gets those letters
back. Three address lines, because that's how shipping labels were laid out, and
the suite might be on line 2, line 3, or neither. Data keyed in over twenty
years by dozens of people, so the same hospital can appear twice.

**`legacy_customer_id` is the most important column in the entire dataset.** It's
the client's internal customer number — the thing every downstream system,
contract and rebate calculation already references. Your canonical IDs should
anchor on it wherever it exists, because that's what makes them stable and what
lets your output plug into everything they already have.

**Role:** `master`.

### 2. `salesforce_accounts.csv` — the commercial view

```
sf_account_id, account_name, billing_street, billing_suite,
billing_city, billing_state, billing_zip, npi_number
```

The CRM. Accounts the sales team manages — which is **not the same population**
as the ERP. It includes prospects who've never bought anything, and misses
customers that only ever came through a distributor.

**Characteristics:** title case, full words, generally cleaner than the ERP
because a human typed it recently. The suite has its own column, which is a
small gift. ZIP is sometimes ZIP+4.

**It carries `npi_number` — sometimes.** Roughly 70% populated. The NPI is the
strongest identifier in the whole dataset, and the fact it's missing on a third
of records is exactly why you can't build the pipeline around it.

**Role:** `crm`.

### 3. `provider_reference.csv` — licensed third-party data

```
npi, organization_name, address_line, city, state, zip5, zip4,
idn_id, idn_name, health_system_id, health_system_name
```

Bought from a healthcare data vendor. Think Definitive Healthcare or IQVIA. This
is external truth about US healthcare organisations — who exists, where, and
**who owns whom**.

**Two distinct jobs, and it's easy to notice only the first:**

1. **It's a matching source.** It participates in matching like any other
   source. That's how a customer acquires an NPI it never had in the ERP.
2. **It's the only source that knows the hierarchy.** `idn_id` and
   `health_system_id` exist nowhere else. Without this file you have customers
   but no structure.

The NPI is the join key that makes both work.

**Watch out:** the vendor's coverage is not complete. Two real customers in this
dataset are absent from it. They must survive your pipeline with no hierarchy
attached — not crash it, not vanish.

**Role:** `reference`.

### 4. `gpo_roster.csv` — purchasing group membership

```
gpo_id, gpo_name, npi, member_since
```

A **GPO** (Group Purchasing Organization) is how US hospitals negotiate
collectively — hundreds of facilities band together for better pricing. Vizient,
Premier, HealthTrust are the real ones.

Joined to customers by **NPI**.

**The modelling trap, and it's the most common one in this domain:** a GPO is
**not** a level of the hierarchy. A hospital belongs to a health system *and*
separately to a purchasing organisation, and the two have nothing to do with
each other. Some facilities belong to two GPOs at once. Model membership as its
own table of edges — the moment you make it a tree level, the two-GPO case
breaks it.

**Role:** hierarchy input. Never enters matching.

### 5–7. The tracing files — where the money is

**`distributor_alpha_tracing_2026-03.csv`** — daily EDI drop, March

```
trace_id, invoice_date, ship_to_name, ship_to_address, ship_to_city,
ship_to_state, ship_to_zip, product_code, quantity, net_sales_amount
```

The highest volume and the dirtiest. EDI is an old B2B format; files arrive
daily, generated by the distributor's warehouse system from whatever the picker
typed. Expect abbreviation, OCR-style damage, suites smuggled into the name
field, typos.

**`distributor_beta_tracing_2026-03.csv`** — monthly manual upload, March

```
RecordID, SaleDate, CustomerName, Street, CityStateZip, Item, Qty, Amount
```

**Completely different column names for the same concepts.** City, state and ZIP
are jammed into one column. Dates are US format, not ISO. Somebody at Beta
assembles this in Excel once a month.

This file exists to make one point: **onboarding a new distributor must be a
config change, not a code change.** If adding Beta means editing Python, your
mapping model is wrong. There are dozens of distributors in reality.

**`distributor_gamma_tracing_2026-04-01.csv`** — April

A later file, for the incremental exercise. Mostly customers you've already
resolved, plus a couple that are genuinely new.

**Role:** `tracing`. These are the only files carrying sales figures, and the
only ones the business is actually trying to resolve.

### 8. `legacy_match_decisions.csv` — the human baseline

```
decision_id, source_system, source_record_id, legacy_customer_id,
match_level, decided_by, decided_on
```

**The most interesting file in the set.** What the client's data integrity team
decided, by hand, for March. For every tracing record: the customer they
assigned it to, or `UNMATCHED`.

`match_level` records which rung of their ladder caught it:

| Level | Meaning |
|---|---|
| `L1_EXACT_NAME_ADDRESS` | Name and address matched exactly |
| `L2_EXACT_NAME_ZIP` | Name and ZIP matched |
| `L3_FUZZY` | A human judged it similar enough |
| `L4_ADDRESS_ONLY` | Address matched, name didn't |
| `L5_LOOSE_ADDRESS` | A human worked it out from partial information |
| `UNMATCHED` | They gave up |

`decided_by` is `system` for the top rungs and a person's name lower down —
which tells you exactly where the manual effort is concentrated. That
distribution is itself a finding worth putting in the readout.

**This file does three jobs:**

1. **Evaluation baseline.** Your precision and recall are measured against it.
2. **Training data.** The "seeded" run re-estimates your m probabilities from
   these decisions. That's what teaches the model how *this* client's data
   behaves.
3. **Business evidence.** It quantifies how much human effort the current
   process costs.

**And it is not perfect.** People gave up on records that were resolvable, and
occasionally assigned the wrong customer. A Friday afternoon looks different
from a Tuesday morning.

That means your metrics have a **noise floor**: some of your "errors" are the
baseline being wrong, not you. Sampling disagreements by hand is not optional
extra rigour — it's the only way to tell the two apart. On the real project
you'd take fifty disagreements to the client and ask them to adjudicate.

**Role:** ground truth and training data. Never a matching source.

---

## How they connect

```
                    THE JOIN KEYS

   legacy_customer_id          npi                  (nothing)
          │                     │                       │
   ┌──────┴──────┐      ┌───────┴────────┐      ┌──────┴───────────┐
   │     ERP     │      │   Salesforce   │      │  TRACING FILES   │
   │  (master)   │      │     (crm)      │      │    alpha/beta    │
   └──────┬──────┘      └───────┬────────┘      │     gamma        │
          │                     │               └──────┬───────────┘
          │                     │                      │
          │              ┌──────┴──────┐               │
          │              │  PROVIDER   │               │
          │              │  REFERENCE  │               │
          │              └──┬───────┬──┘               │
          │                 │       │                  │
          │             npi │       │ idn / health     │
          │                 │       │ system ids       │
          │          ┌──────┴───┐   │                  │
          │          │   GPO    │   │                  │
          │          │  ROSTER  │   │                  │
          │          └──────────┘   │                  │
          │                         │                  │
          └─────────────────────────┴──────────────────┘
                                 │
                        YOUR MATCHER
                    (name + address similarity)
                                 │
                                 ▼
                      CANONICAL CUSTOMER
                                 ▲
                                 │
                    LEGACY MATCH DECISIONS
                   (the humans' answer, for March)
```

The thing to internalise:

- **ERP ↔ Salesforce ↔ Reference** can partly join on **NPI**, where it exists
- **GPO roster** joins to reference on **NPI**
- **Hierarchy** comes only from **reference**, via `idn_id` / `health_system_id`
- **Tracing files join to nothing.** No key, no ID, nothing. They carry a typed
  name and address and that is all

**That last line is the entire project.** Everything else is scaffolding around
the problem of attaching a typed string to a real customer.

---

## What a handover actually looks like

Worth knowing, because you'll get one:

You will **not** get a document listing the data quality issues. You'll get the
files, a couple of calls with someone who knows the ERP, and access to whoever
does the manual matching today — and that person is the single most valuable
source of information on the project. They know that Alpha always drops the
suite, that Beta's ZIP is unreliable, and that the Portland and Orlando Saint
Marys are constantly confused. None of that is written down anywhere.

So budget your first day for **profiling**, not building. Load every file, count
nulls, look at distinct values, sort by length to find truncation, and write
down what you find. That list is your real spec, and you'll keep adding to it
for weeks.

Which is exactly why task A.0 in the build plan exists.
