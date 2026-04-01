import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import requests
from datetime import datetime, date

# ========== KONFIGURASI HALAMAN ==========
st.set_page_config(layout="wide", page_title="Smart Market Dashboard", page_icon="📈")

# ========== SESSION STATE ==========
if 'last_resistance' not in st.session_state:
    st.session_state.last_resistance = None
if 'last_volume_ratio' not in st.session_state:
    st.session_state.last_volume_ratio = 0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# ========== FUNGSI BANTU ==========
def safe_sma(series, window):
    if len(series) < window:
        return series.rolling(window, min_periods=1).mean()
    return ta.trend.sma_indicator(series, window=window)

def fix_ticker(ticker):
    ticker = ticker.strip().upper()
    if ticker.startswith('^') or ticker.endswith('.JK'):
        return ticker
    return ticker + '.JK'

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("# 📊 Smart Market Dashboard")
    ticker_input = st.text_input("Ticker", "^JKSE", help="Contoh: BBCA, BBRI")
    ticker = fix_ticker(ticker_input)
    if ticker != ticker_input:
        st.info(f"Format: {ticker}")
    timeframe = st.selectbox("Timeframe", ["1d","1wk","1mo"])
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption("Data dari Yahoo Finance")

# ========== LOAD DATA ==========
@st.cache_data(ttl=600)
def load_data(ticker, timeframe):
    df = yf.download(ticker, period="2y", interval=timeframe, progress=False)
    if df.empty:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(how='all')
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'].fillna(0)
    return df

data = load_data(ticker, timeframe)
if data.empty or len(data) < 5:
    st.warning(f"Data tidak cukup untuk {ticker}.")
    st.stop()

close = data['Close']
volume = data['Volume'] if 'Volume' in data.columns else pd.Series(0, index=data.index)

# ========== INDIKATOR TEKNIS ==========
data['SMA20'] = safe_sma(close, min(20, len(data)-1))
data['SMA50'] = safe_sma(close, min(50, len(data)-1))
data['RSI'] = ta.momentum.rsi(close, window=14) if len(data) >= 14 else 50.0
if len(data) >= 26:
    macd = ta.trend.MACD(close)
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()
else:
    data['MACD'] = 0.0
    data['MACD_signal'] = 0.0
if volume.sum() > 0:
    data['Volume_MA'] = volume.rolling(20, min_periods=1).mean()
else:
    data['Volume_MA'] = 0.0
data['support'] = data['Low'].rolling(20, min_periods=1).min()
data['resistance'] = data['High'].rolling(20, min_periods=1).max()
try:
    data['AD'] = ta.volume.acc_dist_index(data['High'], data['Low'], data['Close'], data['Volume'], fillna=True)
except:
    data['AD'] = 0.0
try:
    data['CMF'] = ta.volume.chaikin_money_flow(data['High'], data['Low'], data['Close'], data['Volume'], window=20, fillna=True)
except:
    data['CMF'] = 0.0
data = data.ffill().fillna(0)

# ========== HEADER ==========
st.title(f"📈 {ticker}")
last_close = data['Close'].iloc[-1]
last_high = data['High'].iloc[-1]
last_low = data['Low'].iloc[-1]
prev_close = data['Close'].iloc[-2] if len(data) > 1 else last_close
change = last_close - prev_close
change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
col1, col2, col3, col4 = st.columns(4)
col1.metric("Harga Terakhir", f"{last_close:.2f}", f"{change_pct:.2f}%", delta_color="normal")
col2.metric("Hari Ini - Tertinggi", f"{last_high:.2f}")
col3.metric("Hari Ini - Terendah", f"{last_low:.2f}")
col4.metric("Volume Terakhir", f"{volume.iloc[-1]:,.0f}" if volume.sum() > 0 else "N/A")

ad_val = data['AD'].iloc[-1]
cmf_val = data['CMF'].iloc[-1]
ad_status = "Akumulasi" if ad_val > 0 else "Distribusi" if ad_val < 0 else "Netral"
cmf_status = "Akumulasi" if cmf_val > 0 else "Distribusi" if cmf_val < 0 else "Netral"
st.markdown(f"""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px;">
    <b>📊 AD:</b> {ad_status} ({ad_val:.2f}) &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>💰 CMF20:</b> {cmf_status} ({cmf_val:.3f})
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# ========== TABS ==========
tab1, tab2, tab3, tab4 = st.tabs(["📈 Grafik", "🤖 AI Signal", "🔍 IHSG Scanner", "📖 Info"])

# ========== TAB 1: GRAFIK ==========
with tab1:
    st.subheader("Candlestick Chart")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'],
                                 low=data['Low'], close=data['Close'], name="Price"))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))
    fig.add_trace(go.Scatter(x=data.index, y=data['support'], name="Support", line=dict(dash='dash')))
    fig.add_trace(go.Scatter(x=data.index, y=data['resistance'], name="Resistance", line=dict(dash='dash')))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Volume")
    if volume.sum() > 0:
        st.bar_chart(volume)
    else:
        st.info("Volume tidak tersedia untuk indeks")

    col_r, col_m = st.columns(2)
    with col_r:
        st.subheader("RSI (14)")
        st.line_chart(data['RSI'])
    with col_m:
        st.subheader("MACD")
        st.line_chart(data[['MACD', 'MACD_signal']])

    st.subheader("AD & CMF")
    col_ad, col_cmf = st.columns(2)
    with col_ad:
        st.line_chart(data['AD'])
    with col_cmf:
        st.line_chart(data['CMF'])

# ========== TAB 2: AI SIGNAL ==========
with tab2:
    score = 0
    try:
        if data['RSI'].iloc[-1] < 35: score += 1
        if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: score += 1
        if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]: score += 1
        if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: score += 1
        if volume.sum() > 0 and volume.iloc[-1] > data['Volume_MA'].iloc[-1]: score += 1
    except:
        pass
    st.subheader("🤖 AI Score")
    st.metric("Score", f"{score}/5")
    if score >= 4:
        st.success("🚀 STRONG BUY")
    elif score == 3:
        st.info("🟡 HOLD")
    else:
        st.error("🔻 SELL")

    # Probability
    st.subheader("📊 Probability Engine")
    bull = bear = 0
    if data['RSI'].iloc[-1] < 35: bull += 1
    else: bear += 1
    if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: bull += 1
    else: bear += 1
    if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: bull += 1
    else: bear += 1
    total = bull + bear
    bull_prob = (bull/total)*100 if total > 0 else 50
    st.write(f"📈 Bullish: {bull_prob:.1f}% | 📉 Bearish: {100-bull_prob:.1f}%")

    # Risk Meter
    returns = data['Close'].pct_change().dropna()
    volatility = returns.std() * 100 if len(returns) > 0 else 0
    if volatility < 1.5:
        risk = "LOW"
        st.success(f"Risk Level: {risk}")
    elif volatility < 3:
        risk = "MEDIUM"
        st.warning(f"Risk Level: {risk}")
    else:
        risk = "HIGH"
        st.error(f"Risk Level: {risk}")

    # FINAL DECISION
    st.header("FINAL DECISION")
    if score >= 3:
        st.success("🟢 ACCUMULATE")
    elif score == 2:
        st.warning("🟡 WAIT")
    else:
        st.error("🔴 AVOID")

# ========== TAB 3: IHSG SCANNER ==========
with tab3:
    st.subheader("🔥 SUPER FAST IHSG SCANNER (15 Blue Chip)")
    full_ihsg_list = [
        "BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
        "ADRO.JK","ANTM.JK","MDKA.JK","UNTR.JK","ICBP.JK",
        "INDF.JK","UNVR.JK","SMGR.JK","CPIN.JK","JPFA.JK"
    ]
    @st.cache_data(ttl=1800)
    def scan_market_fast(tickers):
        all_data = yf.download(tickers, period="6mo", interval="1d", group_by="ticker", progress=False, threads=True)
        rows = []
        for ticker in tickers:
            try:
                if ticker not in all_data.columns.levels[0]:
                    continue
                df = all_data[ticker].dropna()
                if len(df) < 20: continue
                close = df['Close']
                rsi = ta.momentum.rsi(close, window=14).iloc[-1] if len(close) >= 14 else 50
                sma20 = close.rolling(20).mean().iloc[-1]
                if pd.isna(sma20):
                    sma20 = close.iloc[-1]
                score_val = (1 if rsi < 35 else 0) + (1 if close.iloc[-1] > sma20 else 0)
                rows.append([ticker, round(rsi, 2), score_val])
            except:
                continue
        return pd.DataFrame(rows, columns=["Ticker", "RSI", "Score"])
    with st.spinner("Memindai 15 saham..."):
        scan_df = scan_market_fast(full_ihsg_list)
    if not scan_df.empty:
        st.dataframe(scan_df.sort_values("Score", ascending=False), use_container_width=True)
        st.subheader("🚀 TOP 5 BUY")
        top5 = scan_df.sort_values("Score", ascending=False).head(5)
        if not top5.empty:
            st.table(top5)
        else:
            st.info("Tidak ada saham dengan score > 0")
    else:
        st.warning("Scanner gagal, coba lagi nanti.")

# ========== TAB 4: INFO ==========
with tab4:
    with st.expander("📖 Glossary"):
        st.markdown("""
        **RSI** < 35: Oversold (potensi beli) | >70: Overbought  
        **SMA20/50**: Harga > SMA = uptrend  
        **MACD > Signal**: Bullish  
        **Volume > Volume MA**: Volume di atas rata-rata  
        **AD > 0**: Akumulasi (tekanan beli)  
        **CMF > 0**: Tekanan beli  
        **AI Score** 4-5: Strong Buy, 3: Hold, 0-2: Sell  
        **FINAL DECISION** score ≥3: Accumulate, =2: Wait, ≤1: Avoid
        """)
    st.caption("⚠️ **DISCLAIMER:** Dashboard ini hanya untuk edukasi dan analisis otomatis. Bukan rekomendasi beli/jual.")
