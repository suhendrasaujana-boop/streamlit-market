import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np
from supabase import create_client
from datetime import datetime, timedelta

# ========== KONFIGURASI HALAMAN ==========
st.set_page_config(layout="wide", page_title="Smart Market Dashboard", page_icon="📊")

# ========== SUPABASE ==========
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== SESSION STATE ==========
if 'user' not in st.session_state:
    st.session_state.user = None
if 'subscription_expiry' not in st.session_state:
    st.session_state.subscription_expiry = None
if 'last_resistance' not in st.session_state:
    st.session_state.last_resistance = None
if 'last_volume_ratio' not in st.session_state:
    st.session_state.last_volume_ratio = 0

# ========== FUNGSI AUTENTIKASI ==========
def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        profile = supabase.table('profiles').select('subscription_expiry').eq('id', res.user.id).execute()
        if profile.data:
            st.session_state.subscription_expiry = profile.data[0]['subscription_expiry']
        st.rerun()
        return True
    except Exception:
        st.error("Login gagal. Periksa email dan password.")
        return False

def register_user(email, password):
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": "https://smart-market-dashboard.streamlit.app"
            }
        })
        if response.user:
            st.success("Pendaftaran berhasil! Silakan cek email untuk verifikasi.")
        else:
            st.error("Pendaftaran gagal, coba lagi.")
        return True
    except Exception as e:
        st.error(f"Error detail: {str(e)}")
        return False

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.subscription_expiry = None
    st.rerun()

def is_premium():
    if st.session_state.user is None or st.session_state.subscription_expiry is None:
        return False
    expiry = datetime.fromisoformat(st.session_state.subscription_expiry.replace('Z', '+00:00'))
    return datetime.now(expiry.tzinfo) < expiry

def get_emiten_limit():
    if st.session_state.user is None:
        return 3
    return 5 if is_premium() else 3

# ========== SIDEBAR LOGIN ==========
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/stock.png", width=80)
    st.title("🔐 Akun Saya")
    if st.session_state.user is None:
        tab1, tab2 = st.tabs(["Login", "Daftar"])
        with tab1:
            login_email = st.text_input("Email", key="login_email")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                login_user(login_email, login_pass)
        with tab2:
            reg_email = st.text_input("Email", key="reg_email")
            reg_pass = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Daftar", use_container_width=True):
                register_user(reg_email, reg_pass)
    else:
        st.success(f"👋 Halo, **{st.session_state.user.email}**")
        if is_premium():
            expiry = datetime.fromisoformat(st.session_state.subscription_expiry.replace('Z', '+00:00'))
            sisa_hari = (expiry - datetime.now(expiry.tzinfo)).days
            st.info(f"✅ **Premium aktif**: {sisa_hari} hari lagi (akses 5 emiten)")
        else:
            st.warning("⚠️ **Masa gratis 30 hari telah habis.** Beli paket premium untuk akses 5 emiten.")
        if st.button("Logout", use_container_width=True):
            logout_user()

# ========== MAIN DASHBOARD ==========
st.title("🚀 SMART MARKET DASHBOARD — ALL IN ONE FINAL")

# ========== INPUT TICKER ==========
col1, col2 = st.columns(2)
ticker = col1.text_input("Ticker", "^JKSE")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# ========== LOAD DATA ==========
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

# ========== INDIKATOR TEKNIS ==========
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

data = data.ffill().fillna(0)

# ========== NOTIFIKASI BREAKOUT & VOLUME ==========
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

# ========== CANDLESTICK CHART ==========
fig = go.Figure()
fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))
fig.add_trace(go.Scatter(x=data.index, y=data['support'], name="Support"))
fig.add_trace(go.Scatter(x=data.index, y=data['resistance'], name="Resistance"))
st.plotly_chart(fig, use_container_width=True)

# ========== VOLUME ==========
st.subheader("Volume")
if data['Volume'].sum() > 0:
    st.bar_chart(data['Volume'])
else:
    st.info("Volume tidak tersedia untuk indeks (IHSG)")

# ========== RSI & MACD ==========
col1, col2 = st.columns(2)
with col1:
    st.subheader("RSI")
    st.line_chart(data['RSI'])
with col2:
    st.subheader("MACD")
    st.line_chart(data[['MACD', 'MACD_signal']])

# ========== AI SCORE ==========
score = 0
try:
    if pd.notna(data['RSI'].iloc[-1]) and data['RSI'].iloc[-1] < 35: score += 1
    if pd.notna(data['Close'].iloc[-1]) and pd.notna(data['SMA20'].iloc[-1]) and data['Close'].iloc[-1] > data['SMA20'].iloc[-1]: score += 1
    if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]: score += 1
    if pd.notna(data['MACD'].iloc[-1]) and pd.notna(data['MACD_signal'].iloc[-1]) and data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]: score += 1
    if data['Volume'].sum() > 0 and pd.notna(data['Volume'].iloc[-1]) and pd.notna(data['Volume_MA'].iloc[-1]) and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]: score += 1
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

# ========== BREAKOUT DETECTOR ==========
if len(data) > 1 and data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
    st.success("🔥 BREAKOUT DETECTED")

# ========== RISK METER ==========
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

# ========== IHSG SCANNER DENGAN BATASAN EMITEN ==========
st.subheader("🔥 SUPER FAST IHSG SCANNER (15 Blue Chip)")

# Daftar lengkap 15 saham blue chip
full_ihsg_list = [
    "BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
    "ADRO.JK","ANTM.JK","MDKA.JK","UNTR.JK","ICBP.JK",
    "INDF.JK","UNVR.JK","SMGR.JK","CPIN.JK","JPFA.JK"
]

# Batasi berdasarkan status user
emiten_limit = get_emiten_limit()
ihsg_list = full_ihsg_list[:emiten_limit]

st.caption(f"Menampilkan **{len(ihsg_list)}** dari {len(full_ihsg_list)} emiten (batasan untuk akun Anda: {emiten_limit} emiten)")

@st.cache_data(ttl=1800)
def scan_market_fast(tickers):
    all_data = yf.download(tickers, period="6mo", interval="1d", group_by="ticker", progress=False, threads=True)
    rows = []
    for ticker in tickers:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 20:
                continue
            close = df['Close']
            if len(close) >= 14:
                rsi = ta.momentum.rsi(close, window=14).iloc[-1]
            else:
                rsi = 50
            sma20 = close.rolling(20).mean().iloc[-1]
            if pd.isna(sma20):
                sma20 = close.iloc[-1]
            score_val = (1 if rsi < 35 else 0) + (1 if close.iloc[-1] > sma20 else 0)
            rows.append([ticker, round(rsi, 2), score_val])
        except Exception:
            continue
    return pd.DataFrame(rows, columns=["Ticker", "RSI", "Score"])

with st.spinner("Memindai 15 saham IHSG..."):
    scan_df = scan_market_fast(ihsg_list)

if not scan_df.empty:
    st.dataframe(scan_df.sort_values("Score", ascending=False), use_container_width=True)
    st.subheader("🚀 TOP 5 BUY")
    top5 = scan_df.sort_values("Score", ascending=False).head(5)
    st.table(top5)
else:
    st.warning("Scanner gagal, coba lagi nanti.")

# ========== MARKET MOMENTUM ==========
st.subheader("📈 Market Momentum")
returns_tail = data['Close'].pct_change().tail(20).dropna()
gain = (returns_tail > 0).sum()
loss = (returns_tail < 0).sum()
st.write(f"Up Days: {gain} | Down Days: {loss}")

# ========== PROBABILITY ENGINE ==========
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

# ========== MOMENTUM DETECTOR ==========
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

# ========== VOLUME ALERT ==========
st.subheader("🚨 Volume Alert")
if data['Volume'].sum() > 0:
    if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1] * 1.8:
        st.success("Volume Spike Detected")
    else:
        st.write("Normal Volume")
else:
    st.info("Volume tidak tersedia untuk indeks")

# ========== TREND STRENGTH ==========
st.subheader("📈 Trend Strength")
if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['Close'].iloc[-1] > 0:
    trend_strength = abs(data['SMA20'].iloc[-1] - data['SMA50'].iloc[-1])
    if trend_strength > data['Close'].iloc[-1] * 0.05:
        st.success("Strong Trend")
    elif trend_strength > data['Close'].iloc[-1] * 0.02:
        st.info("Moderate Trend")
    else:
        st.warning("Weak Trend")
else:
    st.warning("Data tidak cukup")

# ========== AI FINAL PRO ==========
st.header("🧠 AI FINAL PRO")
final_score = 0
if bull_prob > 60:
    final_score += 1
if risk == "LOW":
    final_score += 1
if momentum > 2:
    final_score += 1
if data['Volume'].sum() > 0 and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]:
    final_score += 1
if final_score >= 3:
    st.success("🚀 STRONG ACCUMULATE")
elif final_score == 2:
    st.warning("🟡 SPEC BUY")
else:
    st.error("🔻 WAIT / AVOID")

# ========== GOD MODE TRADING ENGINE ==========
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
    if rr > 2:
        st.success("Good Trade Setup")
    elif rr > 1:
        st.warning("Moderate Setup")
    else:
        st.error("Bad Setup")
else:
    st.warning("Risk tidak valid")

st.subheader("📈 Trend Score")
trend_score = 0
if price > data['SMA20'].iloc[-1]:
    trend_score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
    trend_score += 1
if data['RSI'].iloc[-1] > 50:
    trend_score += 1
st.write(f"Trend Score: {trend_score}/3")

st.subheader("🔥 Breakout Strength")
if price > resistance:
    strength = (price - resistance) / resistance * 100
    st.success(f"Breakout Strength: {strength:.2f}%")
else:
    st.write("No Breakout")

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

# ========== FINAL DECISION ==========
st.header("FINAL DECISION")
if score >= 4:
    st.success("🟢 ACCUMULATE")
elif score == 3:
    st.warning("🟡 WAIT")
else:
    st.error("🔴 AVOID")

# ========== GLOSSARY LENGKAP ==========
with st.expander("📖 GLOSSARY LENGKAP (Klik untuk lihat semua penjelasan)"):
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
    - Garis histogram menunjukkan kekuatan trend

    **4. Volume & Volume MA**
    - Volume: Jumlah saham yang diperdagangkan
    - Volume MA: Rata-rata volume 20 hari
    - Volume > MA(20)×1.8 = Volume Spike
    - Volume tinggi = Minat besar

    **5. Support & Resistance**
    - Support: Level harga terendah (area beli)
    - Resistance: Level harga tertinggi (area jual)
    - Support (20 periode): Low terendah 20 hari
    - Resistance (20 periode): High tertinggi 20 hari

    ### 🎯 SIGNAL & SCORING SYSTEMS
    **AI Score (0-5)**
    - +1: RSI < 35 (Oversold)
    - +1: Harga > SMA20
    - +1: SMA20 > SMA50 (Golden Cross)
    - +1: MACD > Signal
    - +1: Volume > Rata-rata
    - 4-5: STRONG BUY 🚀
    - 3: HOLD 🟡
    - 0-2: SELL 🔻

    **Probability Engine**
    - Menghitung peluang Bullish/Bearish
    - Bull > 60% = Potensi naik
    - Bear > 60% = Potensi turun

    **Trend Score (0-3)**
    - +1: Harga > SMA20
    - +1: SMA20 > SMA50 (Uptrend)
    - +1: RSI > 50 (Momentum positif)
    - 3: Strong Uptrend
    - 2: Moderate Uptrend
    - 1: Weak Trend

    **Risk Meter**
    - Volatilitas dari return harian
    - < 1.5% = LOW RISK ✅
    - 1.5-3% = MEDIUM RISK ⚠️
    - > 3% = HIGH RISK 🔴

    ### 🚀 TRADING SIGNALS
    **Breakout Signals**
    - Breakout: Harga > Resistance
    - Breakdown: Harga < Support
    - Breakout Strength: (Harga - Resistance)/Resistance × 100%
    - Strong breakout > 3%

    **Momentum Detector**
    - Change 5 hari terakhir × 100%
    - > 5%: Strong Up Momentum 🔥
    - 2-5%: Moderate Up Momentum 📈
    - -2 s/d 2%: Sideways ➡️
    - < -5%: Strong Down Momentum 📉

    **Risk Reward Ratio**
    - RR = (Target1 - Entry) / (Entry - Stop Loss)
    - RR > 2: Good Setup ✅
    - RR 1-2: Moderate Setup ⚠️
    - RR < 1: Bad Setup 🔴

    **Volume Spike Alert**
    - Volume > MA(20) × 1.8
    - Menandakan minat institusi
    - Konfirmasi breakout lebih valid

    ### 🧠 GOD MODE COMPONENTS
    **Smart Entry**
    - Formula: (Support + Current Price) / 2
    - Entry di area support untuk safety
    - Menghindari FOMO

    **Stop Loss**
    - Formula: Support × 0.97
    - Stop loss 3% di bawah support
    - Proteksi modal maksimal -5-7%

    **Target Profit**
    - Target 1: Resistance level
    - Target 2: Resistance × 1.05 (+5%)
    - Ambil profit bertahap

    **God Score (0-4)**
    - +1: RR > 2
    - +1: Trend Score ≥ 2
    - +1: RSI < 70 (Tidak overbought)
    - +1: Harga > SMA20
    - 3-4: GOD MODE BUY 🚀
    - 2: SPEC BUY ⚡
    - 0-1: NO TRADE ❌

    ### 📈 MARKET SCANNER
    **IHSG Scanner Logic**
    - Memindai 15 saham blue chip IHSG
    - Filter: RSI oversold & Harga > SMA20
    - Score 0-2 untuk setiap saham
    - Top 5 saham dengan score tertinggi

    **Market Momentum**
    - Menghitung up/down days dalam 20 hari
    - Up days > Down days = Bullish market
    - Down days > Up days = Bearish market

    ### ⚠️ INTERPRETASI SCORE
    - **🔥 STRONG BUY (4-5)**: Semua indikator bullish, momentum kuat, risiko rendah-medium, cocok untuk entry.
    - **🟡 HOLD/WAIT (3)**: Indikator mixed, tunggu konfirmasi, perketat stop loss.
    - **🔴 SELL/AVOID (0-2)**: Indikator bearish, momentum turun, risiko tinggi, hindari entry baru.

    ### 💡 TIPS PENGGUNAAN
    1. **Multi-Timeframe**: Cek timeframe 1d, 1wk, 1mo untuk konfirmasi trend.
    2. **Konfirmasi**: Jangan hanya andalkan 1 indikator.
    3. **Risk Management**: Selalu gunakan stop loss (max 5-7%).
    4. **Volume Penting**: Breakout tanpa volume = false breakout.
    5. **Market Scanner**: Cek saham lain jika saham utama sedang bearish.
    6. **God Mode**: Gunakan untuk entry yang lebih akurat.
    7. **Probabilitas**: Bukan kepastian, selalu siap dengan skenario alternatif.
    """)

# ========== DISCLAIMER ==========
st.markdown("---")
st.caption("⚠️ **DISCLAIMER:** Dashboard ini hanya untuk edukasi dan analisis teknikal otomatis. Bukan rekomendasi beli/jual. Keputusan investasi sepenuhnya risiko Anda.")
