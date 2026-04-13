import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. TERMINAL UI CONFIGURATION ---
st.set_page_config(page_title="ALPHA TERMINAL v4.5", layout="wide", initial_sidebar_state="collapsed")

def apply_custom_style():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;500;700&display=swap');
        
        :root {
            --bg-color: #05070a;
            --card-bg: #0d1117;
            --text-main: #e6edf3;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --border-color: #30363d;
        }

        .stApp { background-color: var(--bg-color); color: var(--text-main); }
        .data-font { font-family: 'Fira Code', monospace !important; }
        
        /* Terminal Metric Cards */
        .metric-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        
        .status-pulse {
            display: inline-block;
            width: 10px; height: 10px;
            background-color: var(--accent-green);
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(63, 185, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(63, 185, 80, 0); }
        }

        h1, h2, h3 { font-family: 'Fira Code', monospace !important; text-transform: uppercase; letter-spacing: 2px; }
        .stExpander { border: 1px solid var(--border-color) !important; background: transparent !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_market_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        data = yf.download(tks, period="2y", interval="1d", progress=False, auto_adjust=True)
        return data['Close']
    except Exception as e:
        st.error(f"DATA_SYNC_ERROR: {e}")
        return None

def get_macro_spread():
    try:
        # T10Y2Y from FRED
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
        df = pd.read_csv(url)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna()
        curr = df['value'].iloc[-1]
        
        # Logic: Recession risk is highest when curve DE-INVERTS (crosses back above 0)
        was_inverted = (df['value'].tail(252) < 0).any()
        if curr > 0 and was_inverted: score = 20  # Danger zone: Re-steepening
        elif curr < 0: score = 50 + (abs(curr) * 10) # Early inversion is "calm"
        else: score = 90 # Healthy slope
        return min(100, score), curr
    except:
        return 50, 0.0

# --- 3. THE ANALYTICS ENGINE ---
def run_alpha_model():
    prices = fetch_market_data()
    if prices is None: return None
    
    spy = prices['SPY'].dropna()
    spy_last = spy.iloc[-1]
    
    # 1. TREND: Distance from 200DMA (Bullish > 0)
    ma200 = spy.rolling(200).mean().iloc[-1]
    dist_200 = (spy_last - ma200) / ma200
    tr_score = min(100, max(0, 50 + (dist_200 * 500)))

    # 2. CREDIT: Risk Appetite (HYG/IEF Ratio)
    credit_ratio = (prices['HYG'] / prices['IEF']).dropna()
    cr_ma = credit_ratio.rolling(50).mean().iloc[-1]
    cr_score = 100 if credit_ratio.iloc[-1] > cr_ma else 30

    # 3. BREADTH: % of Sectors > 200DMA
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above_count = 0
    for s in secs:
        s_px = prices[s].dropna()
        if s_px.iloc[-1] > s_px.rolling(200).mean().iloc[-1]: above_count += 1
    br_score = (above_count / 11) * 100

    # 4. VOLATILITY: VIX Mean Reversion
    vix = prices['^VIX'].dropna()
    v_curr = vix.iloc[-1]
    # Score 100 when VIX is high (Buying opportunity), 0 when VIX is crushed (Complacency)
    v_rank = (v_curr - vix.min()) / (vix.max() - vix.min())
    vx_score = v_rank * 100

    # 5. MOMENTUM: DeMark-ish Exhaustion
    dm = (spy > spy.shift(4)).astype(int)
    current_state = dm.iloc[-1]
    count = 0
    for val in reversed(dm.tolist()):
        if val == current_state: count += 1
        else: break
    # High count in uptrend = Exhaustion (Low Score)
    ex_score = 100 - (count * 10) if current_state == 1 else (count * 10)

    # 6. MACRO: Yield Curve
    yc_score, yc_val = get_macro_spread()

    # AGGREGATION
    weights = [0.25, 0.15, 0.20, 0.10, 0.10, 0.20]
    scores = [tr_score, cr_score, br_score, vx_score, ex_score, yc_score]
    final_avg = sum(s * w for s, w in zip(scores, weights))
    
    # Regime Classification
    if final_avg > 70: regime = "AGGRESSIVE EXPANSION"
    elif final_avg > 50: regime = "CAUTIOUS BULL"
    elif final_avg > 35: regime = "DEFENSIVE / HEDGED"
    else: regime = "CAPITAL PRESERVATION"

    return {
        "avg": final_avg, "regime": regime, "yc_v": yc_val, "br_c": above_count,
        "metrics": [
            ("Trend Alignment", tr_score, f"SPY vs 200MA: {dist_200:+.2%}"),
            ("Credit Signal", cr_score, "Junk/Treasury Ratio"),
            ("Market Breadth", br_score, f"{above_count}/11 Sectors Bullish"),
            ("Volatility Index", vx_score, f"VIX Spot: {v_curr:.2f}"),
            ("Trend Exhaustion", ex_score, f"{count}-Day Sequential {'High' if current_state==1 else 'Low'}"),
            ("Macro Spread", yc_score, f"10Y-2Y: {yc_val:.2f}%")
        ]
    }

# --- 4. DISPLAY INTERFACE ---
def main():
    apply_custom_style()
    
    # Header
    cols = st.columns([2, 1])
    with cols[0]:
        st.markdown(f"<h1><span class='status-pulse'></span>ALPHA TERMINAL v4.5</h1>", unsafe_allow_html=True)
        st.caption(f"SYSTEM STATUS: ONLINE // LAST SCAN: {datetime.now().strftime('%H:%M:%S')} // DATA: REALTIME_L1")
    
    data = run_alpha_model()
    if not data:
        st.warning("WAITING FOR DATA LINK...")
        return

    # Top Row Metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"<div class='metric-card'><small>SYSTEM AGGREGATE</small><h2>{data['avg']:.1f}%</h2></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='metric-card'><small>MARKET REGIME</small><h2>{data['regime']}</h2></div>", unsafe_allow_html=True)
    with m3:
        alloc = "100%" if data['avg'] > 75 else "75%" if data['avg'] > 60 else "25%" if data['avg'] > 40 else "CASH"
        st.markdown(f"<div class='metric-card'><small>SUGGESTED ALLOCATION</small><h2>{alloc}</h2></div>", unsafe_allow_html=True)

    # Main Visualization
    fig = go.Figure(go.Bar(
        x=[x[1] for x in data['metrics']],
        y=[x[0] for x in data['metrics']],
        orientation='h',
        marker=dict(color=['#58a6ff' if x[1] > 50 else '#f85149' for x in data['metrics']])
    ))
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e6edf3', family='Fira Code'),
        xaxis=dict(range=[0, 100], gridcolor='#30363d'),
        yaxis=dict(gridcolor='#30363d')
    )
    st.plotly_chart(fig, use_container_width=True)

    # Detailed Ledger
    st.markdown("### STRENGTH LEDGER")
    for label, score, detail in data['metrics']:
        c1, c2, c3 = st.columns([1, 2, 1])
        c1.markdown(f"<p class='data-font'>{label}</p>", unsafe_allow_html=True)
        
        # Custom Progress Bar
        color = "#3fb950" if score > 60 else "#f85149" if score < 40 else "#d29922"
        bar_html = f"""
        <div style="background-color: #30363d; width: 100%; height: 12px; margin-top: 5px; border-radius: 2px;">
            <div style="background-color: {color}; width: {score}%; height: 12px; border-radius: 2px;"></div>
        </div>
        """
        c2.markdown(bar_html, unsafe_allow_html=True)
        c3.markdown(f"<p class='data-font' style='text-align:right;'>{detail}</p>", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("DISCLAIMER: ALPHA TERMINAL provides algorithmic analysis based on linear price action. No financial advice intended.")

if __name__ == "__main__":
    main()
