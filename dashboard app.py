import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v3.9", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    .metric-row { border-bottom: 1px solid #30363d; padding: 15px 0; }
    .label { color: #8b949e; font-size: 0.75rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }
    .strength-text { font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=1800)
def fetch_alpha_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        data = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        return data['Close'] if not data.empty else None
    except: return None

def get_yc_data():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']; df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(); curr = float(df.iloc[-1]['value']); was_inv = (df.tail(180)['value'] < 0).any()
        # Strength: 0% = Re-steepening Trap, 50% = Inverted, 100% = Healthy
        strength = 0 if (curr > 0 and was_inv) else (50 if curr < 0 else 100)
        return strength, curr, was_inv
    except: return 50, 0.0, False

# --- 3. LOGIC ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    # [1] TREND (SPY vs 200MA)
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    spy_ma = float(spy.rolling(200).mean().iloc[-1])
    tr_p = 100 if spy_px > spy_ma else 0
    
    # [2] CREDIT (HYG/IEF vs 50MA)
    hyg = prices['HYG'].dropna(); ief = prices['IEF'].dropna()
    ratio = hyg / ief; ma50 = ratio.rolling(50).mean()
    cr_p = 100 if float(ratio.iloc[-1]) > float(ma50.iloc[-1]) else 0
    
    # [3] BREADTH (11 Sectors vs 200MA) - UPDATED TO TREND STRENGTH LOGIC
    sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
