with date_cutoff as(
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
having count (*) >= 30
order by median_price_per_sqft desc; 