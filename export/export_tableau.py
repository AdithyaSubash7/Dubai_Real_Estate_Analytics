import os
import pandas as pd
from sqlalchemy import create_engine

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "dubai_real_estate"
DB_USER = "postgres"
DB_PASSWORD = "7410"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

OUTPUT_DIR = r"C:\Users\LENOVO\Documents\Project\dubai rental\tableau_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

views= [
    "vw_price_by_area",
    "vw_price_trend_citywide",
    "vw_price_trend_by_area",
    "vw_rental_yield",
    "vw_yield_ranking",
    "vw_yield_citywide"
]

def main():
    print("\n" + "=" * 45 + " EXPORTING POSTGRESQL VIEWS TO CSV " + "=" * 45)
    engine= create_engine(DATABASE_URL)

    for view in views:
        csv_path= os.path.join(OUTPUT_DIR, f"{view}.csv")
        print(f"Exporting '{view}..")

        df= pd.read_sql_table(view, engine)
        df.to_csv(csv_path, index= False)
        print(f"-> Saved {len(df):,} rows to {os.path.basename(csv_path)}")

    engine.dispose()
    print("=" * 45 + "\nALL 6 VIEWS EXPORTED SUCCESSFULLY FOR TABLEAU!\n")

if __name__ == "__main__":
    main()