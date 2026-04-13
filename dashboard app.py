import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v5.2", layout="wide")

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

# --- 2. ECONOMIC NEWS ENGINE ---
def get_red_folder_events():
    now = datetime.now(pytz.timezone('US/Eastern'))
    # Simulated High-Impact Events (In production, replace with API feed)
    events = [
        {"event": "Core CPI Inflation", "date": (now + timedelta(hours=14)).replace(minute=30)},
        {"event": "FOMC Meeting Minutes", "date": (now + timedelta(hours=6)).replace(minute=0)},
        {"event": "Unemployment Claims", "date": (now + timedelta(hours=30)).replace(minute=30)}
    ]
    upcoming = []
    for e in events:
        diff = e['date'] - now
        if diff.total_seconds() > 0:
            h, r = divmod(int(diff.total_seconds()), 3600)
            m, _ = divmod(r, 60)
            e['countdown'] = f"{h}h {m}m"
            e['urgent'] = h < 4
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

def get_yc_analysis():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']; df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(); curr = float(df['value'].iloc[-1]); was_inv = (df['value'].tail(180) < 0).any()
        if curr > 0 and was_inv: s = 10
        elif curr < 0: s = 40 + (curr + 1.0) * 20 
        else: s = min(100, 60 + (curr * 50))
        return s, curr
    except: return 50, 0.0

# --- 4. ANALYTICS ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    vix = prices['^VIX'].dropna(); vix_px = float(vix.iloc[-1])
    hyg = prices['HYG'].dropna(); hyg_px = float(hyg.iloc[-1])
    dxy = prices['DX-Y.NYB'].dropna(); dxy_px = float(dxy.iloc[-1])

    # [A] YOUR SPECIFIC TACTICAL LOGIC
    spy_200ma = spy.rolling(200).mean().iloc[-1]
    dist_to_200 = (spy_px - spy_200ma) / spy_200ma
    downtrend = dist_to_200 <= -0.02
    neutral_trend = dist_to_200 > -0.02

    hyg_20ma = hyg.rolling(20).mean().iloc[-1]
    dxy_20_high = dxy.tail(20).max()
    env_ok = (neutral_trend and hyg_px >= hyg_20ma and dxy_px < dxy_20_high)

    vix_prev = vix.shift(1).iloc[-1]
    vix_change = (vix_px - vix_prev) / vix_prev
    vix_20ma = vix.rolling(20).mean().iloc[-1]
    vix_20std = vix.rolling(20).std().iloc[-1]
    vix_zscore = (vix_px - vix_20ma) / vix_20std
    good_spike = (vix_change > 0.08 and vix_zscore > 1.5)

    if downtrend: action, a_class = "NO TRADE", "status-no-trade"
    elif env_ok and good_spike: action, a_class = "SELL PREMIUM", "status-sell-premium"
    else: action, a_class = "WAIT", "status-wait"

    # [B] FULL SYSTEM METRICS
    tr_p = min(100, max(0, 50 + (dist_to_200 * 1000)))
    
    ratio = (prices['HYG'] / prices['IEF']).dropna()
    cr_p = min(100, max(0, 50 + ((ratio.iloc[-1] / ratio.rolling(50).mean().iloc[-1]) - 1) * 2000))
    
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = sum([1 for s in secs if prices[s].iloc[-1] > prices[s].rolling(200).mean().iloc[-1]])
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

    yc_p, yc_v = get_yc_analysis()
    
    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p + rsi_p) / 7
    alloc = 100 if avg >= 80 else (75 if avg >= 60 else (50 if avg >= 40 else 20))

    return {
        "alloc": alloc, "avg": avg, "action": action, "a_class": a_class, "yc_v": yc_v, "rsi": rsi_val, "c": c,
        "news": get_red_folder_events(),
        "metrics": [
            ("Macro: Yield Curve", f"{yc_v:.2f}% Spread", yc_p),
            ("Trend: 200MA Prox", f"{dist_to_200:+.2%}", tr_p),
            ("Credit: Risk Ratio", "HYG/IEF Strength", cr_p),
            ("Breadth: Sectors", f"{above}/11 Bullish", br_p),
            ("Tactical: VIX Z-Score", f"Z: {vix_zscore:.2f}", vx_p),
            ("Tactical: RSI-14", f"Value: {rsi_val:.1f}", rsi_p),
            ("Tactical: Exhaust", f"Step {c}/9", dm_p)
        ]
    }

# --- 5. DISPLAY ---
def main():
    st.write(f"## ALPHA TERMINAL v5.2 // {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    d = run_model()
    if d is None: return

    # TOP ROW: NEWS, ACTION, AND STRENGTH
    c_news, c_action, c_gauge = st.columns([1, 1.2, 1])
    
    with c_news:
        st.write("### 🚨 RED FOLDER NEWS")
        if not d['news']: st.write("No major news imminent.")
        for e in d['news']:
            urgent_cls = "red-folder" if e['urgent'] else ""
            st.markdown(f"""<div class="news-card"><small>HIGH IMPACT</small><br><span class="{urgent_cls}">{e['event']}</span><br>T-MINUS: {e['countdown']}</div>""", unsafe_allow_html=True)

    with c_action:
        st.write("### ⚔️ STRATEGIC DECISION")
        st.markdown(f"""<div class="metric-container" style="text-align:center;"><p style="color:#8b949e; margin-bottom:15px;">TACTICAL BIAS</p><div class="action-card {d['a_class']}">{d['action']}</div><p style="margin-top:15px;">ALLOCATION: {d['alloc']}%</p></div>""", unsafe_allow_html=True)

    with c_gauge:
        st.write("### 📊 AGGREGATE STRENGTH")
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#161b22"}))
        fig.update_layout(height=180, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    st.write("### STRENGTH LEDGER")
    for label, reading, pct in d['metrics']:
        col1, col2, col3 = st.columns([1, 1, 2])
        col1.write(f"**{label}**"); col2.write(reading)
        color = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
        col3.markdown(f'<div class="progress-bg"><div style="background-color:{color}; width:{pct}%; height:14px; border-radius:2px;"></div></div>', unsafe_allow_html=True)

    st.write("---")
    st.write("### 🧠 SIGNAL INTELLIGENCE DICTIONARY")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown(f"""
        <div class="logic-box"><b>1. Ta
