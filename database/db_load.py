import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

db_host= "localhost"
db_port= "5432"
db_name= "dubai_real_estate"
db_user= "postgres"
db_password= "YOUR_PASSWORD"

database_url= f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

cleaned_dir= r"C:\Users\LENOVO\Documents\Project\dubai rental\cleaned"
sales_csv_path= os.path.join(cleaned_dir, "sales_cleaned.csv")
rent_csv_path= os.path.join(cleaned_dir, "rent_cleaned.csv")

expected_sales_rows= 816_268
expected_rent_rows= 5_041_012

create_tables_sql= """
drop table if exists sales cascade;
drop table if exists rent cascade;

create table sales(
    transaction_id     text,
    transaction_date    date not null,
    area_id             integer not null,
    area_name           text not null,
    property_type       text not null,
    bedrooms            integer not null,
    is_off_plan         integer not null,
    reg_type            text not null,
    area_sqm            numeric(14, 2) not null,
    area_sqft           numeric(14, 2) not null,
    actual_worth_aed    numeric(14, 2) not null,
    price_per_sqft      numeric(14, 2) not null
    );

create table rent(
    contract_id         text,
    line_number         integer not null,
    contract_date       date not null,
    contract_reg_type   text not null,
    area_id             integer not null,
    area_name           text not null,
    property_type       text not null,
    bedrooms            integer not null,
    area_sqm            numeric(14, 2) not null,
    area_sqft           numeric(14, 2) not null,
    annual_rent_aed     numeric(14, 2) not null,
    rent_per_sqft       numeric(14, 2) not null        
);
"""
def bulk_copy_csv(raw_conn, file_path: str, table_name: str):
    filename= os.path.basename(file_path)
    print(f"Streaming '{filename}' into table '{table_name}' using native COPY...")
    start_time= time.time()

    with raw_conn.cursor() as cur:
        with open(file_path, "r", encoding= "utf-8") as f:
            copy_sql= f"""
                copy {table_name}
                from stdin
                with (format csv, header true, delimiter ',');
            """
            cur.copy_expert(sql=copy_sql, file= f)

    raw_conn.commit()
    elapsed= time.time() - start_time
    print(f"-> Successfully loaded '{table_name}' in {elapsed:.2f} seconds.")

def main():
    print("\n" + "=" * 40 + " STAGE 3: POSTGRESQL BULK LOAD " + "=" * 40 + "\n")

    for path in [sales_csv_path, rent_csv_path]:
        if not os.path.exists(path):
            print(f"[FILE ERROR] Could not find required CSV at:\n  {path}")
            print("Please ensure Stage 2 (cleaning) was executed and saved to this folder.")
            return

    print(f"Connecting to PostgreSQL database '{db_name}' on {db_host}:{db_port} as '{db_user}'...")
    try:
        engine= create_engine(database_url)

        with engine.connect() as test_conn:
            test_conn.execute(text("select 1;"))
        print("Database connection established successfully.\n")
    except OperationalError as err:
        err_msg= str(err)
        print("\n" + "!" * 50)
        print("[CONNECTION FAILED] Could not connect to PostgreSQL.")
        print(f"Error Message: {err_msg.strip()}")
        print("\nPlease check the following:")  
        if "password authentication failed" in err_msg:
            print("  -> WRONG PASSWORD: Make sure DB_PASSWORD matches what you set during installation.")
        elif "does not exist" in err_msg:
            print(f"  -> DATABASE MISSING: Verify you created database '{db_name}' in pgAdmin.")
        elif "Connection refused" in err_msg or "Is the server running" in err_msg:
            print("  -> SERVER STOPPED: Open PowerShell as Admin and run: Start-Service postgresql*")
        else:
            print("  -> Verify db_host, db_port, and db_user at the top of this script.")
        print("!" * 50 + "\n")
        return
    except Exception as general_err:
        print(f"[UNEXPECTED ERROR] {general_err}")
        return

    try:
        print("Creating initial table schemas (without indexes)...")
        with engine.connect() as conn:
            conn.execute(text(create_tables_sql))
            conn.commit()
        print("Tables 'sales' and 'rent' created successfully.\n")

        raw_connection= engine.raw_connection()
        try:
            bulk_copy_csv(raw_connection, sales_csv_path, "sales")
            bulk_copy_csv(raw_connection, rent_csv_path, "rent")
        finally:
            raw_connection.close()

        print("\n" + "=" * 30 + " POST-LOAD CONSTRAINTS & INDEXES " + "=" * 30)
        with engine.connect() as conn:

            print("Adding Primary Key on sales(transaction_id)...")
            conn.execute(text("alter table sales add primary key (transaction_id);"))
            conn.commit()
            print("  -> sales Primary Key added.")

            print("\nChecking for duplicate (contract_id, line_number) pairs in rent...")
            dup_check_sql= """
                select count(*)
                from (
                    select contract_id, line_number
                    from rent
                    group by contract_id, line_number
                    having count(*) > 1
                    ) as duplicate_pairs;
            """
            dup_pairs_count= conn.execute(text(dup_check_sql)).scalar()

            if dup_pairs_count== 0:
                print("-> 0 duplicate (contract_id, line_number) pairs found.")
                print("-> Applying composite Primary Key on rent(contract_id, line_number)...")
                conn.execute(text("alter table rent add primary key (contract_id, line_number);"))
                conn.commit()
                print("-> rent composite Primary Key added successfully.")
            else:
                print(f"-> WARNING: Found {dup_pairs_count:,} duplicate (contract_id, line_number) pairs!")
                print("-> SKIPPING Primary Key constraint on rent to prevent load failure.")

            print("\nBuilding B-Tree query indexes (area_id, date, bedrooms)...")
            index_start= time.time()

            conn.execute(text("create index idx_sales_area_id on sales (area_id);"))
            conn.execute(text("create index idx_sales_date on sales (transaction_date);"))
            conn.execute(text("create index idx_sales_bedrooms on sales (bedrooms);"))

            conn.execute(text("create index idx_rent_area_id on rent (area_id);"))
            conn.execute(text("create index idx_rent_date on rent (contract_date);"))
            conn.execute(text("create index idx_rent_bedrooms on rent (bedrooms);"))

            conn.commit()
            idx_elapsed= time.time() - index_start
            print(f"-> All 6 indexes built successfully in {idx_elapsed:.2f} seconds.")

        print("\n" + "=" * 30 + "ROW COUNT INTEGRITY VERIFICATION" + "=" * 30)
        with engine.connect() as conn:
            sales_db_count= conn.execute(text("select count(*) from sales;")).scalar()
            rent_db_count= conn.execute(text("select count(*) from rent;")).scalar()

        sales_delta= sales_db_count - expected_sales_rows
        rent_delta= rent_db_count - expected_rent_rows

        print(f"Sales DB Count : {sales_db_count:,} | Expected CSV : {expected_sales_rows:,} | Difference: {sales_delta:,}")
        print(f"Rent DB Count  : {rent_db_count:,} | Expected CSV : {expected_rent_rows:,} | Difference: {rent_delta:,}")

        if sales_db_count== expected_sales_rows and rent_db_count== expected_rent_rows:
            print("\n[VERIFICATION RESULT: PASSED]")
            print("100% of cleaned data was loaded into PostgreSQL without loss or truncation.")
        else:
            print("\n[VERIFICATION RESULT: WARNING]")
            print("Row counts do not match expected Stage 2 figures. Inspect the difference above.")
    except SQLAlchemyError as sql_err:
        print(f"\n[DATABASE EXECUTION ERROR] {sql_err}")
    finally:
        engine.dispose()

if __name__== "__main__":
    main()
