# Customer MDM — proof of concept

Matches customer records across five systems that share no common ID, and
groups them into one record per real customer.

The problem: distributors report each sale with a typed name and address, but
no customer number. Today a team matches these by hand.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
pytest -v
```

Then open the notebooks in order.

## The pipeline

| Step | File | What it does |
|---|---|---|
| Profile | `notebooks/00_profiling.ipynb` | Find what's wrong with the data → `docs/DATA_ISSUES.md` |
| Standardise | `src/mdm/standardize.py` | Clean names, streets, suites, ZIPs |
| Conform | `src/mdm/conform.py` | Five file layouts → one table |
| Match | `src/mdm/deterministic.py` | Exact rules: same NPI, same legacy ID, same name + street + ZIP |
| Cluster | `src/mdm/cluster.py` | Pairs of matches → one group per customer |
| Score | `src/mdm/scoring.py` | Compare with the client's manual decisions |

## Results so far — March sample

| | |
|---|---|
| Records, five sources | 406 |
| Exact name matches ERP vs Salesforce | 0 raw → 51 after cleaning |
| Matched pairs | 831 |
| Customer groups | 123 |
| Precision vs manual decisions | 93.0% |
| Recall vs manual decisions | 65.8% |
| Tracing records resolved automatically | 65.0% |

## Not done yet

- Fuzzy (probabilistic) matching — to recover the records exact rules miss
- Golden record and survivorship
- Customer hierarchy
- Incremental files (the April file)
- Running on Databricks

## Documents

- `docs/DATA_ISSUES.md` — every data problem found, with examples
- `docs/DECISIONS.md` — modelling decisions and the evidence for them
- `data/sample/SOURCES.md` — what each source file is
