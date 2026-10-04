import networkx as nx
import pandas as pd


# =============================================================================
# cluster — turn PAIRS into CUSTOMERS
#
# A pair only says "these two records belong together".
# A customer is a GROUP of records. So we follow the links:
#
#   pairs:   A-B    B-C    D-E          (F has no pairs)
#
#   A is linked to B, B is linked to C   ->  A, B, C  = customer 1
#   D is linked to E                     ->  D, E     = customer 2
#   F is linked to nothing               ->  F        = customer 3
#
# A and C were never compared directly — they end up together because
# both are linked to B.
#
# HOW: think of every record as a DOT and every pair as a LINE between two
# dots. Each separate island of connected dots is one customer.
# networkx is a library made for exactly this ("graphs" of dots and lines).
#
#   step 1   empty graph
#   step 2   every record becomes a dot     <- this keeps lonely records like F
#   step 3   every pair becomes a line
#   step 4   find the islands, give each one a number
# =============================================================================

def cluster(records: pd.DataFrame, pairs: pd.DataFrame):
    g = nx.Graph()                                                      # 1

    g.add_nodes_from(records["record_uid"])                             # 2

    g.add_edges_from(zip(pairs["record_uid_l"], pairs["record_uid_r"]))  # 3

    rows = []
    for number, island in enumerate(nx.connected_components(g), start=1):   # 4
        for uid in island:
            rows.append((uid, number))

    return pd.DataFrame(rows, columns=["record_uid", "cluster_id"])


# =============================================================================
# show_clusters — put the cluster number next to every record, so you can
# READ the customers instead of looking at IDs
#
#   cluster_id  source_system      name_raw                  street_std
#   1           erp                ST JOSEPH HOSP            1240 MAIN STREET
#   1           sf                 Saint Joseph Hospital     1240 MAIN STREET
#   1           distributor_alpha  ST JOSEPHS HOSPITAL       1240 MAIN STREET
#   2           ...
# =============================================================================

def show_clusters(records: pd.DataFrame, clusters: pd.DataFrame):
    view = records.merge(clusters, on="record_uid")                     # add cluster_id to each record
    view = view.sort_values(["cluster_id", "source_system"])            # records of one customer together
    return view[["cluster_id", "source_system", "name_raw", "street_std", "zip5", "legacy_customer_id"]]
