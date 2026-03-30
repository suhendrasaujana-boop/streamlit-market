# Contoh untuk AI Score dengan tooltip
with st.expander("ℹ️ Tentang AI Score"):
    st.info("""
    **AI Score dihitung dari 5 komponen:**
    1. RSI < 35 (Oversold) → +1 poin
    2. Harga > SMA20 (Trend naik jangka pendek) → +1 poin  
    3. SMA20 > SMA50 (Golden cross) → +1 poin
    4. MACD > Signal (Momentum bullish) → +1 poin
    5. Volume > Rata-rata 20 hari (Minat tinggi) → +1 poin
    
    **Interpretasi:**
    - 4-5: Kondisi sangat bullish
    - 3: Netral, perlu konfirmasi
    - 0-2: Kondisi bearish
    """)

# Tampilkan AI Score dengan deskripsi
st.subheader("🤖 AI Score")
st.metric("Score", f"{score}/5")

# Tambahan breakdown
col_a, col_b, col_c, col_d, col_e = st.columns(5)
with col_a:
    st.caption(f"RSI: {'✅' if data['RSI'].iloc[-1] < 35 else '❌'}")
with col_b:
    st.caption(f"Harga > SMA20: {'✅' if data['Close'].iloc[-1] > data['SMA20'].iloc[-1] else '❌'}")
with col_c:
    st.caption(f"SMA20 > SMA50: {'✅' if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1] else '❌'}")
with col_d:
    st.caption(f"MACD > Signal: {'✅' if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1] else '❌'}")
with col_e:
    st.caption(f"Volume > MA: {'✅' if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1] else '❌'}")
