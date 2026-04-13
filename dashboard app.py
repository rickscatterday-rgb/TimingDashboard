import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v3.6", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    .metric-row { border-bottom: 1px solid #30363d; padding: 20px 0; }
    .label { color: #8b949e; font-size: 0.75rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }
    .strength-text { font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. OPTIMIZED DATA ENGINE ---
@st.cache_data(ttl=1800)
def fetch_alpha_data():
    tickers = ['SPY', '^VIX', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        data = yf.download(tickers, period="400d", interval="1d", progress=False, auto_adjust=True)
        return data['Close'] if not data.empty else None
    except: return None

def get_yc_data():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']; df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(); curr = float(df.iloc[-1]['value']); was_inv = (df.tail(180)['value'] < 0).any()
        # Strength: 0% = Trap, 50% = Inverted, 100% = Healthy
        strength = 0 if (curr > 0 and was_inv) else (50 if curr < 0 else 100)
        return strength, curr, was_inv
    except: return 50, 0.0, False

# --- 3. THE SCORING LEDGER ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    # [1] TREND STRENGTH
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1]); spy_ma = float(spy.rolling(200).mean().iloc[-1])
    trend_pct = 100 if spy_px > spy_ma else 0
    
    # [2] BREADTH STRENGTH
    sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in sectors:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
    # Washout (0-2) = 100% Buy Strength, Overbought (9-11) = 0% Strength
    breadth_pct = 100 if above <= 2 else (0 if above >= 9 else 60)
    
    # [3] VIX STRENGTH (Snapback)
    vix = prices['^VIX'].dropna(); vx_pct = 50 # Neutral
    if len(vix) > 21:
        v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_u = v_ma + (2 * v_std); v_n = float(vix.iloc[-1]); v_p = float(vix.iloc[-2])
        if v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1]): vx_pct = 100 # Snapback Buy
        elif v_n < 13: vx_pct = 0 # Complacency Sell
    
    # [4] EXHAUSTION STRENGTH (DeMark)
    dm = (spy > spy.shift(4)).astype(int); last = dm.iloc[-1]; c = 0
    for val in reversed(dm.tolist()):
        if val == last: c += 1
        else: break
    dm_pct = 100 if (c >= 8 and last == 0) else (0 if (c >= 8 and last == 1) else 50)
    
    # [5] YIELD CURVE STRENGTH
    yc_pct, yc_v, yc_w = get_yc_data()
    
    avg_strength = (trend_pct + breadth_pct + vx_pct + dm_pct + yc_pct) / 5
    alloc = 100 if avg_strength >= 85 else (75 if avg_strength >=
