import os
import pandas as pd

# Raw file paths
sales_path = r"C:\Users\LENOVO\Documents\Project\dubai rental\sales\merge\merged.csv"
rent_path = r"C:\Users\LENOVO\Documents\Project\dubai rental\rent\merge\merged.csv"

def inspect_area_ids(file_path: str, dataset_name: str):
    print(f"\n{'='*25} {dataset_name} {'='*25}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Load only area_id and area_name_en, dropping duplicates immediately to save memory
    df = pd.read_csv(file_path, usecols=['area_id', 'area_name_en'], low_memory=False)
    unique_pairs = df.dropna().drop_duplicates()

    # 1. Al Barsha / Al Barshaa South variants
    barsha = unique_pairs[
        unique_pairs['area_name_en'].str.contains(r'Barsha.*South', case=False, regex=True)
    ].sort_values(by=['area_name_en', 'area_id'])
    
    print("\n--- Al Barsha South / Al Barshaa South Variants ---")
    if not barsha.empty:
        print(barsha.to_string(index=False))
    else:
        print("None found.")

    # 2. Al Thanayah / Al Thanyah variants
    thanayah = unique_pairs[
        unique_pairs['area_name_en'].str.contains(r'Than[a-z]*yah', case=False, regex=True)
    ].sort_values(by=['area_name_en', 'area_id'])
    
    print("\n--- Al Thanyah / Al Thanayah Variants ---")
    if not thanayah.empty:
        print(thanayah.to_string(index=False))
    else:
        print("None found.")

inspect_area_ids(sales_path, "RAW SALES TRANSACTIONS")
inspect_area_ids(rent_path, "RAW EJARI RENT CONTRACTS")