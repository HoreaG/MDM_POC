import pandas as pd
from mdm.standardize import standardize_name, standardize_street, extract_suite, standardize_zip, parse_city_state_zip
from pathlib import Path  


header_names = ["record_uid", "source_system", "source_record_id", "role", "name_raw", "name_std", "street_std", "suite_std", "zip5", "legacy_customer_id", "npi"]

mapping = {
    "erp": {
        "record_uid": "erp_customer_id",
        "source_system": "erp",
        "role": "master",
        "name_raw": "customer_name",
        "street_std": "address_line_1",
        "suite_std": ["address_line_1", "address_line_2", "address_line_3"],  
        "zip5": "postal_code",
        "legacy_customer_id": "legacy_customer_id",
        "npi": ""
    },
    "sf": {
        "record_uid": "sf_account_id",
        "source_system": "sf",
        "role": "crm",
        "name_raw": "account_name",
        "street_std": "billing_street",
        "suite_std": ["billing_street", "billing_suite"],                    
        "zip5": "billing_zip",
        "legacy_customer_id": "",
        "npi": "npi_number"
    },
    "reference": {                                                            
        "record_uid": "npi",
        "source_system": "reference",
        "role": "reference",
        "name_raw": "organization_name",
        "street_std": "address_line",
        "suite_std": ["address_line"],
        "zip5": "zip5",
        "legacy_customer_id": "",
        "npi": "npi"
    },
    "distributor": {                                                          
        "record_uid": "trace_id",
        "source_system": "distributor",
        "role": "tracing",
        "name_raw": "ship_to_name",
        "street_std": "ship_to_address",
        "suite_std": ["ship_to_address", "ship_to_name"],                     
        "zip5": "ship_to_zip",
        "legacy_customer_id": "",
        "npi": ""
    },
    "beta": {                                                                 
        "record_uid": "RecordID",
        "source_system": "beta",
        "role": "tracing",
        "name_raw": "CustomerName",
        "street_std": "Street",
        "suite_std": ["Street", "CustomerName"],
        "zip5": "",                                                           
        "city_state_zip": "CityStateZip",                                     
        "legacy_customer_id": "",
        "npi": ""
    }
}


def one_table(df: pd.DataFrame, name: str, mapping: dict):
    name_lower = name.lower()
    
    if "beta" in name_lower:
        system_key = "beta"
    elif "alpha" in name_lower or "gamma" in name_lower:
        system_key = "distributor"
    else:
        system_key = name

    if system_key not in mapping:
        raise ValueError(f"Unknown system '{name}'. Available: {list(mapping)}")
    system_branch = mapping[system_key]
    master_df = pd.DataFrame()

    master_df["record_uid"] = name + "::" + df[system_branch["record_uid"]]
    master_df["source_system"] = name
    master_df["role"] = system_branch["role"]
    master_df["source_record_id"] = df[system_branch["record_uid"]]
    master_df["name_raw"] = df[system_branch["name_raw"]]
    master_df["name_std"] = df[system_branch["name_raw"]].apply(standardize_name)
    master_df["street_std"] = df[system_branch["street_std"]].apply(standardize_street)
    master_df["suite_std"] = df[system_branch["suite_std"]].apply(lambda row: extract_suite(*row), axis=1)
    if system_branch["zip5"] != "":                                          
        master_df["zip5"] = df[system_branch["zip5"]].apply(lambda z: standardize_zip(z)[0])
    else:                                                                     
        master_df["zip5"] = df[system_branch["city_state_zip"]].apply(lambda v: parse_city_state_zip(v)[2])

    if system_branch["legacy_customer_id"] != "":                             
        master_df["legacy_customer_id"] = df[system_branch["legacy_customer_id"]]

    if system_branch["npi"] != "":                                            
        master_df["npi"] = df[system_branch["npi"]]

    master_df = master_df.reindex(columns=header_names)                       
    master_df = master_df.fillna("")                                          

    return master_df


files = [
    ("erp",               "erp_customer_master"),
    ("sf",                "salesforce_accounts"),
    ("reference",         "provider_reference"),
    ("distributor_alpha", "distributor_alpha_tracing_2026-03"),
    ("distributor_beta",  "distributor_beta_tracing_2026-03"),
]


# NEW — load every file, conform it, and stack them into one table
def build_records(folder):
    tables = []
    for name, file in files:
        df = pd.read_csv(Path(folder) / f"{file}.csv", dtype=str)
        tables.append(one_table(df, name, mapping))

    return pd.concat(tables, ignore_index=True)