import os
import gc
import pandas as pd
import numpy as np

sales_path = r"C:\Users\LENOVO\Documents\Project\dubai rental\sales\merge\merged.csv"
rent_path = r"C:\Users\LENOVO\Documents\Project\dubai rental\rent\merge\merged.csv"

output_dir = r"C:\Users\LENOVO\Documents\Project\dubai rental\cleaned"
os.makedirs(output_dir, exist_ok=True)

cleaned_sales_path = os.path.join(output_dir, "sales_cleaned.csv")
cleaned_rent_path = os.path.join(output_dir, "rent_cleaned.csv")

SQM_TO_SQFT = 10.7639
START_DATE = "2015-01-01"
END_DATE = "2026-09-27"

MIN_AREA_SQM = 15.0
MAX_AREA_SQM = 2000.0

def log_step(step_name: str, df_before: pd.DataFrame, df_after: pd.DataFrame, reason: str):
    """Logs row count changes between cleaning steps."""
    before_count = len(df_before)
    after_count = len(df_after)
    removed_count = before_count - after_count
    pct_removed = (removed_count / before_count) * 100 if before_count > 0 else 0.0
    
    print(f"[{step_name}]")
    print(f"  Rows Before : {before_count:,}")
    print(f"  Rows After  : {after_count:,}")
    print(f"  Removed     : {removed_count:,} ({pct_removed:.2f}%)")
    print(f"  Reason      : {reason}\n")


def standardize_area_names(series: pd.Series) -> pd.Series:
    """Standardizes casing and preserves recognized Dubai acronyms."""
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(r'\s+', ' ', regex=True)
        .str.title()
    )
    acronym_replacements = {
        r'\bJvc\b': 'JVC',
        r'\bJbr\b': 'JBR',
        r'\bJlt\b': 'JLT',
        r'\bDifc\b': 'DIFC',
        r'\bMbr\b': 'MBR',
        r'\bDso\b': 'DSO',
        r'\bDic\b': 'DIC',
        r'\bDmc\b': 'DMC',
        r'\bTecom\b': 'TECOM',
        r'\bUtc\b': 'UTC',
        r'\bCbd\b': 'CBD'
    }
    for pattern, replacement in acronym_replacements.items():
        cleaned = cleaned.str.replace(pattern, replacement, regex=True)
    return cleaned

#sales

print("\n" + "=" * 35 + " CLEANING SALES TRANSACTIONS " + "=" * 35 + "\n")

sales_cols = [
    'transaction_id', 'instance_date', 'area_id', 'area_name_en',
    'actual_worth', 'procedure_area', 'meter_sale_price',
    'trans_group_en', 'property_usage_en', 'property_type_en',
    'rooms_en', 'reg_type_en'
]

print("Loading raw sales data...")
df_sales = pd.read_csv(sales_path, usecols=sales_cols, low_memory=False)
initial_sales_rows = len(df_sales)
print(f"Raw Sales Rows Loaded: {initial_sales_rows:,}\n")

step_df = df_sales[df_sales['trans_group_en'] == 'Sales'].copy()
log_step("Sales 1: Transaction type", df_sales, step_df, "Drop mortgages and gifts (keep only trans_group_en == 'Sales')")
df_sales = step_df

step_df = df_sales[df_sales['property_usage_en'] == 'Residential'].copy()
log_step("Sales 2: Property usage", df_sales, step_df, "Drop Commercial, Industrial, Hospitality, and 'أخرى'")
df_sales = step_df

sales_type_map = {'Unit': 'Apartment', 'Villa': 'Villa'}
step_df = df_sales[df_sales['property_type_en'].astype(str).str.strip().isin(['Unit', 'Villa'])].copy()
step_df['property_type'] = step_df['property_type_en'].astype(str).str.strip().map(sales_type_map)
log_step("Sales 3: Property type", df_sales, step_df, "Drop Land and Building blocks (keep Unit -> Apartment, Villa -> Villa)")
df_sales = step_df

sales_bedroom_map = {
    'Studio': 0,
    '1 B/R': 1,
    '2 B/R': 2,
    '3 B/R': 3,
    '4 B/R': 4,
    '5 B/R': 5,
    '6 B/R': 6,
    '7 B/R': 7
}
step_df = df_sales[df_sales['rooms_en'].isin(sales_bedroom_map.keys())].copy()
step_df['bedrooms'] = step_df['rooms_en'].map(sales_bedroom_map).astype(int)
log_step("Sales 4: Bedroom Extraction", df_sales, step_df, "Drop non-residential rooms; map Studio to 0, 1-7 B/R to integers")
df_sales = step_df

df_sales['transaction_date'] = pd.to_datetime(df_sales['instance_date'], errors='coerce')
step_df = df_sales[
    (df_sales['transaction_date'] >= START_DATE) & 
    (df_sales['transaction_date'] <= END_DATE)
].copy()
log_step("Sales 5: Date range", df_sales, step_df, f"Drop corrupted dates and filter strictly within {START_DATE} to {END_DATE}")
df_sales = step_df

step_df = df_sales[
    (df_sales['actual_worth'] >= 100_000) &
    (df_sales['procedure_area'] >= MIN_AREA_SQM) &
    (df_sales['procedure_area'] <= MAX_AREA_SQM) &
    df_sales['area_name_en'].notna() &
    df_sales['area_id'].notna()
].copy()
log_step("Sales 6: Area & Value bounds", df_sales, step_df, f"Drop price < 100k AED, area < {MIN_AREA_SQM} m² or > {MAX_AREA_SQM} m², and null areas/IDs")
df_sales = step_df

df_sales['area_id'] = df_sales['area_id'].astype('int64')
df_sales['area_name'] = standardize_area_names(df_sales['area_name_en'])
df_sales['area_sqm'] = df_sales['procedure_area'].round(2)
df_sales['area_sqft'] = (df_sales['procedure_area'] * SQM_TO_SQFT).round(2)
df_sales['actual_worth_aed'] = df_sales['actual_worth'].round(2)
df_sales['price_per_sqft'] = (df_sales['actual_worth_aed'] / df_sales['area_sqft']).round(2)
df_sales['is_off_plan'] = (df_sales['reg_type_en'].astype(str).str.strip() == 'Off-Plan Properties').astype(int)
df_sales['reg_type'] = df_sales['reg_type_en'].astype(str).str.strip()

q_low_sales = df_sales['price_per_sqft'].quantile(0.005)
q_high_sales = df_sales['price_per_sqft'].quantile(0.995)
step_df = df_sales[
    (df_sales['price_per_sqft'] >= q_low_sales) & 
    (df_sales['price_per_sqft'] <= q_high_sales)
].copy()
log_step(
    "Sales 7: Price/SqFt outliers", 
    df_sales, 
    step_df, 
    f"Drop derived price_per_sqft outside 0.5th ({q_low_sales:.2f} AED) and 99.5th ({q_high_sales:.2f} AED) percentiles"
)
df_sales = step_df

final_sales_cols = [
    'transaction_id', 'transaction_date', 'area_id', 'area_name',
    'property_type', 'bedrooms', 'is_off_plan', 'reg_type',
    'area_sqm', 'area_sqft', 'actual_worth_aed', 'price_per_sqft'
]
df_sales_final = df_sales[final_sales_cols].copy()

print(f"Sales cleaning complete. Final rows: {len(df_sales_final):,} (Retained {(len(df_sales_final)/initial_sales_rows)*100:.2f}% of raw rows)")
print(f"Saving cleaned sales to {cleaned_sales_path}...")
df_sales_final.to_csv(cleaned_sales_path, index=False)
print("Sales CSV saved successfully.\n")

del df_sales, df_sales_final, step_df
gc.collect()

#rent

print("\n" + "=" * 35 + " CLEANING EJARI RENT CONTRACTS " + "=" * 35 + "\n")

rent_cols = [
    'contract_id', 'line_number', 'contract_start_date', 'area_id', 'area_name_en',
    'actual_area', 'annual_amount', 'contract_reg_type_en',
    'property_usage_en', 'ejari_property_type_en', 'ejari_property_sub_type_en'
]

print("Loading raw rent data (10.5M rows)...")
df_rent = pd.read_csv(rent_path, usecols=rent_cols, low_memory=False)
initial_rent_rows = len(df_rent)
print(f"Raw Rent Rows Loaded: {initial_rent_rows:,}\n")

step_df = df_rent[df_rent['property_usage_en'] == 'Residential'].copy()
log_step("Rent 1: Property usage", df_rent, step_df, "Drop Commercial, Industrial, Labor camps, Multi Usage")
df_rent = step_df

rent_type_map = {
    'Flat': 'Apartment',
    'Villa': 'Villa',
    'Studio': 'Apartment',
    'Complex Villas': 'Villa'
}
step_df = df_rent[df_rent['ejari_property_type_en'].isin(rent_type_map.keys())].copy()
step_df['property_type'] = step_df['ejari_property_type_en'].map(rent_type_map)
log_step("Rent 2: Property type", df_rent, step_df, "Keep Flat/Studio -> Apartment, Villa/Complex Villa -> Villa")
df_rent = step_df

rent_bedroom_map = {
    'Studio': 0,
    '1bed room+Hall': 1,
    '2 bed rooms+hall': 2,
    '3 bed rooms+hall': 3,
    '4 bed rooms+hall': 4,
    '5 bed rooms+hall': 5,
    '6 bed rooms+hall': 6
}
step_df = df_rent[df_rent['ejari_property_sub_type_en'].isin(rent_bedroom_map.keys())].copy()
step_df['bedrooms'] = step_df['ejari_property_sub_type_en'].map(rent_bedroom_map).astype(int)
log_step("Rent 3: Bedroom Extraction", df_rent, step_df, "Normalize '1bed room+Hall', map Studio to 0, 1-6 B/R to integers")
df_rent = step_df

df_rent['contract_date'] = pd.to_datetime(df_rent['contract_start_date'], errors='coerce')
step_df = df_rent[
    (df_rent['contract_date'] >= START_DATE) & 
    (df_rent['contract_date'] <= END_DATE)
].copy()
log_step("Rent 4: Date range", df_rent, step_df, f"Drop corrupted dates and filter strictly within {START_DATE} to {END_DATE}")
df_rent = step_df

step_df = df_rent[
    (df_rent['annual_amount'] >= 10_000) &
    (df_rent['annual_amount'] <= 2_500_000) &
    (df_rent['actual_area'] >= MIN_AREA_SQM) &
    (df_rent['actual_area'] <= MAX_AREA_SQM) &
    df_rent['area_name_en'].notna() &
    df_rent['area_id'].notna()
].copy()
log_step("Rent 5: Area & Rent Bounds", df_rent, step_df, f"Drop rent < 10k or > 2.5M AED, area < {MIN_AREA_SQM} m² or > {MAX_AREA_SQM} m², and null areas/IDs")
df_rent = step_df

df_rent['area_id'] = df_rent['area_id'].astype('int64')
df_rent['area_name'] = standardize_area_names(df_rent['area_name_en'])
df_rent['area_sqm'] = df_rent['actual_area'].round(2)
df_rent['area_sqft'] = (df_rent['area_sqm'] * SQM_TO_SQFT).round(2)
df_rent['annual_rent_aed'] = df_rent['annual_amount'].round(2)
df_rent['rent_per_sqft'] = (df_rent['annual_rent_aed'] / df_rent['area_sqft']).round(2)
df_rent['contract_reg_type'] = df_rent['contract_reg_type_en'].str.strip()

q_low_rent = df_rent['rent_per_sqft'].quantile(0.005)
q_high_rent = df_rent['rent_per_sqft'].quantile(0.995)
step_df = df_rent[
    (df_rent['rent_per_sqft'] >= q_low_rent) & 
    (df_rent['rent_per_sqft'] <= q_high_rent)
].copy()
log_step(
    "Rent 6: Rent/SqFt Outliers", 
    df_rent, 
    step_df, 
    f"Drop derived rent_per_sqft outside 0.5th ({q_low_rent:.2f} AED) and 99.5th ({q_high_rent:.2f} AED) percentiles"
)
df_rent = step_df

final_rent_cols = [
    'contract_id', 'line_number', 'contract_date', 'contract_reg_type',
    'area_id', 'area_name', 'property_type', 'bedrooms',
    'area_sqm', 'area_sqft', 'annual_rent_aed', 'rent_per_sqft'
]
df_rent_final = df_rent[final_rent_cols].copy()

print(f"Rent cleaning complete. Final rows: {len(df_rent_final):,} (Retained {(len(df_rent_final)/initial_rent_rows)*100:.2f}% of raw rows)")
print(f"Saving cleaned rent to {cleaned_rent_path}...")
df_rent_final.to_csv(cleaned_rent_path, index=False)
print("Rent CSV saved successfully.\n")


print("=" * 35 + " VERIFYING OUTPUT SCHEMAS " + "=" * 35)
print("Sales Columns:", df_sales_final.columns.tolist() if 'df_sales_final' in locals() else pd.read_csv(cleaned_sales_path, nrows=1).columns.tolist())
print("Rent Columns :", df_rent_final.columns.tolist() if 'df_rent_final' in locals() else pd.read_csv(cleaned_rent_path, nrows=1).columns.tolist())
print("\n" + "=" * 35 + " STAGE 2 RE-RUN COMPLETED " + "=" * 35)