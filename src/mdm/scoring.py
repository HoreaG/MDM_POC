import pandas as pd


# =============================================================================
# score — compare OUR answer with the HUMAN answer, for every tracing record
#
# The client's team matched March's tracing records by hand.
# legacy_match_decisions.csv holds their answer: for each record, the
# customer number (legacy_customer_id) they picked — or empty if they gave up.
#
#   step 1   each cluster -> its customer number
#            (taken from the ERP record inside the cluster)
#   step 2   each tracing record -> our answer = its cluster's number
#   step 3   put our answer next to the human answer
#   step 4   label each record
#
#     ours     human    label
#     L-0001   L-0001   CORRECT       we matched it, and agree
#     L-0001   L-0002   WRONG         we matched it to the wrong customer
#     L-0001   (empty)  EXTRA         we matched, the human didn't
#     (empty)  L-0001   MISSED        the human matched, we didn't
#     (empty)  (empty)  BOTH_EMPTY    nobody could match it
# =============================================================================

def score(records: pd.DataFrame, clusters: pd.DataFrame, decisions: pd.DataFrame):
    df = records.merge(clusters, on="record_uid")

    # 1. cluster -> customer number
    erp = df[df["legacy_customer_id"] != ""]
    cluster_number = erp.groupby("cluster_id")["legacy_customer_id"].first()

    # 2. our answer for each tracing record
    tracing = df[df["role"] == "tracing"].copy()
    tracing["ours"] = tracing["cluster_id"].map(cluster_number).fillna("")

    # 3. the human answer, side by side
    human = decisions[["source_system", "source_record_id", "legacy_customer_id"]].fillna("")
    human = human.rename(columns={"legacy_customer_id": "human"})
    result = tracing.merge(human, on=["source_system", "source_record_id"])

    # 4. label each record
    def label(row):
        if row["ours"] != "" and row["ours"] == row["human"]:
            return "CORRECT"
        if row["ours"] != "" and row["human"] != "":
            return "WRONG"
        if row["ours"] != "":
            return "EXTRA"
        if row["human"] != "":
            return "MISSED"
        return "BOTH_EMPTY"

    result["label"] = result.apply(label, axis=1)
    return result[["source_system", "source_record_id", "name_raw", "ours", "human", "label"]]


# =============================================================================
# summary — turn the labels into the three numbers that matter
#
#   PRECISION   of the matches we made, how many were right?
#               low = we merge customers that aren't the same. The EXPENSIVE error.
#   RECALL      of the matches the humans made, how many did we find too?
#               low = work still lands on a person. The SAFE error.
#   AUTOMATION  how many tracing records did we resolve without a person?
#
#   Never report precision without recall — matching nothing gives perfect precision.
# =============================================================================

def summary(result: pd.DataFrame):
    counts = result["label"].value_counts()
    correct = counts.get("CORRECT", 0)
    wrong = counts.get("WRONG", 0)
    extra = counts.get("EXTRA", 0)
    missed = counts.get("MISSED", 0)

    precision = correct / (correct + wrong + extra)
    recall = correct / (correct + wrong + missed)
    automation = (result["ours"] != "").mean()

    print(counts.to_string())
    print()
    print(f"precision   {precision:.1%}")
    print(f"recall      {recall:.1%}")
    print(f"automation  {automation:.1%}  of {len(result)} tracing records")