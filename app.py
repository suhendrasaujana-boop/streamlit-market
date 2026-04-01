import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# ========== KONFIGURASI HALAMAN ==========
st.set_page_config(layout="wide", page_title="Smart Market Dashboard", page_icon="📊")

# ========== SESSION STATE ==========
if 'last_resistance' not in st.session_state:
    st.session_state.last_resistance = None
if 'last_volume_ratio' not in st.session_state:
    st.session_state.last_volume_ratio = 0

# ========== FUNGSI BANTU ==========
def safe_sma(series, window):
    if len(series) < window:
        return series.rolling(window, min_periods=1).mean()
    return ta.trend.sma_indicator(series, window=window)

def format_number(x):
    """Format angka dengan koma untuk ribuan (untuk tampilan)"""
    if x is None or pd.isna(x):
        return "N/A"
    return f"{x:,.2f}"

def fix_ticker(ticker):
    """Otomatis tambahkan .JK jika diperlukan (kecuali indeks)"""
    ticker = ticker.strip().upper()
    if ticker.startswith('^') or ticker.endswith('.JK'):
        return ticker
    return ticker + '.JK'

# ========== SIDEBAR ==========
with st.sidebar:
    # Gunakan emoji sebagai ikon (stabil, tidak bergantung URL)
    st.markdown("# 📊 Smart Market Dashboard")
    
    ticker_input = st.text_input(
        "Ticker",
        "^JKSE",
        help="Contoh: BBCA, BBRI, ASII, atau ^JKSE untuk IHSG. Anda boleh ketik tanpa .JK, akan otomatis ditambahkan."
    )
    # Perbaiki ticker (tambahkan .JK jika perlu)
    ticker = fix_ticker(ticker_input)
    if ticker != ticker_input:
        st.info(f"Format ticker disesuaikan menjadi: {ticker}")
    
    timeframe = st.selectbox("Timeframe", ["1d","1wk","1mo"], help="1d = harian, 1wk = mingguan, 1mo = bulanan")
    
    # Tombol refresh manual
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.caption("Data dari Yahoo Finance | Update otomatis setiap 10 menit")

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

@st.cache_data(ttl=600)
def get_fundamental(ticker):
    """Ambil info fundamental dari yfinance"""
    try:
        obj = yf.Ticker(ticker)
        info = obj.info
        return {
            'pe': info.get('trailingPE', None),
            'pb': info.get('priceToBook', None),
            'div_yield': info.get('dividendYield', None),
            'market_cap': info.get('marketCap', None),
            'sector': info.get('sector', None)
        }
    except:
        return {}

data = load_data(ticker, timeframe)

if data.empty or len(data) < 5:
    st.warning(f"Data tidak cukup untuk {ticker} (minimal 5 periode).")
    st.stop()

# Data tambahan untuk fundamental (jika saham, bukan indeks)
if not ticker.startswith('^'):
    fundamental = get_fundamental(ticker)
else:
    fundamental = {}

close = data['Close']
volume = data['Volume'] if 'Volume' in data.columns else pd.Series(0, index=data.index)

# ========== INDIKATOR TEKNIS ==========
data['SMA20'] = safe_sma(close, min(20, len(data)-1))
data['SMA50'] = safe_sma(close, min(50, len(data)-1))

if len(data) >= 14:
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

if volume.sum() > 0:
    data['Volume_MA'] = volume.rolling(20, min_periods=1).mean()
else:
    data['Volume_MA'] = 0.0

data['support'] = data['Low'].rolling(20, min_periods=1).min()
data['resistance'] = data['High'].rolling(20, min_periods=1).max()

# Akumulasi/Distribusi (AD)
try:
    data['AD'] = ta.volume.acc_dist_index(data['High'], data['Low'], data['Close'], data['Volume'], fillna=True)
except:
    data['AD'] = 0.0

# Chaikin Money Flow (CMF) 20 periode
try:
    data['CMF'] = ta.volume.chaikin_money_flow(data['High'], data['Low'], data['Close'], data['Volume'], window=20, fillna=True)
except:
    data['CMF'] = 0.0

# Forward fill untuk semua kolom, lalu isi NaN dengan 0
data = data.ffill().fillna(0)

# ========== NOTIFIKASI BREAKOUT (toast) ==========
if not data.empty:
    current_resistance = data['resistance'].iloc[-1]
    current_price = data['Close'].iloc[-1]
    if st.session_state.last_resistance is None:
        st.session_state.last_resistance = current_resistance

    if current_price > current_resistance and current_resistance != st.session_state.last_resistance:
        st.toast(f"🚀 BREAKOUT! Harga menembus resistance {current_resistance:.2f}", icon="🚀")
        st.session_state.last_resistance = current_resistance

    if volume.sum() > 0:
        vol_last = volume.iloc[-1]
        vol_ma = data['Volume_MA'].iloc[-1]
        if vol_ma > 0:
            volume_ratio = vol_last / vol_ma
            if volume_ratio > 1.8 and volume_ratio != st.session_state.last_volume_ratio:
                st.toast(f"🔥 Volume Spike! {volume_ratio:.1f}x rata-rata", icon="⚠️")
                st.session_state.last_volume_ratio = volume_ratio

# ========== HEADER: INFO HARGA & FUNDAMENTAL ==========
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

# Akumulasi/Distribusi dan CMF
ad_val = data['AD'].iloc[-1]
cmf_val = data['CMF'].iloc[-1]
ad_status = "Akumulasi" if ad_val > 0 else "Distribusi" if ad_val < 0 else "Netral"
cmf_status = "Akumulasi" if cmf_val > 0 else "Distribusi" if cmf_val < 0 else "Netral"

st.markdown(f"""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px;">
    <b>📊 Akumulasi/Distribusi (AD):</b> {ad_status} ({ad_val:.2f}) &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>💰 Chaikin Money Flow (CMF20):</b> {cmf_status} ({cmf_val:.3f})
</div>
""", unsafe_allow_html=True)

# Fundamental ringkas (jika ada)
if fundamental:
    pe = fundamental.get('pe')
    pb = fundamental.get('pb')
    div_yield = fundamental.get('div_yield')
    market_cap = fundamental.get('market_cap')
    sector = fundamental.get('sector')
    fund_cols = st.columns(4)
    fund_cols[0].metric("PER (TTM)", f"{pe:.2f}" if pe else "N/A")
    fund_cols[1].metric("PBV", f"{pb:.2f}" if pb else "N/A")
    fund_cols[2].metric("Dividend Yield", f"{div_yield*100:.2f}%" if div_yield else "N/A")
    fund_cols[3].metric("Market Cap", f"{market_cap/1e12:.2f}T" if market_cap else "N/A")
    if sector:
        st.caption(f"Sektor: {sector}")

st.markdown("---")

# ========== TABS UTAMA ==========
tab1, tab2, tab3, tab4 = st.tabs(["📈 Grafik & Indikator", "🤖 AI Signal & Risk", "🔍 IHSG Scanner", "📖 Glossary"])

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

    # Volume
    st.subheader("Volume")
    if volume.sum() > 0:
        st.bar_chart(volume)
    else:
        st.info("Volume tidak tersedia untuk indeks (IHSG)")

    # RSI & MACD dalam 2 kolom
    col_r, col_m = st.columns(2)
    with col_r:
        st.subheader("RSI (14)")
        st.line_chart(data['RSI'])
        st.caption("RSI < 35: Oversold (potensi beli) | RSI > 70: Overbought (potensi jual)")
    with col_m:
        st.subheader("MACD")
        st.line_chart(data[['MACD', 'MACD_signal']])
        st.caption("MACD > Signal: Bullish | MACD < Signal: Bearish")

    # AD & CMF
    st.subheader("Accumulation/Distribution & Chaikin Money Flow")
    col_ad, col_cmf = st.columns(2)
    with col_ad:
        st.line_chart(data['AD'])
        st.caption("AD Line naik = akumulasi, turun = distribusi")
    with col_cmf:
        st.line_chart(data['CMF'])
        st.caption("CMF > 0 = tekanan beli, < 0 = tekanan jual")

# ========== TAB 2: AI SIGNAL & RISK ==========
with tab2:
    # AI Score
    score = 0
    try:
        if pd.notna(data['RSI'].iloc[-1]) and data['RSI'].iloc[-1] < 35: score += 1
        if pd.notna(data['Close'].iloc[-1]) and pd.notna(data['SMA20'].iloc[-1]) and data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: score += 1
        if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]: score += 1
        if pd.notna(data['MACD'].iloc[-1]) and pd.notna(data['MACD_signal'].iloc[-1]) and data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: score += 1
        if volume.sum() > 0 and pd.notna(volume.iloc[-1]) and pd.notna(data['Volume_MA'].iloc[-1]) and volume.iloc[-1] > data['Volume_MA'].iloc[-1]: score += 1
    except Exception:
        pass

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🤖 AI Score")
        st.metric("Score", f"{score}/5")
        if score >= 4:
            st.success("🚀 STRONG BUY")
        elif score == 3:
            st.info("🟡 HOLD")
        else:
            st.error("🔻 SELL")

    with col_b:
        st.subheader("🎯 Risk Meter")
        returns = data['Close'].pct_change().dropna()
        volatility = returns.std() * 100 if len(returns) > 0 else 0
        if volatility < 1.5:
            risk = "LOW"
            st.success(f"Risk Level : {risk}")
        elif volatility < 3:
            risk = "MEDIUM"
            st.warning(f"Risk Level : {risk}")
        else:
            risk = "HIGH"
            st.error(f"Risk Level : {risk}")

    # Probability Engine
    st.subheader("📊 Probability Engine")
    bull = bear = 0
    if data['RSI'].iloc[-1] < 35:
        bull += 1
    else:
        bear += 1
    if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
        bull += 1
    else:
        bear += 1
    if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
        bull += 1
    else:
        bear += 1
    total = bull + bear
    if total > 0:
        bull_prob = (bull/total)*100
        bear_prob = (bear/total)*100
    else:
        bull_prob = bear_prob = 50
    st.write(f"📈 Bullish: {bull_prob:.1f}% | 📉 Bearish: {bear_prob:.1f}%")

    # Momentum Detector
    st.subheader("🔥 Momentum Detector")
    if len(data) >= 6:
        momentum = data['Close'].pct_change(5).iloc[-1] * 100
        if pd.isna(momentum):
            momentum = 0
    else:
        momentum = 0
    if momentum > 5:
        st.success("Strong Up Momentum")
    elif momentum > 2:
        st.info("Moderate Up Momentum")
    elif momentum < -5:
        st.error("Strong Down Momentum")
    else:
        st.warning("Sideways")

    # Breakout Detector & Volume Alert
    col_brk, col_vol = st.columns(2)
    with col_brk:
        st.subheader("🚀 Breakout Detector")
        if len(data) > 1 and data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
            st.success("🔥 BREAKOUT DETECTED")
        else:
            st.info("Tidak ada breakout")
    with col_vol:
        st.subheader("🚨 Volume Alert")
        if volume.sum() > 0:
            if volume.iloc[-1] > data['Volume_MA'].iloc[-1] * 1.8:
                st.success("Volume Spike Detected")
            else:
                st.write("Normal Volume")
        else:
            st.info("Volume tidak tersedia")

    # AI FINAL PRO
    st.header("🧠 AI FINAL PRO")
    final_score = 0
    if bull_prob > 60:
        final_score += 1
    if risk == "LOW":
        final_score += 1
    if momentum > 2:
        final_score += 1
    if volume.sum() > 0 and volume.iloc[-1] > data['Volume_MA'].iloc[-1]:
        final_score += 1
    if final_score >= 3:
        st.success("🚀 STRONG ACCUMULATE")
    elif final_score == 2:
        st.warning("🟡 SPEC BUY")
    else:
        st.error("🔻 WAIT / AVOID")

    # GOD MODE
    st.header("🚀 GOD MODE TRADING ENGINE")
    price = data['Close'].iloc[-1]
    support = data['support'].iloc[-1] if pd.notna(data['support'].iloc[-1]) else price * 0.95
    resistance = data['resistance'].iloc[-1] if pd.notna(data['resistance'].iloc[-1]) else price * 1.05

    entry = (support + price) / 2
    stoploss = support * 0.97
    target1 = resistance
    target2 = resistance * 1.05
    risk_amount = entry - stoploss
    reward = target1 - entry
    rr = reward / risk_amount if risk_amount > 0 else 0

    col_e, col_s, col_t = st.columns(3)
    col_e.metric("🎯 Smart Entry", f"{entry:.2f}")
    col_s.metric("🛑 Stoploss", f"{stoploss:.2f}")
    col_t.metric("💰 Target 1", f"{target1:.2f}")

    st.write(f"**Risk Reward Ratio:** 1 : {rr:.2f}")
    if rr > 2:
        st.success("Good Trade Setup")
    elif rr > 1:
        st.warning("Moderate Setup")
    else:
        st.error("Bad Setup")

    # Trend Score & Breakout Strength
    col_ts, col_bs = st.columns(2)
    with col_ts:
        st.subheader("📈 Trend Score")
        trend_score = 0
        if price > data['SMA20'].iloc[-1]:
            trend_score += 1
        if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
            trend_score += 1
        if data['RSI'].iloc[-1] > 50:
            trend_score += 1
        st.write(f"Trend Score: {trend_score}/3")
    with col_bs:
        st.subheader("🔥 Breakout Strength")
        if price > resistance:
            strength = (price - resistance) / resistance * 100
            st.success(f"Breakout Strength: {strength:.2f}%")
        else:
            st.write("No Breakout")

    # FINAL GOD SIGNAL
    st.header("🧠 FINAL GOD SIGNAL")
    god_score = 0
    if rr > 2:
        god_score += 1
    if trend_score >= 2:
        god_score += 1
    if data['RSI'].iloc[-1] < 70:
        god_score += 1
    if price > data['SMA20'].iloc[-1]:
        god_score += 1
    if god_score >= 3:
        st.success("🚀 GOD MODE BUY")
    elif god_score == 2:
        st.warning("⚡ SPEC BUY")
    else:
        st.error("❌ NO TRADE")

    # FINAL DECISION
    st.header("FINAL DECISION")
    if score >= 4:
        st.success("🟢 ACCUMULATE")
    elif score == 3:
        st.warning("🟡 WAIT")
    else:
        st.error("🔴 AVOID")

# ========== TAB 3: IHSG SCANNER (DIPERBAIKI) ==========
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
                if len(df) < 20:
                    continue
                close = df['Close']
                rsi = ta.momentum.rsi(close, window=14).iloc[-1] if len(close) >= 14 else 50
                sma20 = close.rolling(20).mean().iloc[-1]
                if pd.isna(sma20):
                    sma20 = close.iloc[-1]
                score_val = (1 if rsi < 35 else 0) + (1 if close.iloc[-1] > sma20 else 0)
                rows.append([ticker, round(rsi, 2), score_val])
            except Exception:
                continue
        return pd.DataFrame(rows, columns=["Ticker", "RSI", "Score"])

    with st.spinner("Memindai 15 saham IHSG..."):
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

# ========== TAB 4: GLOSSARY ==========
with tab4:
    st.markdown("""
    ### 📊 TECHNICAL INDICATORS
    **1. RSI (Relative Strength Index)**
    - Mengukur kekuatan pergerakan harga
    - RSI < 30 → Oversold (potensi naik)
    - RSI > 70 → Overbought (potensi turun)
    - RSI 30-70 → Normal

    **2. SMA (Simple Moving Average)**
    - Rata-rata harga dalam periode tertentu
    - SMA20: Trend jangka pendek (1 bulan)
    - SMA50: Trend jangka menengah (2-3 bulan)
    - Harga > SMA = Trend naik
    - Harga < SMA = Trend turun

    **3. MACD (Moving Average Convergence Divergence)**
    - Indikator momentum dan trend
    - MACD > Signal = Bullish
    - MACD < Signal = Bearish

    **4. Volume & Volume MA**
    - Volume: Jumlah saham yang diperdagangkan
    - Volume MA: Rata-rata volume 20 hari
    - Volume > MA(20)×1.8 = Volume Spike

    **5. Support & Resistance**
    - Support: Level harga terendah (area beli)
    - Resistance: Level harga tertinggi (area jual)

    **6. Accumulation/Distribution (AD)**
    - Mengukur aliran dana masuk/keluar
    - AD > 0 = Akumulasi (tekanan beli)
    - AD < 0 = Distribusi (tekanan jual)

    **7. Chaikin Money Flow (CMF)**
    - Volume-weighted indicator
    - CMF > 0 = Akumulasi
    - CMF < 0 = Distribusi

    ### 🎯 SIGNAL SYSTEMS
    **AI Score (0-5)**
    - +1: RSI < 35
    - +1: Harga > SMA20
    - +1: SMA20 > SMA50
    - +1: MACD > Signal
    - +1: Volume > Rata-rata
    - 4-5: STRONG BUY | 3: HOLD | 0-2: SELL

    **Probability Engine**
    - Menghitung peluang Bullish/Bearish dari 3 indikator

    **Risk Meter**
    - Volatilitas harian: LOW (<1.5%), MEDIUM (1.5-3%), HIGH (>3%)

    **God Mode**
    - Kombinasi Risk Reward, Trend Score, RSI, dan SMA untuk sinyal akhir

    ### 💡 TIPS
    1. Gunakan timeframe yang berbeda untuk konfirmasi trend.
    2. Jangan hanya mengandalkan satu indikator.
    3. Selalu gunakan stop loss.
    4. Breakout tanpa volume tinggi seringkali false breakout.
    """)

# ========== DISCLAIMER ==========
st.markdown("---")
st.caption("⚠️ **DISCLAIMER:** Dashboard ini hanya untuk edukasi dan analisis teknikal otomatis. Bukan rekomendasi beli/jual. Keputusan investasi sepenuhnya risiko Anda.")
