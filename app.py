import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Smart Market Dashboard Ultimate")

# =========================
# INPUT
# =========================
ticker = st.text_input("Ticker", "BBRI.JK")

# =========================
# DATA
# =========================
data = yf.download(ticker, period="1y", interval="1d")

# FIX yfinance multiindex
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

data = data.astype(float)

# =========================
# TECHNICAL
# =========================
close = data['Close']

data['SMA20'] = ta.trend.sma_indicator(close, window=20)
data['SMA50'] = ta.trend.sma_indicator(close, window=50)
data['RSI'] = ta.momentum.rsi(close, window=14)

macd = ta.trend.MACD(close)
data['MACD'] = macd.macd()
data['MACD_signal'] = macd.macd_signal()

# =========================
# CHART
# =========================
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close'],
    name="Price"
))

fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))

st.plotly_chart(fig, use_container_width=True)

# =========================
# RSI
# =========================
st.subheader("RSI")
st.line_chart(data['RSI'])

# =========================
# MACD
# =========================
st.subheader("MACD")
st.line_chart(data[['MACD','MACD_signal']])

# =========================
# FUNDAMENTAL
# =========================
st.subheader("Fundamental")
info = yf.Ticker(ticker).info

col1, col2, col3, col4 = st.columns(4)

col1.metric("Market Cap", info.get("marketCap"))
col2.metric("PE Ratio", info.get("trailingPE"))
col3.metric("PB Ratio", info.get("priceToBook"))
col4.metric("ROE", info.get("returnOnEquity"))

# =========================
# NEWS
# =========================
st.subheader("Latest News")

try:
    news = yf.Ticker(ticker).news
    for n in news[:5]:
        st.write(f"### {n['title']}")
        st.write(n['publisher'])
        st.write(n['link'])
except:
    st.write("No news available")

# =========================
# SIGNAL
# =========================
st.subheader("Signal")

if data['RSI'].iloc[-1] < 30:
    st.success("Oversold - Potential Buy")
elif data['RSI'].iloc[-1] > 70:
    st.error("Overbought - Potential Sell")
else:
    st.info("Neutral")
