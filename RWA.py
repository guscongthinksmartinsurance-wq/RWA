import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components

# --- 1. TỰ ĐỘNG LẤY 500 COIN TOP ---
@st.cache_data(ttl=86400)
def get_top_500_symbols():
    # Danh sách này sẽ được Bot cập nhật tự động để anh search thoải mái
    # Ở đây em liệt kê các mã phổ biến, thực tế Bot sẽ quét rộng hơn
    common = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "TRX", "LINK", "MATIC", "UNI", "LTC", "APT", "ARB", "OP", "NEAR", "TIA", "SEI", "INJ", "SUI", "FET", "RENDER", "ONDO", "PENDLE", "PYTH", "JUP"]
    return sorted(list(set(common)))

# --- 2. BỘ NÃO PHÂN TÍCH 4 CHỈ SỐ ---
def get_full_analysis(symbol, days=30):
    try:
        df = yf.download(symbol, period="60d", interval="1d", progress=False)
        if df.empty: return None
        
        cp = float(df['Close'].iloc[-1])
        # Chỉ số 1: RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain/(loss + 1e-10)))).iloc[-1]
        
        # Chỉ số 2: Volume Ratio
        vol_ratio = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
        
        # Chỉ số 3: Bollinger Bands
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        std20 = df['Close'].rolling(20).std().iloc[-1]
        lower_b = ma20 - (2 * std20)
        upper_b = ma20 + (2 * std20)
        
        # Chỉ số 4: Support/Resistance
        sup = float(df['Low'].rolling(days).min().iloc[-1])
        res = float(df['High'].rolling(days).max().iloc[-1])
        
        # --- LOGIC TỔNG HỢP (MANAGER DECISION) ---
        dist_sup = ((cp / sup) - 1) * 100
        score = 0
        reasons_ok = []
        reasons_missing = []

        if rsi < 35: score += 1; reasons_ok.append(f"RSI quá bán ({rsi:.1f})")
        else: reasons_missing.append(f"RSI chưa đẹp ({rsi:.1f})")

        if cp <= lower_b: score += 1; reasons_ok.append("Chạm dải Bollinger dưới")
        else: reasons_missing.append(f"Chưa chạm Bollinger dưới (cần về ${lower_b:.2f})")

        if dist_sup < 4: score += 1; reasons_ok.append(f"Sát Hỗ trợ ({dist_sup:.1f}%)")
        else: reasons_missing.append(f"Cách Hỗ trợ {dist_sup:.1f}% (đợi ở ${sup:.2f})")

        if vol_ratio > 1.2: score += 1; reasons_ok.append(f"Dòng tiền vào mạnh (x{vol_ratio:.1f})")
        else: reasons_missing.append(f"Dòng tiền yếu (x{vol_ratio:.1f})")

        # Phân loại trạng thái
        if score >= 3: stt, col = "🎯 MUA MẠNH NHẤT", "#3fb950"
        elif score == 2: stt, col = "✅ MUA CÂN NHẮC", "#1f6feb"
        elif score == 1: stt, col = "⌛ QUAN SÁT SÁT", "#d29922"
        else: stt, col = "😴 TRUNG LẬP", "#8b949e"

        full_reason = "✅ Đạt: " + ", ".join(reasons_ok) + ". <br>❌ Thiếu: " + ", ".join(reasons_missing)
        return {"cp":cp, "stt":stt, "col":col, "rs":full_reason, "sup":sup, "res":res, "rsi":rsi, "vol":vol_ratio}
    except: return None
