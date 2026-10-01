with sales_cohort as (
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
rent_cohort as (
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
	having count (*) >= 30
),
yield_calculated as (
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
			else 'high-confidence'
		end as confidence_level
	from sales_cohort s
	inner join rent_cohort r
		on s.area_id= r.area_id
		and s.property_type= r.property_type
		and s.bedrooms= r.bedrooms
),
ranked_segments as(
	select
		*,
		row_number() over (order by gross_rental_yield_pct desc) as rank_top,
		row_number() over (order by gross_rental_yield_pct asc) as rank_bottom
	from yield_calculated
)
select
	case
		when rank_top <= 15 then 'Top 15'
		else 'Bottom 15'
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
where rank_top <= 15 or rank_bottom <= 15
order by gross_rental_yield_pct desc;