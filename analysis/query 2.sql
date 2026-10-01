drop table if exists rent_clean cascade;

create table rent_clean as 
select r.*
from rent r 
join (
	select contract_id
	from rent
	group by contract_id
	having count(*)= 1
) single_contracts on r.contract_id= single_contracts.contract_id
where r.line_number= 1;

alter table rent_clean add primary key (contract_id, line_number);

CREATE INDEX idx_rent_clean_area_id ON rent_clean (area_id);
CREATE INDEX idx_rent_clean_date ON rent_clean (contract_date);
CREATE INDEX idx_rent_clean_bedrooms ON rent_clean (bedrooms);

select count(*) as rent_clean_row_count from rent_clean;


WITH sales_yearly AS (
    SELECT
        EXTRACT(YEAR FROM transaction_date)::INT AS market_year,
        COUNT(*) AS sales_count,
        MIN(transaction_date) AS min_sales_date,
        MAX(transaction_date) AS max_sales_date
    FROM sales
    GROUP BY 1
),
rent_yearly AS (
    SELECT
        EXTRACT(YEAR FROM contract_date)::INT AS market_year,
        COUNT(*) AS rent_count,
        MIN(contract_date) AS min_rent_date,
        MAX(contract_date) AS max_rent_date
    FROM rent_clean
    GROUP BY 1
)
SELECT
    COALESCE(s.market_year, r.market_year) AS market_year,
    s.sales_count,
    s.min_sales_date,
    s.max_sales_date,
    r.rent_count,
    r.min_rent_date,
    r.max_rent_date
FROM sales_yearly s
FULL OUTER JOIN rent_yearly r 
    ON s.market_year = r.market_year
ORDER BY market_year ASC;

