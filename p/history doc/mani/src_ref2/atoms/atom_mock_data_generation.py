#!/usr/bin/env python
"""
Verification script for atom_mock_data_generation
This script verifies mock data generation mechanisms appropriate for A-share market data platform
"""

def verify_mock_data_generation():
    try:
        import polars as pl
        import pyarrow as pa
        from datetime import datetime, timedelta, date
        import random

        # Generate mock A-share stock symbols
        def generate_mock_symbols(count=10):
            symbols = []
            for i in range(count):
                # Generate realistic Chinese stock symbols
                if i % 3 == 0:
                    # SSE (Shanghai) A-shares starting with 600, 601, 603
                    prefix = random.choice(["600", "601", "603"])
                    suffix = f"{random.randint(1, 9999):04d}"
                    symbol = f"SH{prefix}{suffix}"
                elif i % 3 == 1:
                    # SZE (Shenzhen) Main Board A-shares starting with 000, 001, 002
                    prefix = random.choice(["000", "001", "002"])
                    suffix = f"{random.randint(1, 9999):04d}"
                    symbol = f"SZ{prefix}{suffix}"
                else:
                    # SZE GEM (Growth Enterprise Market) starting with 300
                    suffix = f"{random.randint(1, 9999):04d}"
                    symbol = f"SZ300{suffix}"
                symbols.append(symbol)
            return symbols

        # Generate mock trading dates (business days)
        def generate_trading_dates(start_date, count):
            dates = []
            current_date = start_date
            while len(dates) < count:
                # Skip weekends (Saturday=5, Sunday=6 in Python weekday)
                if current_date.weekday() < 5:
                    dates.append(current_date.date())
                current_date += timedelta(days=1)
            return dates

        # Generate mock stock basic information
        symbols = generate_mock_symbols(5)
        symbol_names = ["股票A", "股票B", "股票C", "股票D", "股票E"]
        industries = ["制造业", "金融业", "房地产业", "信息技术", "医疗保健"]
        exchanges = ["SSE", "SZE", "SZE"]

        basic_info_data = pl.DataFrame({
            "symbol": symbols,
            "name": symbol_names,
            "industry": [random.choice(industries) for _ in range(5)],
            "exchange": [random.choice(exchanges) for _ in range(5)],
            "listing_date": [date(2010, 1, 1), date(2012, 5, 15), date(2015, 8, 20), date(2018, 3, 12), date(2020, 7, 8)],
            "currency": ["CNY"] * 5,
            "market_cap": [random.uniform(1e9, 500e9) for _ in range(5)]  # 1 billion to 500 billion CNY
        })

        # Generate mock daily trading data
        trading_dates = generate_trading_dates(datetime(2023, 1, 1), 10)  # 10 trading days

        trading_data_rows = []
        for symbol in symbols[:3]:  # Use first 3 symbols for trading data
            base_price = random.uniform(10, 200)  # Base price between 10 and 200
            for trade_date in trading_dates:
                # Generate realistic daily OHLC data with some variation
                open_price = base_price * (0.98 + random.uniform(-0.02, 0.04))
                high_price = open_price * (1 + random.uniform(0.005, 0.05))
                low_price = open_price * (1 - random.uniform(0.005, 0.05))
                close_price = base_price * (0.99 + random.uniform(-0.03, 0.03))

                # Ensure high >= open/close >= low
                high_price = max(high_price, open_price, close_price)
                low_price = min(low_price, open_price, close_price)

                volume = random.randint(100000, 10000000)  # Volume between 100k and 10M
                turnover = close_price * volume

                trading_data_rows.append({
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open_price": round(open_price, 3),
                    "high_price": round(high_price, 3),
                    "low_price": round(low_price, 3),
                    "close_price": round(close_price, 3),
                    "volume": volume,
                    "turnover": round(turnover, 2),
                    "prev_close": round(open_price / (1 + random.uniform(-0.02, 0.02)), 3)
                })

                # Adjust base price for next day based on return
                base_price = close_price * (1 + random.uniform(-0.05, 0.05))

        trading_data = pl.DataFrame(trading_data_rows)

        # Verify data structure integrity
        assert len(basic_info_data) == 5, "Should have 5 basic info records"
        assert len(trading_data) > 0, "Should have trading data records"
        assert "symbol" in basic_info_data.columns, "Basic info should have symbol column"
        assert "symbol" in trading_data.columns, "Trading data should have symbol column"
        assert "trade_date" in trading_data.columns, "Trading data should have trade_date column"

        # Verify data types
        assert basic_info_data.schema["symbol"] == pl.Utf8, "Symbol should be string type"
        assert basic_info_data.schema["market_cap"] == pl.Float64, "Market cap should be float type"
        assert trading_data.schema["close_price"] == pl.Float64, "Price should be float type"
        assert trading_data.schema["volume"] == pl.Int64, "Volume should be integer type"

        print(f"Generated {len(basic_info_data)} basic info records")
        print(f"Generated {len(trading_data)} trading records")
        print(f"Symbols: {basic_info_data['symbol'].head(3).to_list()}")
        print(f"Trading dates range: {min(trading_data['trade_date'])} to {max(trading_data['trade_date'])}")
        print(f"Price range: {min(trading_data['close_price'])} - {max(trading_data['close_price'])}")
        print(f"Volume range: {min(trading_data['volume'])} - {max(trading_data['volume'])}")

        # Verify that the generated data follows expected patterns for A-share market
        # (e.g., prices are reasonable, volumes are realistic, etc.)
        reasonable_prices = all(0.01 <= price <= 10000 for price in trading_data['close_price'])
        reasonable_volumes = all(0 < vol <= 1e9 for vol in trading_data['volume'])

        assert reasonable_prices, "All prices should be in reasonable range for A-share market"
        assert reasonable_volumes, "All volumes should be in reasonable range for A-share market"

        print("SUCCESS: Mock data generation works appropriately for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error generating mock data: {e}")
        return False

if __name__ == "__main__":
    success = verify_mock_data_generation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)