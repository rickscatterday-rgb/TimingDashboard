import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- INSTITUTIONAL THEME CONFIG ---
st.set_page_config(page_title="ALPHA TERMINAL | Institutional Dashboard", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    /* Dark Terminal Theme */
    .main { background-color: #0e1117; color: #ffffff; }
    font-family: 'Inter', sans-serif;

    /* Glassmorphism Cards */
    .stMetric { background: #1a1c24; border: 1px solid #2d2f39; padding: 20px; border-radius: 10px; }
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 20px;
    }
    
    .macro-header { color: #8b949e; font-size: 0.8rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 15px;}
    .allocation-value { font-size: 4rem; font-weight: 800; color: #58a6ff; line-height: 1; }
    .score-badge { padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; }
    
    /* Allocation Glow */
    .glow-box {
        border: 1px solid #30363d;
        border-left: 4px solid #58a6ff;
        background: #0d1117;
        padding: 30px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            return df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        except: return pd.Series()

    def get_yc_analysis(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            
            curr = float(df.iloc[-1]['value'])
            # Recession Watch: Was it inverted in the last 180 days?
            lookback = df.tail(180)
            was_inverted = (lookback['value'] < 0).any()
            
            # SCORING: 1 (Danger/Lag), 5 (Inverted), 10 (Healthy)
            if curr > 0 and was_inverted: score = 1 # The Trap
            elif curr < 0: score = 5 # Inversion
            else: score = 10 # Healthy
            
            return score, curr, was_inverted
        except: return 5, 0, False

    def run_alpha_model(self):
        scores = {}
        
        # 1. MACO: Yield Curve (With Recession Watch Lag)
        yc_score, yc_curr, yc_warn = self.get_yc_analysis()
        scores['Macro: Yield Curve'] = yc_score
        
        # 2. MACRO: Primary Trend (SPY 200MA)
        spy = self.get_px('SPY', 350); spy_ma = spy.rolling(200).mean()
        spy_curr = float(spy.iloc[-1])
        scores['Macro: Global Trend'] = 10 if spy_curr > float(spy_ma.iloc[-1]) else 1
        
        # 3. INTERMEDIATE: Broad Breadth (11 Sectors)
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above_200 = 0
        for s in sectors:
            px = self.get_px(s, 250)
            if not px.empty and px.iloc[-1] > px.rolling(200).mean().iloc[-1]: above_200 += 1
        breadth_score = (above_200 / len(sectors)) * 10
        # Counter-cyclical scoring
        if breadth_score <= 2: scores['Intermediate: Breadth'] = 10 # Washout
        elif breadth_score >= 8: scores['Intermediate: Breadth'] = 3 # Overbought Warning
        else: scores['Intermediate: Breadth'] = 7
        
        # 4. TACTICAL: Volatility (VIX Snapback)
        vix = self.get_px('^VIX', 50); v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_upper = v_ma + (2 * v_std); v_now = float(vix.iloc[-1]); v_prev = float(vix.iloc[-2])
        if v_prev > float(v_upper.iloc[-2]) and v_now < float(v_upper.iloc[-1]): scores['Tactical: Volatility'] = 10
        elif v_now < float(v_ma.iloc[-1] - (2*v_std.iloc[-1])): scores['Tactical: Volatility'] = 2
        else: scores['Tactical: Volatility'] = 5

        # 5. TACTICAL: Exhaustion (DeMark SPY)
        dm = (spy > spy.shift(4)).astype(int); last_v = dm.iloc[-1]; c = 0
        for val in reversed(dm.tolist()):
            if val == last_v: c += 1
            else: break
        if c >= 8 and last_v == 0: scores['Tactical: Exhaustion'] = 10
        elif c >= 8 and last_v == 1: scores['Tactical: Exhaustion'] = 1
        else: scores['Tactical: Exhaustion'] = 5

        # FINAL ALLOCATION
        avg = sum(scores.values()) / len(scores)
        if avg >= 8.5: alloc = 100
        elif avg >= 7: alloc = 75
        elif avg >= 5.5: alloc = 50
        elif avg >= 4: alloc = 25
        else: alloc = 0

        return scores, avg, alloc, spy_curr, yc_curr, yc_warn

# --- UI EXECUTION ---
def main():
    engine = AlphaEngine()
    with st.spinner('Accessing Alpha Terminal...'):
        scores, avg, alloc, spy_px, yc_val, yc_warn = engine.run_alpha_model()

    # --- TOP LEVEL HEADER ---
    st.markdown("<h1 style='text-align: left; font-size: 1.2rem; color: #8b949e; margin-bottom: 20px;'>PORTFOLIO STRATEGY & RISK OVERSIGHT</h1>", unsafe_allow_html=True)
    
    col_main_1, col_main_2 = st.columns([1, 2])
    
    with col_main_1:
        st.markdown(f"""
            <div class="glow-box">
                <p class="macro-header">Target Exposure</p>
                <div class="allocation-value">{alloc}%</div>
                <p style="margin-top: 15px; color: {'#39d353' if alloc >= 75 else '#f85149' if alloc <= 25 else '#e3b341'}; font-weight: 700;">
                    { 'RISK-ON: AGGRESSIVE' if alloc >= 75 else 'RISK-OFF: CAPITAL PRESERVATION' if alloc <= 25 else 'NEUTRAL: TACTICAL HEDGING' }
                </p>
            </div>
        """, unsafe_allow_html=True)

    with col_main_2:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = avg,
            gauge = {
                'axis': {'range': [1, 10], 'tickcolor': "#30363d"},
                'bar': {'color': "#58a6ff"},
                'bgcolor': "#161b22",
                'steps': [
                    {'range': [1, 4], 'color': "#3e1c1c"},
                    {'range': [4, 7], 'color': "#3e3a1c"},
                    {'range': [7, 10], 'color': "#1c3e24"}
                ],
            }
        ))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    # --- THE CORE TERMINAL ---
    st.divider()
    
    # 1. MACO REGIME SECTION
    st.markdown("<p class="macro-header">Section I: Macro Regime & Systemic Risk</p>", unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    
    with m1:
        st.markdown(f"""
            <div class="card">
                <p style="color: #8b949e; font-size: 0.7rem;">YIELD CURVE RECESSION WATCH</p>
                <h3 style="margin:0;">{yc_val:.2f}%</h3>
                <p style="color: {'#f85149' if yc_warn else '#39d353'}; font-size: 0.8rem;">
                    {'⚠️ WARNING: POST-INVERSION STEEPENING' if yc_warn and yc_val > 0 else 'STABLE' if yc_val > 0 else 'INVERTED: ECONOMIC STRESS'}
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with m2:
        st.markdown(f"""
            <div class="card">
                <p style="color: #8b949e; font-size: 0.7rem;">GLOBAL EQUITY TREND (SPY 200MA)</p>
                <h3 style="margin:0;">${spy_px:.2f}</h3>
                <p style="color: #8b949e; font-size: 0.8rem;">Long-term structural bias is {'BULLISH' if scores['Macro: Global Trend'] == 10 else 'BEARISH'}</p>
            </div>
        """, unsafe_allow_html=True)

    # 2. TACTICAL SECTION
    st.markdown("<p class="macro-header">Section II: Tactical Timing & Execution</p>", unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    
    tactical_items = [
        ("Market Breadth", "Intermediate: Breadth", "Whole-market sector participation."),
        ("Volatility (VIX)", "Tactical: Volatility", "Panic-reversal snapback logic."),
        ("Exhaustion", "Tactical: Exhaustion", "DeMark sequential reversal count.")
    ]
    
    for i, (label, key, desc) in enumerate(tactical_items):
        with [t1, t2, t3][i]:
            val = scores[key]
            color = "#39d353" if val >= 7 else "#f85149" if val <= 3 else "#e3b341"
            st.markdown(f"""
                <div class="card">
                    <p style="color: #8b949e; font-size: 0.7rem;">{label.upper()}</p>
                    <h2 style="margin:0; color: {color};">{val}/10</h2>
                    <p style="color: #6e7681; font-size: 0.75rem; margin-top: 10px;">{desc}</p>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
