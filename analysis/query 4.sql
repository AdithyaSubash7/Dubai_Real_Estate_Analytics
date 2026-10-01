with quarterly_raw as(
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
		'Citywide (All)' as segment,
		count(*) as transaction_count,
		round(percentile_cont(0.5) within group (order by price_per_sqft)::numeric, 2) as median_price_per_sqft
	from sales
	group by 1, 2
)
select 
	market_year,
	market_quarter,
	market_year || '-Q' || market_quarter as quarter_label,
	segment,
	transaction_count,
	median_price_per_sqft,

	--quarter over quarter % change--
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 1) over w)
		/ nullif(lag(median_price_per_sqft, 1) over w, 0),
		2
	) as qoq_pct_change,
	--year over year % change--
	round(
		100.0 * (median_price_per_sqft - lag(median_price_per_sqft, 4) over w)
		/ nullif(lag(median_price_per_sqft, 4) over w, 0),
		2
	) as yoy_pct_change
	
from quarterly_raw
window w as (
	partition by segment
	order by market_year asc, market_quarter asc
)
order by
	segment,
	market_year asc,
	market_quarter asc;