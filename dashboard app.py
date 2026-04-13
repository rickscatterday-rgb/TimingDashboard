import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v3.4", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { border: 1px solid #30363d !important; background-color: #0d1117 !important; border-radius: 0px !important; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    h1, h2, h3, p, span { font-family: 'Roboto Mono', monospace !important; font-weight: 700 !important; }
    .info-text { color: #8b949e; font-size: 0.8rem; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# --- 2. OPTIMIZED DATA ENGINE ---
@st.cache_data(ttl=3600) # Caches data for 1 hour to prevent API blocks
def fetch_all_market_data():
    tickers = ['SPY', '^VIX', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        # One single request for all data
        data = yf.download(tickers, period="400d", interval="1d", progress=False, auto_adjust=True)
        if data.empty: return None
        return data['Close']
    except:
        return None

def get_yc_data():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna()
        curr = float(df.iloc[-1]['value'])
        was_inv = (df.tail(180)['value'] < 0).any()
        score = 1 if (curr > 0 and was_inv) else (5 if curr < 0 else 10)
        return score, curr, was_inv
    except:
        return 5, 0.0, False

# --- 3. LOGIC CALCULATIONS ---
def run_model():
    prices = fetch_all_market_data()
    if prices is None: return None
    
    # Macro: Global Trend (SPY vs 200MA)
    spy = prices['SPY'].dropna()
    spy_px = float(spy.iloc[-1])
    spy_ma = float(spy.rolling(200).mean().iloc[-1])
    tr_s = 10 if spy_px > spy_ma else 1
    
    # Intermediate: Broad Breadth (11 Sectors)
    sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above_count = 0
    for s in sectors:
        s_px = prices[s].dropna()
        if not s_px.empty and s_px.iloc[-1] > s_px.rolling(200).mean().iloc[-1]:
            above_count += 1
    br_s = 10 if above_count <= 2 else (3 if above_count >= 9 else 7)
    
    # Tactical: VIX Snapback
    vix = prices['^VIX'].dropna()
    vx_s = 5
    if len(vix) > 21:
        v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_u = v_ma + (2 * v_std); v_n = float(vix.iloc[-1]); v_p = float(vix.iloc[-2])
        vx_s = 10 if (v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1])) else (2 if v_n < 13 else 6)

    # Tactical: DeMark Exhaustion
    dm = (spy > spy.shift(4)).astype(int)
    l_v = dm.iloc[-1]; cnt = 0
    for val in reversed(dm.tolist()):
        if val == l_v: cnt += 1
        else: break
    dm_s = 10 if (cnt >= 8 and l_v == 0) else (1 if (cnt >= 8 and l_v == 1) else 5)
    
    # Macro: Yield Curve
    yc_s, yc_v, yc_w = get_yc_data()
    
    # Final Score & Allocation
    avg = (yc_s + tr_s + br_s + vx_s + dm_s) / 5
    alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (20 if avg >= 4 else 0)))
    
    return {
        "alloc": alloc, "avg": avg, "spy": spy_px, 
        "yc_v": yc_v, "yc_w": yc_w, "br_c": above_count, 
        "vx_s": vx_s, "dm_c": cnt, "dm_s": dm_s, "tr_s": tr_s
    }

# --- 4. TERMINAL UI ---
def main():
    st.write("### ALPHA TERMINAL v3.4 // RISK OVERSIGHT")
    
    data = run_model()
    
    if data is None:
        st.error("SYSTEM TIMEOUT: Yahoo Finance is not responding. Please refresh the page in 10 seconds.")
        return

    # TOP ROW
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.metric("TARGET CAPITAL ALLOCATION", f"{data['alloc']}%")
        mode = "OFFENSIVE" if data['alloc'] >= 70 else "NEUTRAL" if data['alloc'] >= 40 else "DEFENSIVE"
        st.write(f"SYSTEM STATUS: **{mode}**")
        
    with col2:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = data['avg'],
            gauge = {'axis': {'range': [1, 10], 'tickcolor': "#8b949e"},
                     'bar': {'color': "#58a6ff"}, 'bgcolor': "#0d1117",
                     'steps': [{'range': [1, 4], 'color': "#3e1c1c"}, {'range': [7, 10], 'color': "#1c3e24"}]}))
        fig.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    # METRICS GRID
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("RECESSION WATCH", f"{data['yc_v']:.2f}%", delta="TRAP ACTIVE" if data['yc_w'] and data['yc_v'] > 0 else None, delta_color="inverse")
    m2.metric("SECTOR BREADTH", f"{data['br_c']}/11", help="Number of S&P sectors above 200MA")
    m3.metric("TACTICAL FATIGUE", f"{data['dm_c']} of 9", help="DeMark sequential trend count")

    # INTELLIGENCE LEDGER
    st.markdown("---")
    st.write("**INTELLIGENCE LEDGER (METHODOLOGY)**")
    l, r = st.columns(2)
    with l:
        st.markdown('<p class="info-text"><b>[01] YIELD CURVE:</b> Checks 10Y-2Y. Flagged if inverted in last 6 months but positive now (The Trap).</p>', unsafe_allow_html=True)
        st.markdown('<p class="info-text"><b>[02] SECTOR BREADTH:</b> Scans all 11 S&P sectors. Participation < 2 sectors is a Washout Buy; High > 9 is a Sell warning.</p>', unsafe_allow_html=True)
    with r:
        st.markdown('<p class="info-text"><b>[03] VIX SNAPBACK:</b> Tactical trigger. Active when VIX reverses inside its 2-STD bands.</p>', unsafe_allow_html=True)
        st.markdown('<p class="info-text"><b>[04] GLOBAL TREND:</b> Structural filter. SPY vs 200-day SMA.</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
