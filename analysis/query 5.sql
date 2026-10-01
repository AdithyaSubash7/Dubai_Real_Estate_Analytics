with top_15_areas as(
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
		extract(year from s.transaction_date)::int as market_year,
		extract(quarter from s.transaction_date)::int as market_quarter,
		count(*) as transaction_count,
		round(percentile_cont(0.5) within group (order by s.price_per_sqft):: numeric, 2) as median_price_per_sqft
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
	market_year || '-Q' || market_quarter as quarter_label,
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
window w as(
		partition by area_id, property_type
		order by market_year asc, market_quarter asc
)
order by
	area_name,
	property_type,
	market_year asc,
	market_quarter asc;