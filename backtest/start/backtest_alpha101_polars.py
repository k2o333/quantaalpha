#!/usr/bin/env python3
"""使用vnpy的Alpha101因子进行回测 - 纯Polars引擎"""
import sys
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/third_party/vnpy')

import glob
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import polars as pl
import numpy as np
from tqdm import tqdm


class SimpleBacktestEngine:
    def __init__(self, capital: float = 1_000_000):
        self.capital = capital
        self.cash = capital
        self.positions = defaultdict(float)
        self.trades = []
        self.daily_pnl = []
        
    def reset(self):
        self.cash = self.capital
        self.positions = defaultdict(float)
        self.trades = []
        self.daily_pnl = []
        
    def calculate_alpha101_factor(self, df: pl.DataFrame) -> pl.DataFrame:
        """计算Alpha101因子 (Alpha3: -1 * ts_corr(cs_rank(open), cs_rank(vol), 10))"""
        print("计算Alpha101因子 (纯Polars实现)...")
        
        # 纯Polars实现：先计算截面排名，再计算滚动相关系数
        df = df.with_columns([
            pl.col("open").rank().over("trade_date_dt").alias("open_rank"),
            pl.col("vol").rank().over("trade_date_dt").alias("vol_rank"),
        ])
        
        # 使用原生 pl.rolling_corr
        df = df.with_columns([
            (pl.rolling_corr("open_rank", "vol_rank", window_size=10).over("ts_code") * -1).alias("alpha3")
        ])
        
        return df
    
    def run_backtest(self, df: pl.DataFrame, start_date: str, end_date: str, top_k: int = 20, hold_days: int = 5):
        self.reset()
        start_dt = datetime.strptime(start_date, "%Y%m%d").date()
        end_dt = datetime.strptime(end_date, "%Y%m%d").date()
        df = df.filter((pl.col("trade_date_dt") >= start_dt) & (pl.col("trade_date_dt") <= end_dt))
        
        df = self.calculate_alpha101_factor(df)
        
        trade_dates = df["trade_date_dt"].unique().sort()
        print(f"回测区间: {start_date} 到 {end_date}, 共 {len(trade_dates)} 个交易日")
        
        holdings = {}
        for i, current_date in enumerate(tqdm(trade_dates, desc="回测进度")):
            day_df = df.filter(pl.col("trade_date_dt") == current_date)
            close_prices = {row["ts_code"]: row["close"] for row in day_df.iter_rows(named=True)}
            
            portfolio_value = self.cash
            for code, pos in self.positions.items():
                if code in close_prices:
                    portfolio_value += pos * close_prices[code]
            
            codes_to_sell = [code for code, (buy_date, _, _) in holdings.items() 
                           if (current_date - buy_date).days >= hold_days and code in close_prices]
            
            for code in codes_to_sell:
                if code in close_prices and self.positions[code] > 0:
                    sell_price = close_prices[code]
                    quantity = self.positions[code]
                    proceeds = sell_price * quantity
                    commission = proceeds * 0.0015
                    self.cash += proceeds - commission
                    buy_date, buy_price, _ = holdings[code]
                    pnl = (sell_price - buy_price) * quantity - commission
                    self.trades.append({"date": current_date, "code": code, "action": "SELL",
                                       "price": sell_price, "quantity": quantity, "pnl": pnl})
                    del self.positions[code]
                    del holdings[code]
            
            if i % hold_days == 0:
                signals = day_df.filter(pl.col("alpha3").is_not_nan()).sort("alpha3", descending=True)
                buy_list = signals.head(top_k)["ts_code"].to_list()
                available_cash = self.cash * 0.95
                if buy_list and available_cash > 0:
                    cash_per_stock = available_cash / len(buy_list)
                    for code in buy_list:
                        if code in close_prices and code not in self.positions:
                            buy_price = close_prices[code]
                            quantity = int(cash_per_stock / buy_price / 100) * 100
                            if quantity > 0:
                                cost = buy_price * quantity
                                commission = cost * 0.0005
                                if self.cash >= cost + commission:
                                    self.cash -= (cost + commission)
                                    self.positions[code] = quantity
                                    holdings[code] = (current_date, buy_price, quantity)
                                    self.trades.append({"date": current_date, "code": code, "action": "BUY",
                                                       "price": buy_price, "quantity": quantity, "pnl": -commission})
            
            self.daily_pnl.append({"date": current_date, "cash": self.cash, 
                                  "portfolio_value": portfolio_value, "positions": len(self.positions)})
        
        return self.calculate_statistics()
    
    def calculate_statistics(self):
        if not self.daily_pnl:
            return {}, pl.DataFrame()
        df = pl.DataFrame(self.daily_pnl)
        df = df.with_columns([(pl.col("portfolio_value") / pl.lit(self.capital) - 1).alias("ret")])
        df = df.with_columns([pl.col("portfolio_value").cum_max().alias("cummax")])
        df = df.with_columns([
            (pl.col("portfolio_value") - pl.col("cummax")).alias("drawdown"),
            ((pl.col("portfolio_value") / pl.col("cummax") - 1) * 100).alias("drawdown_pct")
        ])
        
        total_return = (df["portfolio_value"][-1] / self.capital - 1) * 100
        max_drawdown = df["drawdown_pct"].min()
        daily_returns = df["ret"].diff().drop_nulls()
        sharpe_ratio = 0
        if len(daily_returns) > 1:
            daily_rf = 0.03 / 252
            excess_returns = daily_returns - daily_rf
            if daily_returns.std() > 0:
                sharpe_ratio = (excess_returns.mean() / daily_returns.std()) * np.sqrt(252)
        
        total_trades = len([t for t in self.trades if t["action"] == "SELL"])
        win_trades = len([t for t in self.trades if t["action"] == "SELL" and t["pnl"] > 0])
        
        stats = {
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": total_trades,
            "win_rate": (win_trades / total_trades * 100) if total_trades > 0 else 0,
            "final_value": df["portfolio_value"][-1],
            "start_date": df["date"][0],
            "end_date": df["date"][-1]
        }
        return stats, df


def load_data(data_path: str, start_date: str, end_date: str) -> pl.DataFrame:
    print(f"加载数据从 {start_date} 到 {end_date}...")
    start_dt = datetime.strptime(start_date, "%Y%m%d").date()
    end_dt = datetime.strptime(end_date, "%Y%m%d").date()
    files = glob.glob(f"{data_path}/*.parquet")
    selected_files = []
    for f in files:
        basename = Path(f).stem
        parts = basename.split("_")
        if len(parts) >= 4:
            try:
                file_date = datetime.strptime(parts[3], "%Y%m%d").date()
                if start_dt <= file_date <= end_dt:
                    selected_files.append(f)
            except:
                continue
    print(f"找到 {len(selected_files)} 个数据文件")
    dfs = []
    for f in tqdm(selected_files, desc="读取文件"):
        try:
            df = pl.read_parquet(f)
            cols = ["ts_code", "trade_date", "open", "close", "vol", "trade_date_dt"]
            available_cols = [c for c in cols if c in df.columns]
            dfs.append(df.select(available_cols))
        except:
            pass
    if dfs:
        combined = pl.concat(dfs)
        combined = combined.unique(subset=["ts_code", "trade_date"])
        return combined
    return pl.DataFrame()


def main():
    import time
    DATA_PATH = "/home/quan/testdata/aspipe_v4/data/stk_factor_pro"
    START_DATE = "20240101"
    END_DATE = "20241231"
    
    start_time = time.time()
    
    df = load_data(DATA_PATH, START_DATE, END_DATE)
    if df.is_empty():
        print("没有加载到数据!")
        return
    print(f"数据加载完成，共 {len(df)} 条记录")
    print(f"股票数量: {df['ts_code'].n_unique()}")
    print(f"日期范围: {df['trade_date_dt'].min()} 到 {df['trade_date_dt'].max()}")
    
    engine = SimpleBacktestEngine(capital=1_000_000)
    stats, daily_df = engine.run_backtest(df, START_DATE, END_DATE, top_k=20, hold_days=5)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print("回测结果 (纯Polars版本)")
    print("="*50)
    print(f"回测区间: {stats['start_date']} 到 {stats['end_date']}")
    print(f"总收益率: {stats['total_return']:.2f}%")
    print(f"最大回撤: {stats['max_drawdown']:.2f}%")
    print(f"夏普比率: {stats['sharpe_ratio']:.2f}")
    print(f"总交易次数: {stats['total_trades']}")
    print(f"胜率: {stats['win_rate']:.2f}%")
    print(f"最终资金: {stats['final_value']:,.2f}")
    print(f"总耗时: {elapsed:.2f}秒")
    print("="*50)
    
    daily_df.write_csv("/home/quan/testdata/aspipe_v4/backtest_result_polars.csv")
    print("\n详细结果已保存到: /home/quan/testdata/aspipe_v4/backtest_result_polars.csv")


if __name__ == "__main__":
    main()
