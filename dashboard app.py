import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME & FONT SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v4.0", layout="wide")

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

# --- 2. RESILIENT DATA ENGINE (Anti-Block) ---
@st.cache_data(ttl=600) # Caches for 10 mins
def fetch_market_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        # We download and then fix the columns immediately
        df = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        if df.empty: return None
        
        # This part handles the 'Multi-Index' column error that causes blank screens
        if 'Close' in df.columns:
            return df['Close']
        return df
    except:
        return None

def fetch_yc_fred():
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
        df = pd.read_csv(url)
        df.columns = ['date', 'value']
        df['value'] = pd.to_numeric(df['value'
