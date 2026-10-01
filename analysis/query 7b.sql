with sales_citywide as (
	select
		property_type,
		count(*) as total_sales_count,
		ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqft)::NUMERIC, 2) AS citywide_median_price_sqft,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY actual_worth_aed)::NUMERIC, 2) AS citywide_median_sales_price
    FROM sales
	where is_off_plan= 0
		and transaction_date >= (select max(transaction_date) - interval '1 year' from sales)
	group by property_type
),
rent_citywide as (
	select
		property_type,
		count(*) total_rent_count,
		ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rent_per_sqft)::NUMERIC, 2) AS citywide_median_rent_sqft,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_rent_aed)::NUMERIC, 2) AS citywide_median_annual_rent
    FROM rent_clean
	where contract_date >= (select max(contract_date) - interval '1 year' from rent_clean)
	group by property_type
)
select
	s.property_type,
    s.total_sales_count,
    r.total_rent_count,
    s.citywide_median_price_sqft,
    r.citywide_median_rent_sqft,
    s.citywide_median_sales_price,
    r.citywide_median_annual_rent,
	round((r.citywide_median_rent_sqft / s.citywide_median_price_sqft) * 100, 2) as citywide_gross_yield_pct
from sales_citywide s
inner join rent_citywide r
	on s.property_type= r.property_type
order by s.property_type;