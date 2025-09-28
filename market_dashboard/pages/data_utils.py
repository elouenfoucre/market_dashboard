# utils/data_utils.py
import os
import pandas as pd
import yfinance as yf

def load_incremental_data(ticker: str, start="2000-01-01", end=None, cache_dir="data_cache"):
    os.makedirs(cache_dir, exist_ok=True)
    file = os.path.join(cache_dir, f"{ticker.replace('=','_')}.parquet")

    if os.path.exists(file):
        df = pd.read_parquet(file)
        last_date = df.index.max()
        start_dl = last_date + pd.Timedelta(days=1)
    else:
        df = pd.DataFrame()
        start_dl = start

    if end is None:
        end = pd.Timestamp.today().normalize()

    if pd.to_datetime(start_dl) <= end:
        try:
            new_data = yf.download(ticker, start=start_dl, end=end, progress=False)
            if not new_data.empty:
                df = pd.concat([df, new_data])
                df = df[~df.index.duplicated(keep="last")]
                df.to_parquet(file)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    return df
