import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =============================================================================
# 1. SETUP & RECIPIENTS
# =============================================================================
# Add your emails and phone-to-SMS addresses here
RECIPIENTS = [
    "your_email@gmail.com",
    "1234567890@vtext.com",  # Verizon example
    "0987654321@txt.att.net" # AT&T example
]

# =============================================================================
# 2. THE LOGIC (Your Original System)
# =============================================================================
class RegimeBasedDashboard:
    def __init__(self, capital=100000):
        self.capital = capital
        self.data = {}

    def get_data(self, tickers, days=365):
        # Using yfinance for reliability in the cloud
        return yf.download(tickers, period=f"{days}d", interval="1d")

    def get_fred_data(self, series_id):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        try:
            df = pd.read_csv(url)
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.dropna()
        except: return None

    def check_regime(self):
        # Dial 1: Yield Curve
        yc_df = self.get_fred_data('T10Y2Y')
        last_12mo = yc_df.tail(252)
        current_yc = yc_df.iloc[-1]['value']
        was_negative = (last_12mo['value'] < 0).any()
        yc_safe = not (current_yc > 0 and was_negative)

        # Dial 2: Credit (HYG/IEF)
        credit_data = self.get_data(['HYG', 'IEF'], days=150)['Close']
        ratio = credit_data['HYG'] / credit_data['IEF']
        ma50 = ratio.rolling(50).mean()
        credit_safe = ratio.iloc[-1] > ma50.iloc[-1]

        regime = "OFFENSIVE" if (yc_safe and credit_safe) else "DEFENSIVE"
        return {
            "regime": regime, 
            "yc_val": current_yc, 
            "yc_safe": yc_safe, 
            "credit_safe": credit_safe,
            "ratio": ratio.iloc[-1],
            "ma50": ma50.iloc[-1]
        }

    def get_signals(self):
        # VIX Snap-back
        vix = self.get_data('^VIX', days=50)['Close']
        ma = vix.rolling(20).mean()
        std = vix.rolling(20).std()
        upper = ma + (2 * std)
        vix_buy = (vix.iloc[-2] > upper.iloc[-2]) and (vix.iloc[-1] < upper.iloc[-1])
        
        # Simple Trend
        spy = self.get_data('SPY', days=300)['Close']
        ma200 = spy.rolling(200).mean()
        trend_up = spy.iloc[-1] > ma200.iloc[-1]

        return {"vix_buy": vix_buy, "trend_up": trend_up, "spy_price": spy.iloc[-1]}

# =============================================================================
# 3. THE ALERTING ENGINE
# =============================================================================
def send_alerts(message_body):
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_PASSWORD") 

    if not sender or not password:
        print("⚠️ Secret Credentials not found. Skipping alert.")
        return

    msg = MIMEText(message_body)
    msg['Subject'] = "Market Signal Alert"
    msg['From'] = sender

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, RECIPIENTS, msg.as_string())
        print("✅ Alert sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")

# =============================================================================
# 4. THE INTERFACE (Streamlit Dashboard)
# =============================================================================
def run_dashboard():
    st.title("🛡️ Market Timing Dashboard")
    engine = RegimeBasedDashboard()
    
    with st.spinner("Analyzing Markets..."):
        reg = engine.check_regime()
        sig = engine.get_signals()

    # Visual Display
    col1, col2 = st.columns(2)
    
    if reg['regime'] == "OFFENSIVE":
        col1.success(f"REGIME: {reg['regime']} 🟢")
    else:
        col1.error(f"REGIME: {reg['regime']} 🔴")

    col2.metric("Yield Curve", f"{reg['yc_val']:.2f}%", "Safe" if reg['yc_safe'] else "Trap")
    
    st.divider()
    st.subheader("Timing Triggers")
    st.write(f"**VIX Snap-back:** {'✅ ACTIVE' if sig['vix_buy'] else '⚪ None'}")
    st.write(f"**Trend (SPY > 200MA):** {'✅ Bullish' if sig['trend_up'] else '❌ Bearish'}")

# =============================================================================
# 5. EXECUTION LOGIC
# =============================================================================
if __name__ == "__main__":
    # If this is being run by a user looking at the dashboard
    if st._is_running_with_streamlit:
        run_dashboard()
    
    # If this is being run automatically by GitHub Actions (The Alerter)
    else:
        print("Running Automated Market Check...")
        engine = RegimeBasedDashboard()
        reg = engine.check_regime()
        sig = engine.get_signals()
        
        # Define what triggers a text message
        if reg['regime'] == "OFFENSIVE" and sig['vix_buy']:
            send_alerts(f"🟢 BUY SIGNAL: Regime is Offensive and VIX snapped back. Price: ${sig['spy_price']:.2f}")
        
        elif reg['regime'] == "DEFENSIVE":
            # You can decide if you want a daily text during defensive regimes
            print("System is Defensive. No buy signals.")