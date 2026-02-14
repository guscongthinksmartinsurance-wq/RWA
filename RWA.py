import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# --- 1. KẾT NỐI DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    try:
        sh = client.open("TMC-Sales-Assistant")
        ws = sh.worksheet("Holdings")
    except:
        sh = client.open("TMC-Sales-Assistant")
        ws = sh.add_worksheet(title="Holdings", rows="100", cols="10")
        ws.append_row(["Coin", "Holdings", "Entry_Price"])
    data = ws.get_all_records()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=["Coin", "Holdings", "Entry_Price"])
    return ws, df

# --- 2. HÀM PHÂN TÍCH KỸ THUẬT CHUYÊN SÂU (HỘI TỤ 4 CHỈ SỐ) ---
def calculate_advanced_metrics(df, days_lookback=30):
    # 1. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    # 2. Volume Ratio
    avg_vol = df['Volume'].rolling(window=10).mean()
    vol_ratio = df['Volume'] / (avg_vol + 1e-10)
    
    # 3. Bollinger Bands (20, 2)
    ma20 = df['Close'].rolling(window=20).mean()
    std20 = df['Close'].rolling(window=20).std()
    upper_band = ma20 + (2 * std20)
    lower_band = ma20 - (2 * std20)
    
    # 4. Support/Resistance
    sup = df['Low'].rolling(window=days_lookback).min()
    res = df['High'].rolling(window=days_lookback).max()
    
    return {
        "rsi": rsi.iloc[-1],
        "vol": vol_ratio.iloc[-1],
        "lower": lower_band.iloc[-1],
        "upper": upper_band.iloc[-1],
        "sup": sup.iloc[-1],
        "res": res.iloc[-1]
    }

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("💰 QUẢN TRỊ VỐN")
        total_budget = st.number_input("TỔNG VỐN DỰ KIẾN ($)", min_value=1.0, value=2000.0)
        st.divider()
        st.header("🏢 TRẠM DCA")
        with st.form("dca"):
            # Danh sách coin top để anh search
            top_coins = sorted(list(set(["BTC", "ETH", "SOL", "LINK", "ONDO", "QNT", "PENDLE", "SYRUP", "CFG", "AVAX", "DOT", "NEAR", "TIA"] + df_holdings['Coin'].tolist())))
            c_sel = st.selectbox("Chọn Mã Coin", options=top_coins)
            q_add = st.number_input("Số lượng mua thêm", min_value=0.0)
            p_add = st.number_input("Giá mua ($)", min_value=0.0)
            if st.form_submit_button("XÁC NHẬN LỆNH"):
                row = df_holdings[df_holdings['Coin'] == c_sel]
                if not row.empty:
                    old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                    t_q = old_q + q_add
                    a_e = ((old_q * old_e) + (q_add * p_add)) / t_q if t_q > 0 else 0
                    cell = ws.find(c_sel)
                    ws.update(f"B{cell.row}:C{cell.row}", [[t_q, a_e]])
                else: ws.append_row([c_sel, q_add, p_add])
                st.rerun()
        days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

    # XỬ LÝ DỮ LIỆU THỊ TRƯỜNG REAL-TIME
    rwa_list = ['LINK', 'ONDO', 'QNT', 'PENDLE', 'SYRUP', 'CFG']
    all_coins = list(set(rwa_list + df_holdings['Coin'].tolist()))
    tickers = yf.Tickers(" ".join([f"{c}-USD" for c in all_coins if c]))
    
    total_val, total_invest = 0, 0
    display_data = []

    for coin in all_coins:
        if not coin: continue
        try:
            symbol = f"{coin}-USD"
            df_h = tickers.tickers[symbol].history(period="60d")
            cp = float(tickers.tickers[symbol].fast_info['last_price'])
            m = calculate_advanced_metrics(df_h, days_sel)
            
            u_row = df_holdings[df_holdings['Coin'] == coin]
            h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
            
            invested = h * e
            val = cp * h
            total_val += val
            total_invest += invested
            pnl = ((cp / e) - 1) * 100 if e > 0 else 0

            # --- LOGIC RA QUYẾT ĐỊNH DỰA TRÊN 4 CHỈ SỐ ---
            dist_sup = ((cp / m['sup']) - 1) * 100
            
            if (cp <= m['lower'] or m['rsi'] < 32) and dist_sup < 4:
                stt, col = "🎯 MUA MẠNH NHẤT", "#3fb950"
                rs = f"Hội tụ: Giá chạm dải Bollinger dưới (${m['lower']:.3f}), RSI quá bán ({m['rsi']:.1f}) và chỉ cách Hỗ trợ {dist_sup:.1f}%."
            elif dist_sup < 5 and m['vol'] > 1.2:
                stt, col = "✅ DCA THÊM TỐT", "#1f6feb"
                rs = f"Tín hiệu tốt: Dòng tiền vào mạnh (Vol x{m['vol']:.1f}) ngay sát vùng Hỗ trợ cứng ${m['sup']:.3f}."
            elif m['rsi'] > 70 or cp >= m['upper']:
                stt, col = "⚠️ QUÁ MUA - ĐỨNG NGOÀI", "#f85149"
                rs = f"Cảnh báo: RSI quá cao ({m['rsi']:.1f}) hoặc giá vượt dải Bollinger trên (${m['upper']:.3f}). Đợi điều chỉnh."
            elif dist_sup < 3:
                stt, col = "⌛ QUAN SÁT SÁT", "#d29922"
                rs = f"Giá sát Hỗ trợ ${m['sup']:.3f} nhưng lực mua chưa mạnh (RSI {m['rsi']:.1f}). Chờ xác nhận thêm."
            else:
                stt, col = "😴 TRUNG LẬP", "#8b949e"
                rs = f"Giá ổn định giữa Bollinger (${m['lower']:.2f} - ${m['upper']:.2f}). RSI {m['rsi']:.1f} chưa có biến động."

            display_data.append({
                "coin": coin, "cp": cp, "pnl": pnl, "invested": invested, "e": e, 
                "rsi": m['rsi'], "vol": m['vol'], "sup": m['sup'], "res": m['res'], 
                "stt": stt, "col": col, "rs": rs, "is_rwa": coin in rwa_list
            })
        except: continue

    # DASHBOARD TỔNG
    p_total = total_val - total_invest
    p_c = "#3fb950" if p_total >= 0 else "#f85149"
    dash_html = f"""<div style="display: flex; gap: 20px; margin-bottom: 20px; font-family: sans-serif;"><div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;"><div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Tiền Mặt Dự Trữ</div><div style="color: #58a6ff; font-size: 38px; font-weight: 900;">${(total_budget - total_invest):,.2f}</div></div><div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;"><div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">P&L Danh Mục</div><div style="color: {p_c}; font-size: 38px; font-weight: 900;">${p_total:,.2f}</div></div><div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;"><div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Tổng Tài Sản</div><div style="color: white; font-size: 38px; font-weight: 900;">${total_val:,.2f}</div></div></div>"""
    components.html(dash_html, height=160)

    t1, t2 = st.tabs(["🛡️ CHIẾN LƯỢC RWA", "🔍 MÁY QUÉT HUNTER"])

    def render_cards(data_list):
        for d in data_list:
            c_html = f"""
            <div style="background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; font-family: sans-serif; color: white; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <div>
                        <div style="font-size: 36px; font-weight: 900; color: #58a6ff;">{d['coin']}</div>
                        <div style="font-size: 14px; color: #8b949e; margin-top: 5px;">RSI: <b>{d['rsi']:.1f}</b> | Vol: <b>x{d['vol']:.1f}</b></div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 42px; font-weight: 900;">${d['cp']:.3f}</div>
                        <div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'}; font-size: 20px; font-weight: 800;">{d['pnl']:+.1f}%</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 15px;">
                    <div><div style="color:#8b949e; font-size:10px;">VỐN ĐÃ VÀO</div><div style="font-size:18px; font-weight:700; color:#58a6ff;">${d['invested']:,.2f}</div></div>
                    <div><div style="color:#8b949e; font-size:10px;">VỐN AVG</div><div style="font-size:18px; font-weight:700;">${d['e']:.3f}</div></div>
                    <div><div style="color:#8b949e; font-size:10px;">🛡️ HỖ TRỢ</div><div style="font-size:18px; font-weight:700; color:#3fb950;">${d['sup']:.3f}</div></div>
                    <div><div style="color:#8b949e; font-size:10px;">⛔ KHÁNG CỰ</div><div style="font-size:18px; font-weight:700; color:#f85149;">${d['res']:.3f}</div></div>
                </div>
                <div style="margin-top: 15px; padding: 15px; border-radius: 12px; border-left: 8px solid {d['col']}; background: {d['col']}15; color: {d['col']}; font-weight: 800; font-size: 16px;">
                    {d['stt']} <br><span style="font-size: 13px; font-weight: 400; color: #f0f6fc;">{d['rs']}</span>
                </div>
            </div>"""
            components.html(c_html, height=360)

    with t1: render_cards([d for d in display_data if d['is_rwa']])
    with t2: render_cards([d for d in display_data if not d['is_rwa']])

except Exception as e: st.error(f"Lỗi: {e}")
