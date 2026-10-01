# Dubai Real Estate Market Analytics (2015–2026)

**Live dashboard:** https://public.tableau.com/app/profile/adithya.subash/viz/DubaiRealEstateMarketAnalytics2015-2026/MarketOverview

## Business question

Analysts at property firms, banks, and consultancies in the UAE are regularly asked two questions: *where are prices and rents moving, and where do rental yields make sense for investors?* This project builds an end-to-end pipeline — from raw government open data to a published dashboard — to answer both, using real Dubai Land Department (DLD) transaction and Ejari rental records rather than a pre-cleaned dataset.

## Data sources

- **Real Estate Transactions** (DLD): ~1.79M raw records of property sales, mortgages, and gifts, 47 columns, dating back to system inception through September 2026.
  Source: https://www.dubaipulse.gov.ae/data/dld-transactions/dld_transactions-open
- **Rent Contracts** (Ejari): ~10.5M raw rental contract records, 41 columns.
  Source: https://www.dubaipulse.gov.ae/data/dld-registration/dld_rent_contracts-open

Raw and cleaned CSV files are not included in this repository due to size (the raw files alone exceed several hundred MB to multiple GB). Download the source files from the links above and run `01_cleaning/code_2.py` to reproduce `sales_cleaned.csv` and `rent_cleaned.csv`.

Both are official government open data, downloaded as raw row-level records rather than a pre-cleaned dataset — all cleaning and validation shown below was done from scratch.

## Tech stack

Python (pandas) for ingestion and cleaning → PostgreSQL for warehousing and querying → SQL (CTEs, window functions, percentile aggregates) for analysis → Tableau Public for the dashboard.

## Cleaning pipeline and data-quality findings

Every cleaning step was logged with row counts before/after and a stated reason, rather than dropping rows silently. Full logs are in the project's cleaning scripts.

**Sales:** filtered to true sales (excluding mortgages and gifts), residential use only, Unit/Villa property types, valid bedroom counts, a 2015–2026 date window, and sane price/area bounds. **816,268 of 1,785,650 raw rows retained (45.7%).**

**Rent:** filtered to residential use, Apartment/Villa types, bedroom counts extracted from inconsistent sub-type text (e.g. "1bed room+Hall"), the same date window, and sane rent/area bounds. **5,041,012 of 10,511,392 raw rows retained (48.0%).**

### Key data-quality investigations

1. **Multi-line Ejari contracts inflate rent per sqft.** Contracts spanning multiple lines (~0.4% of contracts, 2.3% of rows) showed a median rent/sqft of AED 816 versus AED 60 for single-line contracts — a ~13x gap. Further testing showed 54.7%+ of these contracts repeat the same total rent across lines despite different unit areas, consistent with a whole-contract total being attached to every line rather than divided. These were excluded from all rent analysis (`rent_clean`, 4,905,709 rows) rather than left in or naively averaged.

2. **Apparent area-name spelling inconsistencies were verified, not assumed.** Areas like "Al Barsha South" vs "Al Barshaa South" and "Al Thanyah" vs "Al Thanayah" looked like typos on first inspection. Cross-checking against the raw `area_id` cadastral codes confirmed each spelling maps to a distinct, official DLD zone in *both* the sales and rent datasets independently — not a data-entry error. No merge was applied; the areas were kept separate.

3. **Sales includes off-plan properties**, which are not comparable to current rental income. Off-plan transactions were excluded from all rental yield calculations (kept for general price-trend analysis, flagged via an `is_off_plan` column).

4. **A scatter-plot outlier was checked against source data, not assumed to be an error.** Palm Jumeirah studios showed a median price of AED 3,822/sqft — far above the rest of the dataset. Verified against the underlying rows: a real, if thinly-sampled (71 sales), ultra-prime market segment, correctly flagged `low_confidence` rather than hidden.

## Methodology notes

- All price and rent figures use **medians** (`PERCENTILE_CONT`), not averages, to avoid distortion from outlier transactions.
- Rental yield = median annual rent/sqft ÷ median sale price/sqft × 100, computed at the (area, property type, bedroom count) level over the trailing 12 months, using only existing (non off-plan) sales and single-line rent contracts.
- Segments with fewer than 30 sales or 30 rental contracts are excluded entirely; segments with fewer than 100 on either side are flagged `low_confidence` in the dashboard rather than removed.
- Area matching between sales and rent uses `area_id` (DLD's cadastral code), not area name text, since it was verified to match exactly across both independently-collected datasets.

## Key findings

- Citywide median yield: **Apartments 5.36%**, **Villas 4.20%** — apartments outyield villas, consistent with villas being a lower-turnover, appreciation-focused asset class.
- Yields range from ~9.7% (Warsan Fourth studios) down to ~3.1% (Jumeirah First 2-bed apartments) — affordable, outer communities show the highest cash yield; prime central areas trade yield for capital preservation.
- Citywide apartment prices fell ~20% during the 2020 pandemic dip, then rose steadily from 2021 through 2024–2025.

## Dashboard

Three tabs, built in Tableau Public:
1. **Market Overview** — citywide KPIs, price trend, and price-by-area ranking.
2. **Historical Price Trends & Momentum** — quarterly price trend and YoY momentum for the top 15 areas by transaction volume, filterable by area and property type.
3. **Rental Yield & Risk-Return Matrix** — price vs. rent scatter plot, top/bottom 15 yield segments, with confidence-level flagging and a stated methodology note.

## Limitations

- `actual_area` in the rent dataset is assumed to be in square metres (consistent with `procedure_area` in sales) but this was not independently confirmed against a price field the way the sales area unit was.
- Percentile-based outlier clipping (0.5th–99.5th) was applied citywide, not per area, so an unusually priced but legitimate area could theoretically be affected.
- Yield is a gross figure — it does not account for service charges, vacancy, or transaction costs.
