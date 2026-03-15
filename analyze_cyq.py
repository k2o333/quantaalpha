import os
import polars as pl
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

data_dir = "data/cyq_chips"


def process_file(file):
    df = pl.read_parquet(os.path.join(data_dir, file))
    if "ts_code" in df.columns and "trade_date_dt" in df.columns:
        min_dates = df.group_by("ts_code").agg(
            pl.col("trade_date_dt").min().alias("start_date")
        )
        return min_dates.rows()
    return []


files = [f for f in os.listdir(data_dir) if f.endswith(".parquet")]

company_min_dates = {}

with ProcessPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_file, files)

for result in results:
    for ts_code, start_date in result:
        if ts_code not in company_min_dates or start_date < company_min_dates[ts_code]:
            company_min_dates[ts_code] = start_date

company_start_years = defaultdict(int)
for ts_code, start_date in company_min_dates.items():
    year = start_date.year
    company_start_years[year] += 1

total_companies = len(company_min_dates)
print(f"总公司数量: {total_companies}")
for year in sorted(company_start_years.keys()):
    print(f"{year}年: {company_start_years[year]}家")
