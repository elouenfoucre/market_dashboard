import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta

st.set_page_config(page_title="Daily Performance Monitor", layout="wide")
st.title("Daily Performance Monitor with Yahoo Finance")

# ---------------------------
# Asset universe
# ---------------------------
assets = {
    "Indexes": {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Dow Jones": "^DJI",
        "Euro Stoxx 50": "^STOXX50E",
        "FTSE 100": "^FTSE",
        "Nikkei 225": "^N225"
    },
    "Stocks": {
        "Air Liquide": "AI.PA",
        "NVIDIA": "NVDA",
        "STMicroelectronics": "STM",
        "LVMH": "MC.PA",
        "Airbus": "AIR.PA",
        "TotalEnergies": "TTE.PA"
    },
    "Commodities": {
        "Gold": "GC=F",
        "Crude Oil": "CL=F"
    },
    "Foreign Exchange": {
        "EUR/USD": "EURUSD=X",
        "EUR/CHF": "EURCHF=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "EUR/TRY": "EURTRY=X"
    }
}

# Horizons (calendar days)
PERIODS = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "1Y": 365,
    "3Y": 365 * 3,
    "5Y": 365 * 5,
    "10Y": 365 * 10,
    "20Y": 365 * 20,
}
period_list = list(PERIODS.keys())

today = pd.Timestamp.today().normalize()

# ---------------------------
# Sidebar horizon selector
# ---------------------------
selected_horizon = st.sidebar.selectbox("Select horizon", period_list, index=3)  # default = 1Y
start_all = today - timedelta(days=PERIODS[selected_horizon] + 30)

if selected_horizon in ["10Y", "20Y"]:
    st.warning("⚠️ Fetching long histories may take longer...")

# ---------------------------
# Helpers
# ---------------------------
@st.cache_data(show_spinner=True, ttl=900)
def fetch_all_tickers(ticker_dict, start, end):
    """Batch download all tickers in dictionary"""
    flat = [t for group in ticker_dict.values() for t in group.values()]
    df = yf.download(flat, start=start, end=end, progress=False)["Close"]
    if isinstance(df, pd.Series):  # only one ticker
        df = df.to_frame()
    return df.dropna(how="all")

def window_stats(series: pd.Series, days: int):
    """Compute returns, min, max, vol for given horizon (calendar days)."""
    if series.empty:
        return (np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)
    win = series.loc[series.index >= (today - timedelta(days=days))]
    if win.empty or len(win) < 2:
        v = float(win.iloc[-1]) if len(win) else np.nan
        return (v, v, np.nan, v, v, np.nan)

    start = float(win.iloc[0])
    last  = float(win.iloc[-1])
    ret   = (last / start - 1.0) * 100.0 if start else np.nan
    mn    = float(win.min())
    mx    = float(win.max())

    rets = win.pct_change().dropna()
    ann_vol = float(rets.std() * np.sqrt(252) * 100) if not rets.empty else np.nan

    return (start, last, ret, mn, mx, ann_vol)

def segment(min_px: float, last_px: float, max_px: float, width: int = 18) -> str:
    """ASCII segment: min ── ● ── max (monospace)."""
    if any(map(lambda x: x is None or np.isnan(x), [min_px, last_px, max_px])):
        return "N/A"
    if max_px == min_px:
        left = width // 2
        bar = "─" * left + "●" + "─" * (width - left)
        return f"{min_px:,.2f} {bar} {max_px:,.2f}"
    ratio = (last_px - min_px) / (max_px - min_px)
    ratio = min(max(ratio, 0.0), 1.0)
    dot_idx = int(round(ratio * width))
    bar = "".join("●" if i == dot_idx else "─" for i in range(width + 1))
    return f"{min_px:,.2f} {bar} {max_px:,.2f}"

def color_pct_html(pct: float) -> str:
    """Return colored bold HTML for a single % value."""
    if pct is None or np.isnan(pct):
        return "<span>N/A</span>"
    color = "#0a7a1f" if pct >= 0 else "#b22222"
    return f"<span style='color:{color}; font-weight:600'>{pct:+.2f}%</span>"

def format_period_cell(ret_pct: float, min_px: float, last_px: float, max_px: float, ann_vol_pct: float) -> str:
    """HTML cell with three lines: % return, segment, annualized vol."""
    if any(np.isnan(x) for x in [min_px, last_px, max_px]):
        return "<div>N/A</div>"
    seg = segment(min_px, last_px, max_px, width=18)
    vol_text = "N/A" if (ann_vol_pct is None or np.isnan(ann_vol_pct)) else f"{ann_vol_pct:.1f}%"
    return (
        f"<div>"
        f"{color_pct_html(ret_pct)}<br>"
        f"<span style='font-family: monospace;'>{seg}</span><br>"
        f"<span style='color:#555'>Vol (ann): {vol_text}</span>"
        f"</div>"
    )

def df_to_html(df: pd.DataFrame, index_name: str = "Asset") -> str:
    """Render as HTML table with custom styling."""
    css = """
    <style>
      table.minmax { border-collapse: collapse; width: 100%; font-size: 0.92rem; }
      table.minmax th, table.minmax td { border: 1px solid #eee; padding: 8px 10px; vertical-align: middle; }
      table.minmax th { background: #fafafa; text-align: left; position: sticky; top: 0; z-index: 1; }
      table.minmax td.num { text-align: right; }
      table.minmax td.wide { white-space: nowrap; }
    </style>
    """
    cols = df.columns.tolist()
    parts = [css, "<table class='minmax'>", "<thead><tr>"]
    parts.append(f"<th>{index_name}</th>")
    for c in cols:
        parts.append(f"<th>{c}</th>")
    parts.append("</tr></thead><tbody>")

    for idx, row in df.iterrows():
        parts.append("<tr>")
        parts.append(f"<td>{idx}</td>")
        for c in cols:
            val = row[c]
            if isinstance(val, (int, float, np.floating)) and not np.isnan(val):
                parts.append(f"<td class='num'>{val:,.2f}</td>")
            elif isinstance(val, str) and (val.startswith("<div>") or val.startswith("<span")):
                parts.append(f"<td class='wide'>{val}</td>")
            elif pd.isna(val):
                parts.append("<td>N/A</td>")
            else:
                parts.append(f"<td>{val}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)

# ---------------------------
# Build and print per-class sections
# ---------------------------
skipped_all = []
df_all = fetch_all_tickers(assets, start_all, today)

for class_name, tickers in assets.items():
    st.markdown(f"## {class_name}")

    rows = []
    skipped = []

    for asset_name, ticker in tickers.items():
        if ticker not in df_all.columns:  # missing data
            skipped.append(asset_name)
            continue

        s = df_all[ticker].dropna()
        if s.empty:
            skipped.append(asset_name)
            continue

        last_price = float(s.iloc[-1])

        # 1D %
        one_day_pct = np.nan
        if len(s) >= 2:
            prev_price = float(s.iloc[-2])
            if prev_price:
                one_day_pct = (last_price / prev_price - 1.0) * 100.0
        one_day_html = color_pct_html(one_day_pct)

        row = {
            "Last Price": last_price,
            "1D %": one_day_html,
        }

        # Horizon stats
        for label, days in PERIODS.items():
            start_px, last_px, ret_pct, mn, mx, ann_vol_pct = window_stats(s, days)
            row[f"{label}"] = format_period_cell(ret_pct, mn, last_px, mx, ann_vol_pct)

        rows.append(pd.Series(row, name=asset_name))

    if not rows:
        st.warning(f"No data available for {class_name}.")
        continue

    df = pd.DataFrame(rows)
    st.markdown(df_to_html(df, index_name="Asset"), unsafe_allow_html=True)

    if skipped:
        skipped_all.extend([f"{class_name}: {a}" for a in skipped])

# Global skipped notice
if skipped_all:
    st.warning("No data for: " + ", ".join(skipped_all))
