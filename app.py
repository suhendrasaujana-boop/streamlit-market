import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Smart Market Dashboard")

ticker = st.text_input("Ticker", "BBRI.JK")

@st.cache_data
def load_data(ticker):
    data = yf.download(ticker, period="1y", interval="1d")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

data = load_data(ticker)

if data.empty:
    st.stop()

close = data['Close']

data['SMA20'] = ta.trend.sma_indicator(close, window=20)
data['SMA50'] = ta.trend.sma_indicator(close, window=50)
data['RSI'] = ta.momentum.rsi(close, window=14)

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close']
))

fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))

st.plotly_chart(fig, use_container_width=True)

st.subheader("RSI")
st.line_chart(data['RSI'])

# SIGNAL
st.subheader("Signal")
rsi = data['RSI'].iloc[-1]

if rsi < 30:
    st.success("BUY - Oversold")
elif rsi > 70:
    st.error("SELL - Overbought")
else:
    st.info("WAIT")
