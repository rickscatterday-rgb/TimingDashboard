import os
import yfinance as yf
import pandas as pd
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =============================================================================
# 1. DATA ENGINE
# =============================================================================
class ScorecardEngine:
    def get_px(self, ticker, days=350):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            return df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        except: return pd.Series()

    def get_yc_raw(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.dropna()
        except: return pd.DataFrame()

# =============================================================================
# 2. INDIVIDUAL SCORING CALCULATIONS (1-10)
# =============================================================================
    def calculate_scores(self):
        scores = {}
        
        # --- 1. YIELD CURVE SCORE ---
        yc = self.get_yc_raw()
        curr_yc = float(yc.iloc[-1]['value'])
        was_neg = (yc.tail(252)['value'] < 0).any()
        # Trap (Positive now but was negative) = 1, Healthy = 10, Inverted = 5
        if curr_yc > 0 and was_neg: scores['Yield Curve'] = 1
        elif curr_yc < 0: scores['Yield Curve'] = 5
        else: scores['Yield Curve'] = 10

        # --- 2. CREDIT CANARY (HYG/IEF) ---
        hyg = self.get_px('HYG', 150)
        ief = self.get_px('IEF', 150)
        ratio = hyg / ief
        ma50 = ratio.rolling(50).mean()
        # Above MA = 10, Below = 1
        scores['Credit Canary'] = 10 if float(ratio.iloc[-1]) > float(ma50.iloc[-1]) else 1

        # --- 3. TREND (SPY vs 200MA) ---
        spy = self.get_px('SPY', 350)
        ma200 = spy.rolling(200).mean()
        # Above = 10, Below = 1
        scores['Market Trend'] = 10 if float(spy.iloc[-1]) > float(ma200.iloc[-1]) else 1

        # --- 4. VIX SNAPBACK ---
        vix = self.get_px('^VIX', 50)
        v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        upper = v_ma + (2 * v_std); lower = v_ma - (2 * v_std)
        # Snapback = 10, Touching lower (complacency) = 2, Neutral = 5
        if (float(vix.iloc[-2]) > float(upper.iloc[-2])) and (float(vix.iloc[-1]) < float(upper.iloc[-1])):
            scores['VIX Signal'] = 10
        elif float(vix.iloc[-1]) < float(lower.iloc[-1]):
            scores['VIX Signal'] = 2
        else:
            scores['VIX Signal'] = 5

        # --- 5. BREADTH (% Above 50MA) ---
        leaders = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM', 'V', 'LLY']
        above = 0
        for t in leaders:
            p = self.get_px(t, 60)
            if not p.empty and p.iloc[-1] > p.rolling(50).mean().iloc[-1]: above += 1
        breadth = (above / len(leaders)) * 10
        # Washout (<20%) is actually a 10 (Buy), Overbought (>80%) is a 2 (Sell)
        if breadth <= 2: scores['Breadth'] = 10
        elif breadth >= 8: scores['Breadth'] = 2
        else: scores['Breadth'] = 6

        # --- 6. DEMARK COUNT (SPY) ---
        counts = (spy > spy.shift(4)).astype(int)
        last_val = counts.iloc[-1]; c = 0
        for val in reversed(counts.tolist()):
            if val == last_val: c += 1
            else: break
        # Downside 9 = 10, Upside 9 = 1, Else 5
        if c >= 9 and last_val == 0: scores['DeMark'] = 10
        elif c >= 9 and last_val == 1: scores['DeMark'] = 1
        else: scores['DeMark'] = 5

        return scores, float(spy.iloc[-1]), curr_yc

# =============================================================================
# 3. DASHBOARD UI
# =============================================================================
def main():
    st.set_page_config(page_title="Market Scorecard", layout="wide")
    st.title("⚖️ Market Timing Scorecard")
    
    engine = ScorecardEngine()
    with st.spinner('Calculating Individual Rankings...'):
        scores, spy_price, yc_val = engine.calculate_scores()

    # Calculate Total Score
    total_avg = sum(scores.values()) / len(scores)

    # --- TOP SECTION: THE SUMMARY ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"Total Market Score: {total_avg:.1f} / 10")
        color = "green" if total_avg >= 7 else "orange" if total_avg >= 4 else "red"
        st.markdown(f"<div style='height:30px; width:100%; background-color:#e0e0e0; border-radius:10px;'><div style='height:30px; width:{total_avg*10}%; background-color:{color}; border-radius:10px;'></div></div>", unsafe_allow_html=True)
    
    with col2:
        if total_avg >= 7: st.success("STRATEGY: OFFENSIVE")
        elif total_avg >= 4: st.warning("STRATEGY: NEUTRAL")
        else: st.error("STRATEGY: DEFENSIVE")

    st.divider()

    # --- BOTTOM SECTION: THE INDIVIDUAL RANKINGS ---
    st.write("### Individual Indicator Rankings (1=Sell, 10=Buy)")
    
    # Create 3 columns for the 6 indicators
    c1, c2, c3 = st.columns(3)
    
    items = list(scores.items())
    for i, (name, val) in enumerate(items):
        target_col = [c1, c2, c3][i % 3]
        with target_col:
            st.metric(name, f"{val}/10")
            # Small visual bar for each
            bar_color = "#2ecc71" if val >= 7 else "#e67e22" if val >= 4 else "#e74c3c"
            st.markdown(f"<div style='height:8px; width:100%; background-color:#eee;'><div style='height:8px; width:{val*10}%; background-color:{bar_color};'></div></div>", unsafe_allow_html=True)
            st.write("") # Spacing

    st.divider()
    st.info(f"Market Snapshot: SPY at ${spy_price:.2f} | 10Y-2Y Spread: {yc_val:.2f}%")

if __name__ == "__main__":
    main()
