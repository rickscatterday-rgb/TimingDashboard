import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import requests
import xml.etree.ElementTree as ET

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v5.6", layout="wide")

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: 'Courier New', Courier, monospace !important; }
    .main { background-color: #05070a; color: #c9d1d9; }
    .metric-container {
        border: 1px solid #30363d;
        padding: 20px;
        background-color: #0d1117;
        margin-bottom: 20px;
    }
    .news-card {
        background-color: #1a1010;
        border: 1px solid #f85149;
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 4px;
    }
    .market-open { color: #39d353; font-weight: bold; }
    .market-closed { color: #f85149; font-weight: bold; }
    .red-folder { color: #f85149; font-weight: bold; animation: blinker 2s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    .action-card {
        padding: 20px; text-align: center; border-radius: 4px; font-weight: bold; font-size: 26px; border: 2px solid #30363d;
    }
    .status-no-trade { background-color: #3e1b1b; color: #f85149; border-color: #f85149; }
    .status-sell-premium { background-color: #1b2e3e; color: #58a6ff; border-color: #58a6ff; }
    .status-wait { background-color: #21262d; color: #8b949e; border-color: #30363d; }
    .logic-box { background-color: #161b22; border-left: 3px solid #58a6ff; padding: 15px; margin: 10px 0; font-size: 0.85em; }
    .progress-bg { background-color: #30363d; width: 100%; height: 14px; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# --- 2. LIVE ECONOMIC CALENDAR ENGINE ---
def get_live_red_folders():
    """
    Fetches the actual weekly calendar from Forex Factory's RSS feed.
    Filters for 'High' impact events only.
    """
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    upcoming_red_folders = []

    try:
        # Forex Factory XML Weekly Feed
        response = requests.get("https://www.forexfactory.com/ff_calendar_thisweek.xml", timeout=5)
        root = ET.fromstring(response.content)

        for event in root.findall('event'):
            impact = event.find('impact').text
            # Only look for "High" impact (Red Folders)
            if impact == 'High':
                title = event.find('title').text
                date_str = event.find('date').text # Format: MM-DD-YYYY
                time_str = event.find('time').text # Format: 8:30am
                
                # Combine and parse date/time
                full_dt_str = f"{date_str} {time_str}"
                # Handle cases with no specific time (e.g. 'All Day')
                try:
                    event_dt = datetime.strptime(full_dt_str, "%m-%d-%Y %I:%M%p")
                    event_dt = tz.localize(event_dt)
                except:
                    continue

                diff = event_dt - now
                if diff.total_seconds() > 0:
                    h, r = divmod(int(diff.total_seconds()), 3600)
                    m, _ = divmod(r, 60)
                    upcoming_red_folders.append({
                        "event": title,
                        "date": event_dt,
                        "countdown": f"{h}h {m}m",
                        "urgent": h < 4
                    })
    except Exception as e:
        # Fallback to specific High Impact Jan 2025 events if RSS fails
        fallback_events = [
            {"event": "CPI Inflation Data", "date": datetime(2025, 1, 15, 8, 30, tzinfo=tz)},
            {"event": "Retail Sales", "date": datetime(2025, 1, 15, 8, 30, tzinfo=tz)},
            {"event": "FOMC Rate Decision", "date": datetime(2025, 1, 29, 14, 0, tzinfo=tz)},
        ]
        for fe in fallback_events:
            diff = fe['date'] - now
            if diff.total_seconds() > 0:
                h, r = divmod(int(diff.total_seconds()), 3600)
                m, _ = divmod(r, 60)
                fe['countdown'] = f"{h}h {m}m"
                fe['urgent'] = h < 4
                upcoming_red_folders.append(fe)

    return sorted(upcoming_red_folders, key=lambda x: x['date'])[:3]

# --- 3. MARKET STATUS ---
def get_market_status():
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    if now.weekday() >= 5: return "CLOSED (WEEKEND)", "market-closed"
    open_t = now.replace(hour=9, minute=30, second=0)
    close_t = now.replace(hour=16, minute=0, second=0)
    if open_t <= now <= close_t: return "MARKET OPEN", "market-open"
    return "MARKET CLOSED", "market-closed"

# --- 4. DATA ENGINE & CORE LOGIC ---
@st.cache_data(ttl=3600)
def fetch_alpha_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'DX-Y.NYB', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        df = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        return df['Close'] if not df.empty else None
    except: return None

def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    vix = prices['^VIX'].dropna(); vix_px = float(vix.iloc[-1])
    hyg = prices['HYG'].dropna(); hyg_px = float(hyg.iloc[-1])
    dxy = prices['DX-Y.NYB'].dropna(); dxy_px = float(dxy.iloc[-1])

    # [TACTICAL DECISION LOGIC]
    spy_200ma = spy.rolling(200).mean().iloc[-1]
    dist_to_200 = (spy_px - spy_200ma) / spy_200ma
    downtrend = dist_to_200 <= -0.02
    
    hyg_20ma = hyg.rolling(20).mean().iloc[-1]
    dxy_20_high = dxy.tail(20).max()
    env_ok = (dist_to_200 > -0.02 and hyg_px >= hyg_20ma and dxy_px < dxy_20_high)

    vix_prev = vix.shift(1).iloc[-1]
    vix_zscore = (vix_px - vix.rolling(20).mean().iloc[-1]) / vix.rolling(20).std().iloc[-1]
    vix_change = (vix_px - vix_prev) / vix_prev
    good_spike = (vix_change > 0.08 and vix_zscore > 1.5)

    if downtrend: action, a_class = "NO TRADE", "status-no-trade"
    elif env_ok and good_spike: action, a_class = "SELL PREMIUM", "status-sell-premium"
    else: action, a_class = "WAIT", "status-wait"

    # [7-METRIC STRENGTH SYSTEM]
    tr_p = min(100, max(0, 50 + (dist_to_200 * 1000)))
    ratio = (prices['HYG'] / prices['IEF']).dropna()
    cr_p = min(100, max(0, 50 + ((ratio.iloc[-1] / ratio.rolling(50).mean().iloc[-1]) - 1) * 2000))
    above = sum([1 for s in ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE'] if prices[s].iloc[-1] > prices[s].rolling(200).mean().iloc[-1]])
    br_p = (above / 11) * 100
    vx_p = min(100, max(0, (vix_zscore + 2) * 25))
    delta = spy.diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi_val = 100 - (100 / (1 + (gain/loss))).iloc[-1]
    rsi_p = 100 - rsi_val 
    dm = (spy > spy.shift(4)).astype(int); lv = int(dm.iloc[-1]); c = 0
    for val in reversed(dm.tolist()):
        if val == lv: c += 1
        else: break
    dm_p = (c / 9 * 100) if lv == 0 else (100 - (c / 9 * 100))
    
    # Simple logic for FRED yield curve fallback
    yc_v = 0.0; yc_p = 50 

    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p + rsi_p) / 7
    return {
        "avg": avg, "action": action, "a_class": a_class, "metrics": [
            ("Trend: 200MA Prox", f"{dist_to_200:+.2%}", tr_p),
            ("Credit: Risk Ratio", "HYG/IEF", cr_p),
            ("Breadth: Sectors", f"{above}/11 Bullish", br_p),
            ("Tactical: VIX Z", f"Z: {vix_zscore:.2f}", vx_p),
            ("Tactical: RSI-14", f"Val: {rsi_val:.1f}
