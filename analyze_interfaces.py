import polars as pl
import os
from pathlib import Path

interfaces_config = {
    "balancesheet_vip": "end_date_dt",
    "block_trade": "trade_date_dt",
    "cashflow_vip": "end_date_dt",
    "cyq_chips": "trade_date_dt",
    "cyq_chips1": "trade_date_dt",
    "daily_basic": "trade_date_dt",
    "disclosure_date": "ann_date_dt",
    "dividend": "end_date_dt",
    "express_vip": "ann_date_dt",
    "fina_audit": "ann_date_dt",
    "fina_indicator_vip": "end_date_dt",
    "fina_mainbz_vip": "ann_date_dt",
    "forecast_vip": "ann_date_dt",
    "income_vip": "end_date_dt",
    "moneyflow": "trade_date_dt",
    "pledge_stat": "end_date_dt",
    "repurchase": "ann_date_dt",
    "stk_factor_pro": "trade_date_dt",
    "stk_rewards": "ann_date_dt",
    "stock_basic": "list_date_dt",
    "suspend_d": "trade_date_dt",
    "top10_floatholders": "ann_date_dt",
    "top10_holders": "ann_date_dt",
    "trade_cal": "cal_date_dt",
}

data_dir = Path("/home/quan/testdata/aspipe_v4/data")


def analyze_interface(interface_name: str, date_col: str) -> dict:
    interface_dir = data_dir / interface_name
    files = sorted(interface_dir.glob("*.parquet"))

    if len(files) > 100:
        files = files[:100]

    dfs = []
    for f in files:
        try:
            df = pl.read_parquet(f)
            if date_col in df.columns and "ts_code" in df.columns:
                dfs.append(df.select([date_col, "ts_code"]))
        except:
            continue

    if not dfs:
        return {
            "interface": interface_name,
            "stock_count": 0,
            "min_year": None,
            "2000-2005": 0.0,
            "2005-2010": 0.0,
            "2010-2015": 0.0,
            "2015-2020": 0.0,
            "2020-至今": 0.0,
            "avg_span_days": 0.0,
        }

    df_all = pl.concat(dfs)

    if df_all.schema[date_col] == pl.String:
        df_all = df_all.with_columns(
            pl.col(date_col).str.strip_chars().str.to_date("%Y%m%d").alias("date")
        )
    else:
        df_all = df_all.with_columns(pl.col(date_col).alias("date"))
    df_all = df_all.filter(pl.col("date").is_not_null())

    stock_count = df_all.select("ts_code").unique().height

    years = df_all.with_columns(pl.col("date").dt.year().alias("year"))
    min_year = years.select("year").min().item()

    total_records = df_all.height
    year_ranges = [
        (2000, 2005, "2000-2005"),
        (2005, 2010, "2005-2010"),
        (2010, 2015, "2010-2015"),
        (2015, 2020, "2015-2020"),
        (2020, 2030, "2020-至今"),
    ]

    year_pcts = {}
    for start, end, label in year_ranges:
        count = df_all.filter(
            (pl.col("date").dt.year() >= start) & (pl.col("date").dt.year() < end)
        ).height
        year_pcts[label] = (
            round(count / total_records * 100, 2) if total_records > 0 else 0.0
        )

    spans = df_all.group_by("ts_code").agg(
        pl.col("date").min().alias("min_date"), pl.col("date").max().alias("max_date")
    )
    spans = spans.with_columns(
        (pl.col("max_date") - pl.col("min_date")).dt.total_days().alias("span_days")
    )
    avg_span = spans.select("span_days").mean().item()

    return {
        "interface": interface_name,
        "stock_count": stock_count,
        "min_year": min_year,
        **year_pcts,
        "avg_span_days": round(avg_span, 2) if avg_span else 0.0,
    }


results = []
for interface, date_col in interfaces_config.items():
    print(f"Processing {interface}...")
    result = analyze_interface(interface, date_col)
    results.append(result)

df_result = pl.DataFrame(results)
df_result = df_result.select(
    [
        "interface",
        "stock_count",
        "min_year",
        "2000-2005",
        "2005-2010",
        "2010-2015",
        "2015-2020",
        "2020-至今",
        "avg_span_days",
    ]
)

print(df_result)
df_result.write_csv("/home/quan/testdata/aspipe_v4/interface_analysis.csv")
