import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("🚀 Smart Market Dashboard ULTIMATE")

# =========================
# INPUT
# =========================
col1, col2 = st.columns(2)

ticker = col1.text_input("Ticker", "BBRI.JK")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data(ticker, timeframe):
    data = yf.download(ticker, period="1y", interval=timeframe)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

data = load_data(ticker, timeframe)

if data.empty:
    st.stop()

close = data['Close']

# =========================
# INDICATORS
# =========================
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
# VOLUME
# =========================
st.subheader("Volume")
st.bar_chart(data['Volume'])

# =========================
# RSI + MACD
# =========================
col1, col2 = st.columns(2)

with col1:
    st.subheader("RSI")
    st.line_chart(data['RSI'])

with col2:
    st.subheader("MACD")
    st.line_chart(data[['MACD','MACD_signal']])

# =========================
# AI SCORE
# =========================
st.subheader("AI Score")

score = 0

if data['RSI'].iloc[-1] < 30:
    score += 1
if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
    score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
    score += 1
if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
    score += 1

st.metric("Score", f"{score}/4")

# =========================
# SIGNAL
# =========================
st.subheader("Signal")

if score >= 3:
    st.success("STRONG BUY 🚀")
elif score == 2:
    st.info("HOLD")
else:
    st.error("SELL ⚠️")

# =========================
# SCANNER IHSG SIMPLE
# =========================
st.subheader("Quick Scanner")

ihsg_list = ["BBRI.JK","BBCA.JK","TLKM.JK","ASII.JK","BMRI.JK"]

scan_result = []

for s in ihsg_list:
    try:
        d = yf.download(s, period="3mo", interval="1d")
        rsi = ta.momentum.rsi(d['Close']).iloc[-1]
        scan_result.append([s, rsi])
    except:
        pass

scan_df = pd.DataFrame(scan_result, columns=["Ticker","RSI"])
st.dataframe(scan_df.sort_values("RSI"))
