import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME: INSTITUTIONAL DARK TERMINAL ---
st.set_page_config(page_title="ALPHA TERMINAL", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { 
        border: 1px solid #30363d !important; 
        background-color: #0d1117 !important; 
        border-radius: 0px !important; 
        padding: 20px !important; 
    }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    h1, h2, h3, p, span { font-family: 'Roboto Mono', monospace !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            if isinstance(df.columns, pd.MultiIndex):
                return df['Close'].iloc[:, 0]
            return df['Close']
        except: 
            return pd.Series()

    def get_yc(self):
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
            df = pd.read_csv(url)
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            curr = float(df.iloc[-1]['value'])
            # Recession Watch: 180 day lookback for inversion
            was_inv = (df.tail(180)['value'] < 0).any()
            score = 1 if (curr > 0 and was_inv) else (5 if curr < 0 else 10)
            return score, curr, was_inv
        except: 
            return 5, 0.0, False

    def run_model(self):
        # [A] Macro
        yc_s, yc_v, yc_w = self.get_yc()
        spy = self.get_px('SPY', 350)
        s_px = float(spy.iloc[-1]) if not spy.empty else 0.0
        s
