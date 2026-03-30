import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
import time

st.set_page_config(layout="wide")
st.title("🚀 SMART MARKET DASHBOARD — ALL IN ONE FINAL")

# =========================
# SESSION STATE UNTUK NOTIFIKASI
# =========================
if 'last_resistance' not in st.session_state:
    st.session_state.last_resistance = None
if 'last_volume_ratio' not in st.session_state:
    st.session_state.last_volume_ratio = 0

# =========================
# INPUT
# =========================
col1, col2 = st.columns(2)
ticker = col1.text_input("Ticker", "^JKSE")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# =========================
# LOAD DATA DENGAN HANDLING NaN
# =========================
@st.cache_data(ttl=600)
def load_data(ticker, timeframe):
    df = yf.download(ticker, period="2y", interval=timeframe, progress=False)
    if df.empty:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(how='all')
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'].fillna(0)
    return df

data = load_data(ticker, timeframe)

if data.empty or len(data) < 20:
    st.warning(f"Data tidak mencukupi untuk {ticker}. Minimal 20 periode.")
    st.stop()

close = data['Close']

# =========================
# INDICATORS DENGAN HANDLING NaN
# =========================
min_periods = min(20, len(data)-1)
data['SMA20'] = ta.trend.sma_indicator(close, window=min(20, len(data)-1))
data['SMA50'] = ta.trend.sma_indicator(close, window=min(50, len(data)-1))

if len(data) >= 15:
    data['RSI'] = ta.momentum.rsi(close, window=14)
else:
    data['RSI'] = 50.0

if len(data) >= 26:
    macd = ta.trend.MACD(close)
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()
else:
    data['MACD'] = 0.0
    data['MACD_signal'] = 0.0

if data['Volume'].sum() > 0:
    data['Volume_MA'] = data['Volume'].rolling(20, min_periods=1).mean()
else:
    data['Volume_MA'] = 0.0

data['support'] = data['Low'].rolling(20, min_periods=1).min()
data['resistance'] = data['High'].rolling(20, min_periods=1).max()

data = data.fillna(method='ffill').fillna(0)

# =========================
# NOTIFIKASI BREAKOUT & VOLUME SPIKE
# =========================
current_resistance = data['resistance'].iloc[-1]
current_price = data['Close'].iloc[-1]
if st.session_state.last_resistance is None:
    st.session_state.last_resistance = current_resistance

if current_price > current_resistance and current_resistance != st.session_state.last_resistance:
    st.toast(f"🚀 BREAKOUT! Harga menembus resistance {current_resistance:.2f}", icon="🚀")
    st.session_state.last_resistance = current_resistance

if data['Volume'].sum() > 0:
    volume_ratio = data['Volume'].iloc[-1] / data['Volume_MA'].iloc[-1] if data['Volume_MA'].iloc[-1] > 0 else 0
    if volume_ratio > 1.8 and volume_ratio != st.session_state.last_volume_ratio:
        st.toast(f"🔥 Volume Spike! {volume_ratio:.1f}x rata-rata", icon="⚠️")
        st.session_state.last_volume_ratio = volume_ratio

# =========================
# CHART
# =========================
fig = go.Figure()
fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))
fig.add_trace(go.Scatter(x=data.index, y=data['support'], name="Support"))
fig.add_trace(go.Scatter(x=data.index, y=data['resistance'], name="Resistance"))
st.plotly_chart(fig, use_container_width=True)

# =========================
# VOLUME
# =========================
st.subheader("Volume")
if data['Volume'].sum() > 0:
    st.bar_chart(data['Volume'])
else:
    st.info("Volume tidak tersedia untuk indeks (IHSG)")

# =========================
# RSI + MACD
# =========================
col1, col2 = st.columns(2)
with col1:
    st.subheader("RSI")
    st.line_chart(data['RSI'])
with col2:
    st.subheader("MACD")
    st.line_chart(data[['MACD', 'MACD_signal']])

# =========================
# AI SCORE ENGINE
# =========================
score = 0
try:
    if pd.notna(data['RSI'].iloc[-1]) and data['RSI'].iloc[-1] < 35: score += 1
    if pd.notna(data['Close'].iloc[-1]) and pd.notna(data['SMA20'].iloc[-1]) and data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: score += 1
    if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]: score += 1
    if pd.notna(data['MACD'].iloc[-1]) and pd.notna(data['MACD_signal'].iloc[-1]) and data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: score += 1
    if data['Volume'].sum() > 0 and pd.notna(data['Volume'].iloc[-1]) and pd.notna(data['Volume_MA'].iloc[-1]) and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]: score += 1
except: pass

st.subheader("🤖 AI Score")
st.metric("Score", f"{score}/5")
if score >= 4: st.success("🚀 STRONG BUY")
elif score == 3: st.info("🟡 HOLD")
else: st.error("🔻 SELL")

# =========================
# BREAKOUT DETECTOR
# =========================
if len(data) > 1 and data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
    st.success("🔥 BREAKOUT DETECTED")

# =========================
# RISK METER
# =========================
st.subheader("🎯 Risk Meter")
returns = data['Close'].pct_change().dropna()
volatility = returns.std() * 100 if len(returns) > 0 else 0
if volatility < 1.5:
    risk = "LOW"; st.success(f"Risk Level : {risk}")
elif volatility < 3:
    risk = "MEDIUM"; st.warning(f"Risk Level : {risk}")
else:
    risk = "HIGH"; st.error(f"Risk Level : {risk}")

# =========================
# SUPER FAST IHSG SCANNER (Parallel + Caching)
# =========================
st.subheader("🔥 SUPER FAST IHSG SCANNER (15 Blue Chip)")

ihsg_list = [
    "BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
    "ADRO.JK","ANTM.JK","MDKA.JK","UNTR.JK","ICBP.JK",
    "INDF.JK","UNVR.JK","SMGR.JK","CPIN.JK","JPFA.JK"
]

@st.cache_data(ttl=1800)  # cache 30 menit
def scan_market_fast():
    # Download semua ticker dalam 1 request paralel
    all_data = yf.download(ihsg_list, period="6mo", interval="1d", group_by="ticker", progress=False, threads=True)
    rows = []
    for ticker in ihsg_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 20:
                continue
            close = df['Close']
            # RSI
            if len(close) >= 14:
                rsi = ta.momentum.rsi(close, window=14).iloc[-1]
            else:
                rsi = 50
            sma20 = close.rolling(20).mean().iloc[-1]
            if pd.isna(sma20):
                sma20 = close.iloc[-1]
            score = (1 if rsi < 35 else 0) + (1 if close.iloc[-1] > sma20 else 0)
            rows.append([ticker, round(rsi, 2), score])
        except Exception:
            continue
    return pd.DataFrame(rows, columns=["Ticker", "RSI", "Score"])

with st.spinner("Memindai 15 saham IHSG..."):
    scan_df = scan_market_fast()

if not scan_df.empty:
    st.dataframe(scan_df.sort_values("Score", ascending=False), use_container_width=True)
    st.subheader("🚀 TOP 5 BUY")
    top5 = scan_df.sort_values("Score", ascending=False).head(5)
    st.table(top5)
else:
    st.warning("Scanner gagal, coba lagi nanti.")

# =========================
# MARKET MOMENTUM
# =========================
st.subheader("📈 Market Momentum")
returns_tail = data['Close'].pct_change().tail(20).dropna()
gain = (returns_tail > 0).sum()
loss = (returns_tail < 0).sum()
st.write(f"Up Days: {gain} | Down Days: {loss}")

# =========================
# PROBABILITY ENGINE
# =========================
st.subheader("📊 Probability Engine")
bull = bear = 0
if data['RSI'].iloc[-1] < 35: bull += 1
else: bear += 1
if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: bull += 1
else: bear += 1
if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: bull += 1
else: bear += 1
total = bull + bear
if total > 0:
    bull_prob = (bull/total)*100
    bear_prob = (bear/total)*100
else:
    bull_prob = bear_prob = 50
st.write(f"📈 Bullish: {bull_prob:.1f}% | 📉 Bearish: {bear_prob:.1f}%")

# =========================
# MOMENTUM DETECTOR
# =========================
st.subheader("🔥 Momentum Detector")
if len(data) >= 6:
    momentum = data['Close'].pct_change(5).iloc[-1] * 100
    if pd.isna(momentum): momentum = 0
else:
    momentum = 0
if momentum > 5: st.success("Strong Up Momentum")
elif momentum > 2: st.info("Moderate Up Momentum")
elif momentum < -5: st.error("Strong Down Momentum")
else: st.warning("Sideways")

# =========================
# VOLUME SPIKE ALERT
# =========================
st.subheader("🚨 Volume Alert")
if data['Volume'].sum() > 0:
    if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1] * 1.8:
        st.success("Volume Spike Detected")
    else:
        st.write("Normal Volume")
else:
    st.info("Volume tidak tersedia untuk indeks")

# =========================
# TREND STRENGTH
# =========================
st.subheader("📈 Trend Strength")
if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['Close'].iloc[-1] > 0:
    trend_strength = abs(data['SMA20'].iloc[-1] - data['SMA50'].iloc[-1])
    if trend_strength > data['Close'].iloc[-1] * 0.05: st.success("Strong Trend")
    elif trend_strength > data['Close'].iloc[-1] * 0.02: st.info("Moderate Trend")
    else: st.warning("Weak Trend")
else:
    st.warning("Data tidak cukup")

# =========================
# AI FINAL DECISION PRO
# =========================
st.header("🧠 AI FINAL PRO")
final_score = 0
if bull_prob > 60: final_score += 1
if risk == "LOW": final_score += 1
if momentum > 2: final_score += 1
if data['Volume'].sum() > 0 and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]: final_score += 1
if final_score >= 3: st.success("🚀 STRONG ACCUMULATE")
elif final_score == 2: st.warning("🟡 SPEC BUY")
else: st.error("🔻 WAIT / AVOID")

# =========================
# GOD MODE TRADING ENGINE
# =========================
st.header("🚀 GOD MODE TRADING ENGINE")
price = data['Close'].iloc[-1]
support = data['support'].iloc[-1] if pd.notna(data['support'].iloc[-1]) else price * 0.95
resistance = data['resistance'].iloc[-1] if pd.notna(data['resistance'].iloc[-1]) else price * 1.05

st.subheader("🎯 Smart Entry")
entry = (support + price) / 2
st.write(f"Suggested Entry: {entry:.2f}")

st.subheader("🛑 Stoploss")
stoploss = support * 0.97
st.write(f"Stoploss: {stoploss:.2f}")

st.subheader("💰 Target Profit")
target1 = resistance
target2 = resistance * 1.05
st.write(f"Target 1: {target1:.2f} | Target 2: {target2:.2f}")

st.subheader("⚖️ Risk Reward")
risk_amount = entry - stoploss
reward = target1 - entry
rr = 0
if risk_amount > 0:
    rr = reward / risk_amount
    st.write(f"Risk Reward Ratio: 1 : {rr:.2f}")
    if rr > 2: st.success("Good Trade Setup")
    elif rr > 1: st.warning("Moderate Setup")
    else: st.error("Bad Setup")
else:
    st.warning("Risk tidak valid")

st.subheader("📈 Trend Score")
trend_score = 0
if price > data['SMA20'].iloc[-1]: trend_score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]: trend_score += 1
if data['RSI'].iloc[-1] > 50: trend_score += 1
st.write(f"Trend Score: {trend_score}/3")

st.subheader("🔥 Breakout Strength")
if price > resistance:
    strength = (price - resistance) / resistance * 100
    st.success(f"Breakout Strength: {strength:.2f}%")
else:
    st.write("No Breakout")

st.header("🧠 FINAL GOD SIGNAL")
god_score = 0
if rr > 2: god_score += 1
if trend_score >= 2: god_score += 1
if data['RSI'].iloc[-1] < 70: god_score += 1
if price > data['SMA20'].iloc[-1]: god_score += 1
if god_score >= 3: st.success("🚀 GOD MODE BUY")
elif god_score == 2: st.warning("⚡ SPEC BUY")
else: st.error("❌ NO TRADE")

# =========================
# FINAL DECISION
# =========================
st.header("FINAL DECISION")
if score >= 4: st.success("🟢 ACCUMULATE")
elif score == 3: st.warning("🟡 WAIT")
else: st.error("🔴 AVOID")

# =========================
# GLOSSARY LENGKAP (diringkas agar tidak terlalu panjang tapi informatif)
# =========================
with st.expander("📖 GLOSSARY LENGKAP (Klik untuk lihat semua penjelasan)"):
    st.markdown("""
    **Indikator Teknikal:**
    - **RSI** (<30 oversold, >70 overbought)
    - **SMA20/SMA50** (trend jangka pendek/menengah, harga > SMA = uptrend)
    - **MACD** (momentum, garis > signal = bullish)
    - **Volume & Volume MA** (lonjakan >1.8x = minat besar)
    - **Support/Resistance** (area harga terendah/tertinggi 20 periode)

    **Sistem Scoring:**
    - **AI Score (0-5)**: RSI<35, Harga>SMA20, SMA20>SMA50, MACD>Signal, Volume>MA
    - **Risk Meter**: Volatilitas rendah (<1.5%), sedang (1.5-3%), tinggi (>3%)
    - **Probability Engine**: Peluang bullish vs bearish berdasarkan 3 indikator

    **God Mode:**
    - Smart Entry = (Support + Harga)/2
    - Stop Loss = Support × 0.97
    - Target = Resistance (TP1) dan +5% (TP2)
    - Risk Reward >2 = good setup

    **Scanner Super Cepat**: Download 15 saham paralel, hitung RSI & SMA20, beri score 0-2.
    """)

# =========================
# DISCLAIMER
# =========================
st.markdown("---")
st.caption("⚠️ DISCLAIMER: Dashboard untuk edukasi. Bukan rekomendasi beli/jual. Keputusan investasi sepenuhnya risiko Anda.")
