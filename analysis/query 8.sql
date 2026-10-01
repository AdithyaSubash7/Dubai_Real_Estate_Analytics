-- 1. vw_price_by_area (pricing benchmarks)--

create or replace view vw_price_by_area as
with date_cutoff as (
	select max(transaction_date) - interval '1 year' as min_date
	from sales
)
select
	s.area_id,
    s.area_name,
    s.property_type,
	count(*) as transaction_count,
	round(percentile_cont(0.5) within group (order by s.price_per_sqft)::numeric, 2) as median_price_per_sqft
from sales s
cross join date_cutoff d
where s.transaction_date >= d.min_date
group by s.area_id, s.area_name, s.property_type
having count(*) >= 30;

-- 2. vw_price_trend_citywide (citywide & property type history)--

create or replace view vw_price_trend_citywide as
with quarterly_raw as (
	select
		extract(year from transaction_date)::int as market_year,
		extract(quarter from transaction_date)::int as market_quarter,
		property_type as segment,
		count(*) as transaction_count,
		round(percentile_cont(0.5) within group (order by price_per_sqft)::numeric, 2) as median_price_per_sqft
	from sales
	group by 1, 2, 3

	union all

	select 
		extract(year from transaction_date)::int as market_year,
		extract(quarter from transaction_date)::int as market_quarter,
		'citywide (all)' as segment,
		count(*) as transaction_count,
		round(percentile_cont(0.5) within group (order by price_per_sqft)::numeric, 2) as median_price_per_sqft
	from sales
	group by 1, 2
)
select
	market_year,
	market_quarter,
    market_year || '-Q' || market_quarter AS quarter_label,
    segment,
    transaction_count,
    median_price_per_sqft,
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 1) over w)
		/ nullif(lag(median_price_per_sqft, 1) over w, 0),
		2
	) as qoq_pct_change,
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 4) over w)
		/ nullif(lag(median_price_per_sqft, 4) over w, 0),
		2
	) as yoy_pct_change
from quarterly_raw
window w as (
	partition by segment
	order by market_year asc, market_quarter asc
);

-- 3. vw_price_trend_by_area (top 15 areas split by property type)

create or replace view vw_price_trend_by_area as
with top_15_areas as (
	select
		area_id,
		area_name,
		count(*) as total_historical_sales
	from sales
	group by 1, 2
	order by total_historical_sales desc
	limit 15
),
quarterly_area_data as (
	select
		s.area_id,
		t.area_name,
		s.property_type,
		extract(year from s.transaction_date):: int as market_year,
		extract(quarter from s.transaction_date)::int as market_quarter,
		count(*) as transaction_count,
		round(percentile_cont(0.5) within group (order by s.price_per_sqft)::numeric, 2) as median_price_per_sqft
	from sales s
	inner join top_15_areas t
		on s.area_id= t.area_id
	group by 1, 2, 3, 4, 5
)
select
	area_id,
    area_name,
    property_type,
    market_year,
    market_quarter,
    market_year || '-Q' || market_quarter AS quarter_label,
    transaction_count,
    median_price_per_sqft,
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 1) over w)
		/ nullif(lag(median_price_per_sqft, 1) over w, 0),
		2
	) as qoq_pct_change,
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 4) over w)
		/ nullif(lag(median_price_per_sqft, 4) over w, 0),
		2
	) as yoy_pct_change
from quarterly_area_data
window w as (
	partition by area_id, property_type
	order by market_year asc, market_quarter asc
);

-- 4. vw_rental_yield (full matched segments within confidence flags)--

create or replace view vw_rental_yield as
with sales_count as (
	select
		area_id,
        area_name,
        property_type,
        bedrooms,
		count(*) as sales_count,
		ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqft)::NUMERIC, 2) AS median_price_per_sqft,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY actual_worth_aed)::NUMERIC, 2) AS median_sales_price_aed
		from sales
		where is_off_plan= 0
			and transaction_date >= (select max(transaction_date) - interval '1 year' from sales)
		group by area_id, area_name, property_type, bedrooms
		having count(*) >= 30
),
rent_count as(
	select
		area_id,
        property_type,
        bedrooms,
        COUNT(*) AS rent_count,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rent_per_sqft)::NUMERIC, 2) AS median_rent_per_sqft,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_rent_aed)::NUMERIC, 2) AS median_annual_rent_aed
	from rent_clean
	where contract_date >= (select max(contract_date) - interval '1 year' from rent_clean)
	group by area_id, property_type, bedrooms
	having count(*) >= 30
)
select
	s.area_id,
    s.area_name,
    s.property_type,
    s.bedrooms,
    s.sales_count,
    r.rent_count,
    s.median_price_per_sqft,
    r.median_rent_per_sqft,
    s.median_sales_price_aed,
    r.median_annual_rent_aed,
	round((r.median_rent_per_sqft / s.median_price_per_sqft) * 100, 2) as gross_rental_yield_pct,
	case
		when s.sales_count < 100 or r.rent_count < 100 then 'low_confidence'
		else 'high_confidence'
	end as confidence_level
from sales_count s
inner join rent_count r
	on s.area_id = r.area_id
	and s.property_type= r.property_type
	and s.bedrooms= r.bedrooms;

-- 5. vw_yield_ranking (top 15 & bottom 15 outliers)--

create or replace view vw_yield_ranking as
with ranked_segments as (
	select
		*,
		row_number() over (order by gross_rental_yield_pct desc) as rank_top,
		row_number() over (order by gross_rental_yield_pct asc) as rank_bottom
	from vw_rental_yield
)
select 
	case
		when rank_top <= 15 then 'top 15'
		else 'bottom 15'
	end as ranking_group,
	case
		when rank_top <= 15 then rank_top
		else rank_bottom
	end as group_rank,
	area_id,
    area_name,
    property_type,
    bedrooms,
    sales_count,
    rent_count,
    median_price_per_sqft,
    median_rent_per_sqft,
    gross_rental_yield_pct,
    confidence_level
	from ranked_segments
	where rank_top <= 15 or rank_bottom <= 15;

-- 6. vw_yield_citywide (citywide property type rollup)--

create or replace view vw_yield_citywide as
with sales_citywide as (
	select
		property_type,
		count(*) as total_sales_count,
		ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqft)::NUMERIC, 2) AS citywide_median_price_sqft,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY actual_worth_aed)::NUMERIC, 2) AS citywide_median_sales_price
    FROM sales
	where is_off_plan = 0
		and transaction_date >= (select max(transaction_date) - interval '1 year' from sales)
	group by property_type
),
rent_citywide as (
	select
	property_type,
	count(*) as total_rent_count,
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
	on s.property_type= r.property_type;