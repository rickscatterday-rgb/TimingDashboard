import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v5.1", layout="wide")

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
        padding: 10px;
        margin-bottom: 10px;
        border-radius: 4px;
    }
    .red-folder { color: #f85149; font-weight: bold; animation: blinker 2s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    .action-card {
        padding: 20px; text-align: center; border-radius: 4px; font-weight: bold; font-size: 24px; border: 2px solid #30363d;
    }
    .status-no-trade { background-color: #3e1b1b; color: #f85149; border-color: #f85149; }
    .status-sell-premium { background-color: #1b2e3e; color: #58a6ff; border-color: #58a6ff; }
    .status-wait { background-color: #21262d; color: #8b949e; border-color: #30363d; }
    .progress-bg { background-color: #30363d; width: 100%; height: 14px; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# --- 2. ECONOMIC CALENDAR ENGINE ---
def get_red_folder_news():
    """
    In a production app, fetch from Finnhub or AlphaVantage.
    Here we simulate the major 'Red Folder' schedule for the current cycle.
    """
    now = datetime.now(pytz.timezone('US/Eastern'))
    
    # Example Schedule of Red Folder Events (Simulated for UI demonstration)
    # In a real scenario, you would parse a JSON feed here.
    events = [
        {"event": "CPI Inflation Data", "date": (now + timedelta(days=1)).replace(hour=8, minute=30)},
        {"event": "FOMC Rate Decision", "date": (now + timedelta(hours=5)).replace(minute=0)},
        {"event": "Non-Farm Payrolls", "date": (now + timedelta(days=3)).replace(hour=8, minute=30)},
        {"event": "Retail Sales MoM", "date": (now + timedelta(hours=26)).replace(minute=30)}
    ]
    
    upcoming = []
    for e in events:
        diff = e['date'] - now
        if diff.total_seconds() > 0:
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            e['countdown'] = f"{hours}h {minutes}m"
            e['urgent'] = hours < 4
            upcoming.append(e)
            
    return sorted(upcoming, key=lambda x: x['date'])

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_alpha_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'DX-Y.NYB', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        df = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        return df['Close'] if not df.empty else None
    except: return None

# --- 4. ANALYTICS ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    news_events = get_red_folder_news()
    if prices is None: return None
    
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    vix = prices['^VIX'].dropna(); vix_px = float(vix.iloc[-1])
    hyg = prices['HYG'].dropna(); hyg_px = float(hyg.iloc[-1])
    dxy = prices['DX-Y.NYB'].dropna(); dxy_px = float(dxy.iloc[-1])

    # [STRATEGIC OVERRIDE LOGIC]
    spy_200ma = spy.rolling(200).mean().iloc[-1]
    dist_200 = (spy_px - spy_200ma) / spy_200ma
    downtrend = dist_200 <= -0.02
    
    hyg_20ma = hyg.rolling(20).mean().iloc[-1]
    dxy_20_high = dxy.tail(20).max()
    env_ok = (dist_200 > -0.02 and hyg_px >= hyg_20ma and dxy_px < dxy_20_high)

    vix_prev = vix.shift(1).iloc[-1]
    vix_change = (vix_px - vix_prev) / vix_prev
    vix_20ma = vix.rolling(20).mean().iloc[-1]
    vix_20std = vix.rolling(20).std().iloc[-1]
    vix_zscore = (vix_px - vix_20ma) / vix_20std
    good_spike = (vix_change > 0.08 and vix_zscore > 1.5)

    # News Buffer Logic: If Red Folder event is < 4 hours away, WAIT.
    event_risk = any(e['urgent'] for e in news_events)

    if downtrend: 
        action, action_class = "NO TRADE", "status-no-trade"
    elif event_risk:
        action, action_class = "WAIT (NEWS)", "status-wait"
    elif env_ok and good_spike: 
        action, action_class = "SELL PREMIUM", "status-sell-premium"
    else: 
        action, action_class = "WAIT", "status-wait"

    # [STRENGTH SCORING]
    tr_p = min(100, max(0, 50 + (dist_200 * 1000)))
    vx_p = min(100, max(0, (vix_zscore + 2) * 25))
    br_p = (sum([1 for s in ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE'] if prices[s].iloc[-1] > prices[s].rolling(200).mean().iloc[-1]]) / 11) * 100
    
    avg = (tr_p + vx_p + br_p) / 3 # Simplified Aggregate
    
    return {
        "avg": avg, "action": action, "action_class": action_class, "news": news_events,
        "metrics": [
            ("Trend Alignment", f"{dist_200:+.2%}", tr_p),
            ("VIX Z-Score", f"{vix_zscore:.2f}", vx_p),
            ("Sector Breadth", f"Health: {br_p:.0f}%", br_p)
        ]
    }

# --- 5. DISPLAY ---
def main():
    st.write(f"## ALPHA TERMINAL v5.1 // {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    d = run_model()
    if d is None: return

    # TOP ROW: ALERTS AND NEWS
    col_news, col_strat = st.columns([1, 2])
    
    with col_news:
        st.write("### 🚨 ECONOMIC RADAR")
        for e in d['news']:
            urgent_style = "red-folder" if e['urgent'] else ""
            st.markdown(f"""
            <div class="news-card">
                <small style="color:#8b949e;">RED FOLDER EVENT</small><br>
                <span class="{urgent_style}">{e['event']}</span><br>
                <span style="font-size:1.2em;">T-MINUS: {e['countdown']}</span>
            </div>
            """, unsafe_allow_html=True)

    with col_strat:
        st.write("### ⚔️ STRATEGIC OVERRIDE")
        st.markdown(f"""
        <div class="metric-container" style="text-align:center;">
            <p style="color:#8b949e; margin-bottom:15px;">CURRENT TACTICAL BIAS</p>
            <div class="action-card {d['action_class']}">{d['action']}</div>
            <p style="margin-top:15px; font-size:0.9em;">
                Agg Strength: {d['avg']:.1f}% | 
                Risk Level: {"HIGH" if "WAIT" in d['action'] else "STABLE"}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.write("---")
    
    # BOTTOM ROW: LEDGER & DICTIONARY
    col_ledge, col_dict = st.columns([1.5, 1])
    
    with col_ledge:
        st.write("### STRENGTH LEDGER")
        for label, reading, pct in d['metrics']:
            cl1, cl2, cl3 = st.columns([1, 1, 1.5])
            cl1.write(label); cl2.write(reading)
            color = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
            cl3.markdown(f'<div class="progress-bg"><div style="background-color:{color}; width:{pct}%; height:14px; border-radius:2px;"></div></div>', unsafe_allow_html=True)

    with col_dict:
        st.write("### 🧠 LOGIC ENGINE")
        st.markdown("""
        <div class="logic-box">
            <b>RED FOLDER PROTOCOL:</b><br>
            If high-impact news (CPI, FOMC, etc.) is within 4 hours, all signals are muted to 'WAIT' to prevent gamma-risk exposure.
        </div>
        <div class="logic-box">
            <b>SELL PREMIUM REQ:</b><br>
            1. SPY Distance to 200MA > -2%<br>
            2. HYG > 20-Day Moving Average<br>
            3. DXY < 20-Day Highs<br>
            4. VIX Spike > 8% & Z-Score > 1.5
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
