import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import streamlit.components.v1 as components

# --- HÀM TÍNH TOÁN CHỈ SỐ KỸ THUẬT ---
def calculate_metrics(df):
    # 1. Tính RSI (14 ngày)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 2. Tính Volume Ratio (So với trung bình 10 ngày)
    avg_vol = df['Volume'].rolling(window=10).mean()
    vol_ratio = df['Volume'] / avg_vol
    
    return rsi.iloc[-1], vol_ratio.iloc[-1]

def get_pro_analysis(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="60d") # Lấy 60 ngày để tính RSI
        if df.empty: return None
        
        cp = df['Close'].iloc[-1]
        rsi, vol_ratio = calculate_metrics(df)
        sup = float(df['Low'].rolling(window=30).min().iloc[-1])
        res = float(df['High'].rolling(window=30).max().iloc[-1])
        ath = float(df['High'].max())
        
        # LOGIC QUYẾT ĐỊNH (MANAGER LOGIC)
        dist_sup = ((cp / sup) - 1) * 100
        
        if rsi < 35 and dist_sup < 5:
            state, col, reason = "🎯 MUA MẠNH NHẤT", "#3fb950", f"Hội tụ: RSI thấp ({rsi:.1f}) + Sát Hỗ trợ ({dist_sup:.1f}%). Vùng giá cực an toàn."
        elif rsi < 45 and vol_ratio > 1.2:
            state, col, reason = "✅ MUA TỐT", "#1f6feb", f"Dòng tiền vào mạnh (Vol x{vol_ratio:.1f}) + Giá đang hồi phục từ vùng thấp."
        elif rsi > 70:
            state, col, reason = "⚠️ QUÁ MUA - ĐỨNG NGOÀI", "#f85149", f"Thị trường quá nóng (RSI: {rsi:.1f}). Rủi ro điều chỉnh rất cao."
        elif dist_sup < 3:
            state, col, reason = "⌛ QUAN SÁT SÁT", "#d29922", "Giá sát hỗ trợ nhưng RSI chưa đẹp. Chờ tín hiệu dòng tiền."
        else:
            state, col, reason = "😴 CHỜ ĐỢI", "#8b949e", "Giá đi ngang vùng trung lập. Chưa có biến động để giao dịch."
            
        return {
            "cp": cp, "rsi": rsi, "vol": vol_ratio, "sup": sup, "res": res, 
            "ath": ath, "state": state, "col": col, "reason": reason, "dist_sup": dist_sup
        }
    except: return None

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="Hunter Pro Terminal", layout="wide")

# (Giả sử anh đã chọn Tab 2 và có danh sách coin lạ từ Google Sheet)
# Ví dụ minh họa hiển thị Card cho Tab 2
st.title("🔍 MÁY QUÉT HUNTER - PHÂN TÍCH ĐỊNH LƯỢNG")

# Thử nghiệm với 1 đồng coin lạ (Ví dụ SOL)
coin_test = "SOL"
data = get_pro_analysis(f"{coin_test}-USD")

if data:
    html_card = f"""
    <div style="background: #0d1117; padding: 25px; border-radius: 20px; border: 2px solid {data['col']}; font-family: sans-serif; color: white;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div style="font-size: 40px; font-weight: 900; color: #58a6ff;">{coin_test} <span style="font-size: 16px; color: #8b949e;">(Hunter Mode)</span></div>
                <div style="margin-top: 10px; display: flex; gap: 15px;">
                    <div style="background: #21262d; padding: 5px 15px; border-radius: 10px; border: 1px solid #30363d;">
                        <span style="color: #8b949e; font-size: 12px;">RSI:</span> <span style="color: {'#3fb950' if data['rsi'] < 40 else '#f85149' if data['rsi'] > 70 else 'white'}; font-weight: 700;">{data['rsi']:.1f}</span>
                    </div>
                    <div style="background: #21262d; padding: 5px 15px; border-radius: 10px; border: 1px solid #30363d;">
                        <span style="color: #8b949e; font-size: 12px;">Vol Ratio:</span> <span style="color: white; font-weight: 700;">x{data['vol']:.1f}</span>
                    </div>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 48px; font-weight: 900; color: #ffffff;">${data['cp']:,.2f}</div>
                <div style="font-size: 14px; color: #8b949e;">Cách Hỗ trợ: <span style="color: #3fb950;">{data['dist_sup']:.1f}%</span></div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 25px; text-align: center;">
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px;">
                <div style="color: #8b949e; font-size: 11px;">HỖ TRỢ (30D)</div>
                <div style="font-size: 20px; font-weight: 700;">${data['sup']:,.2f}</div>
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px;">
                <div style="color: #8b949e; font-size: 11px;">KHÁNG CỰ (30D)</div>
                <div style="font-size: 20px; font-weight: 700;">${data['res']:,.2f}</div>
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px;">
                <div style="color: #8b949e; font-size: 11px;">ĐỈNH (ATH)</div>
                <div style="font-size: 20px; font-weight: 700;">${data['ath']:,.2f}</div>
            </div>
        </div>

        <div style="margin-top: 25px; padding: 20px; border-radius: 15px; background: {data['col']}20; border-left: 10px solid {data['col']};">
            <div style="color: {data['col']}; font-size: 22px; font-weight: 900; letter-spacing: 1px;">{data['state']}</div>
            <div style="color: #f0f6fc; font-size: 15px; margin-top: 8px; line-height: 1.4;">{data['reason']}</div>
        </div>
    </div>
    """
    components.html(html_card, height=420)
