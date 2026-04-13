import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- INSTITUTIONAL TERMINAL CONFIG ---
st.set_page_config(page_title="ALPHA TERMINAL", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    .main { background-color: #0d1117; color: #c9d1d9; }
    font-family: 'Inter', sans-serif;

    /* Card Styling */
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 20px;
        margin-bottom: 15px;
    }
    
    .header-label { color: #8b949e; font-size: 0.7rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px;}
    .allocation-value { font-size: 3.5rem; font-weight: 800; color: #58a6ff; line-height: 1; }
    
    /* Exposure Box */
    .exposure-box {
        border: 1px solid #30363d;
        border-left: 4px solid #58a6ff;
        background: #0d1117;
        padding: 25px;
        border-radius: 6px;
    }

    /* Sector Grid */
    .sector-tag { font-size: 0.65rem; color: #8b949e; border: 1px solid #30363d; padding: 2px 6px; border-radius: 3px; margin-right: 4px; }
    </style>
    """, unsafe_allow_html=True)

class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            return df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        except: return pd.Series()

    def get_yc_analysis(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            curr = float(df.iloc[-1]['value'])
            # Recession Watch (Lag check): Was it inverted in the last 180 days?
            lookback = df.tail(180)
            was_inverted = (lookback['value'] < 0).any()
            
            # 1=Trap, 5=Inverted, 10=Normal
            score = 1 if (curr > 0 and was_inverted) else (5 if curr < 0 else 10)
            return score, curr, was_inverted
        except: return 5, 0, False

    def run_model(self):
        scores = {}
        
        # 1. MACRO: Yield Curve
        yc_s, yc_curr, yc_warn = self.get_yc_analysis()
        scores['Macro: Yield Curve'] = yc_s
        
        # 2. MACRO: Trend (SPY 200MA)
        spy = self.get_px('SPY', 350)
        ma200 = spy.rolling(200).mean()
        spy_c = float(spy.iloc[-1])
        scores['Macro: Global Trend'] = 10 if spy_c > float(ma200.iloc[-1]) else 1
        
        # 3. INTERMEDIATE: Whole-Market Breadth (11 Sectors)
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above_200 = 0
        for s in sectors:
            px = self.get_px(s, 250)
            if not px.empty and px.iloc[-1] > px.rolling(200).mean().iloc[-1]: above_200 += 1
        b_score = (above_200 / len(sectors)) * 10
        # Scoring: Washout (0-2 sectors) = 10, Mid = 7, Overbought (9+) = 3
        scores['Intermediate: Breadth'] = 10 if b_score <= 2 else (3 if b_score >= 8 else 7)
        
        # 4. TACTICAL: VIX Snapback
        vix = self.get_px('^VIX', 50); v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_upper = v_ma + (2 * v_std); v_now = float(vix.iloc[-1]); v_prev = float(vix.iloc[-2])
        if v_prev > float(v_upper.iloc[-2]) and v_now < float(v_upper.iloc[-1]): scores['Tactical: Volatility'] = 10
        elif v_now < float(v_ma.iloc[-1] - (2*v_std.iloc[-1])): scores['Tactical: Volatility'] = 2
        else: scores['Tactical: Volatility'] = 5

        # 5. TACTICAL: Exhaustion
        dm = (spy > spy.shift(4)).astype(int); last_v = dm.iloc[-1]; c = 0
        for val in reversed(dm.tolist()):
            if val == last_v: c += 1
            else: break
        scores['Tactical: Exhaustion'] = 10 if (c >= 8 and last_v == 0) else (1 if (c >= 8 and last_v == 1) else 5)

        avg = sum(scores.values()) / len(scores)
        # Allocation Scale
        alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (25 if avg >= 4 else 0)))

        return scores, avg, alloc, spy_c, yc_curr, yc_warn

# --- UI ---
def main():
    engine = AlphaEngine()
    with st.spinner('Synchronizing Terminal...'):
        scores, avg, alloc, spy_px, yc_val, yc_warn = engine.run_model()

    st.markdown("<p style='color: #8b949e; font-size: 0.8rem; font-weight: 700; letter-spacing: 1px;'>SYSTEMS OVERSIGHT // ALPHA TERMINAL v2.5</p>", unsafe_allow_html=True)
    
    # --- TOP ROW ---
    c_top1, c_top2 = st.columns([1, 2])
    
    with c_top1:
        st.markdown(f"""
            <div class="exposure-box">
                <p class="header-label">TARGET CAPITAL EXPOSURE</p>
                <div class="allocation-value">{alloc}%</div>
                <p style="margin-top: 15px; color: {'#39d353' if alloc >= 75 else '#f85149' if alloc <= 25 else '#e3b341'}; font-weight: 700; font-size: 0.8rem;">
                    { 'CONDITION: UNRESTRICTED BUY' if alloc >= 75 else 'CONDITION: CAPITAL PRESERVATION' if alloc <= 25 else 'CONDITION: TACTICAL NEUTRAL' }
                </p>
            </div>
        """, unsafe_allow_html=True)

    with c_top2:
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
        fig.update_layout(height=260, margin=dict(l=20, r=20, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr style='border-top: 1px solid #30363d; margin: 25px 0;'>", unsafe_allow_html=True)
    
    # --- SECTION I: MACRO ---
    st.markdown("<p class='header-label'>Section I: Macro Regime & Systemic Risk</p>", unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    
    with m1:
        st.markdown(f"""
            <div class="card">
                <p class="header-label">YIELD CURVE RECESSION WATCH</p>
                <h2 style="margin:0; color: #c9d1d9;">{yc_val:.2f}%</h2>
                <p style="color: {'#f85149' if yc_warn else '#39d353'}; font-size: 0.75rem; font-weight: 600; margin-top:5px;">
                    {'⚠️ HIGH RISK: POST-INVERSION RE-STEEPENING' if yc_warn and yc_val > 0 else 'STABLE EXPANSION' if yc_val > 0 else 'INVERTED: SYSTEMIC STRESS'}
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with m2:
        st.markdown(f"""
            <div class="card">
                <p class="header-label">GLOBAL EQUITY TREND (SPY 200MA)</p>
                <h2 style="margin:0; color: #c9d1d9;">${spy_px:.2f}</h2>
                <p style="color: #8b949e; font-size: 0.75rem; margin-top:5px;">Structural trend bias is currently {'BULLISH' if scores['Macro: Global Trend'] == 10 else 'BEARISH'}</p>
            </div>
        """, unsafe_allow_html=True)

    # --- SECTION II: TACTICAL ---
    st.markdown("<p class='header-label'>Section II: Tactical Timing & Execution</p>", unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    
    tactical_data = [
        ("Whole Market Breadth", "Intermediate: Breadth", "Participation of 11 S&P sectors."),
        ("Volatility (VIX)", "Tactical: Volatility", "Panic-reversal snapback logic."),
        ("Exhaustion", "Tactical: Exhaustion", "DeMark sequential reversal count.")
    ]
    
    for i, (label, key, desc) in enumerate(tactical_data):
        with [t1, t2, t3][i]:
            val = scores[key]
            color = "#39d353" if val >= 7 else "#f85149" if val <= 3 else "#e3b341"
            st.markdown(f"""
                <div class="card">
                    <p class="header-label">{label}</p>
                    <h1 style="margin:0; color: {color};">{val}<span style="font-size: 1rem; color: #8b949e;">/10</span></h1>
                    <p style="color: #6e7681; font-size: 0.7rem; margin-top: 10px;">{desc}</p>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
