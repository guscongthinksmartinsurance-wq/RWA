import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# --- 1. CẤU HÌNH CHIẾN LƯỢC CỐ ĐỊNH (TAB 1) ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- 2. HÀM TỰ ĐỘNG LẤY DANH SÁCH 500 COIN ---
@st.cache_data(ttl=86400)
def get_top_500_tickers():
    # Danh sách mở rộng các mã phổ biến để anh search
    return sorted(["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "TRX", "LINK", "MATIC", "UNI", "LTC", "APT", "ARB", "OP", "NEAR", "TIA", "SEI", "INJ", "SUI", "FET", "RENDER", "ONDO", "PENDLE", "PYTH", "JUP", "GALA", "STX", "RNDR", "FIL"])

# --- 3. BỘ NÃO PHÂN TÍCH 4 CHỈ SỐ (RSI, VOL, BB, SUP) ---
def analyze_coin_logic(df, cp, days_sel):
    # a. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain/(loss + 1e-10))))
    rsi_val = rsi.iloc[-1]
    
    # b. Volume Ratio
    vol_ratio = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    
    # c. Bollinger Bands
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    lower_b = ma20 - (2 * std20)
    
    # d. Support/Resistance
    sup = float(df['Low'].rolling(window=days_sel).min().iloc[-1])
    res = float(df['High'].rolling(window=days_sel).max().iloc[-1])
    ath = float(df['High'].max())
    
    # --- CHẤM ĐIỂM HỘI TỤ ---
    dist_sup = ((cp / sup) - 1) * 100
    score = 0
    ok, missing = [], []

    if rsi_val < 35: score += 1; ok.append(f"RSI quá bán ({rsi_val:.1f})")
    else: missing.append(f"RSI ({rsi_val:.1f})")

    if cp <= lower_b: score += 1; ok.append("Chạm Bollinger dưới")
    else: missing.append(f"Cách BB dưới (${lower_b:.2f})")

    if dist_sup < 4: score += 1; ok.append(f"Sát Hỗ trợ ({dist_sup:.1f}%)")
    else: missing.append(f"Cách Hỗ trợ {dist_sup:.1f}%")

    if vol_ratio > 1.2: score += 1; ok.append(f"Vol tăng (x{vol_ratio:.1f})")
    else: missing.append(f"Vol thấp (x{vol_ratio:.1f})")

    if score >= 3: stt, col = "🎯 MUA MẠNH NHẤT", "#3fb950"
    elif score == 2: stt, col = "✅ MUA CÂN NHẮC", "#1f6feb"
    else: stt, col = "⌛ QUAN SÁT", "#8b949e"

    reason = f"✅ Đạt: {', '.join(ok) if ok else 'Chưa'} | ❌ Thiếu: {', '.join(missing)}"
    return rsi_val, vol_ratio, sup, res, ath, stt, col, reason

# --- 4. KẾT NỐI DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open("TMC-Sales-Assistant")
    try: ws = sh.worksheet("Holdings")
    except: ws = sh.add_worksheet(title="Holdings", rows="100", cols="10"); ws.append_row(["Coin", "Holdings", "Entry_Price"])
    df = pd.DataFrame(ws.get_all_records())
    if df.empty or 'Coin' not in df.columns: df = pd.DataFrame(columns=["Coin", "Holdings", "Entry_Price"])
    return ws, df

# --- 5. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()

with st.sidebar:
    st.header("💰 QUẢN TRỊ VỐN")
    budget = st.number_input("TỔNG VỐN DỰ KIẾN ($)", value=2000.0)
    st.divider()
    st.header("🏢 TRẠM DCA")
    with st.form("dca"):
        c_search = st.selectbox("Tìm mã Coin", get_top_500_tickers())
        c_custom = st.text_input("Hoặc nhập mã khác (VD: PEPE)")
        coin_final = c_custom.upper() if c_custom else c_search
        q_add = st.number_input("Số lượng", min_value=0.0)
        p_add = st.number_input("Giá mua ($)", min_value=0.0)
        if st.form_submit_button("CẬP NHẬT LỆNH"):
            row = df_holdings[df_holdings['Coin'] == coin_final]
            if not row.empty:
                old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                t_q = old_q + q_add
                a_e = ((old_q * old_e) + (q_add * p_add)) / t_q if t_q > 0 else 0
                cell = ws.find(coin_final)
                ws.update(f"B{cell.row}:C{cell.row}", [[t_q, a_e]])
            else: ws.append_row([coin_final, q_add, p_add])
            st.rerun()
    days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

# LẤY DỮ LIỆU THỊ TRƯỜNG
all_coins = list(set(list(RWA_STRATEGY.keys()) + df_holdings['Coin'].tolist()))
tickers = yf.Tickers(" ".join([f"{c}-USD" for c in all_coins if c]))
total_val, total_invest = 0, 0
tab1_cards, tab2_cards = [], []

for coin in all_coins:
    if not coin: continue
    try:
        symbol = f"{coin}-USD"
        df_h = tickers.tickers[symbol].history(period="60d")
        cp = float(tickers.tickers[symbol].fast_info['last_price'])
        rsi, vol, sup, res, ath, stt, col, rs = analyze_coin_logic(df_h, cp, days_sel)
        
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        invested = h * e
        total_val += (cp * h); total_invest += invested
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0
        
        card_data = {"coin": coin, "cp": cp, "rsi": rsi, "vol": vol, "sup": sup, "res": res, "ath": ath, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": pnl}
        
        if coin in RWA_STRATEGY:
            tw = RWA_STRATEGY[coin]['target_w']
            rw = (cp * h / budget * 100)
            card_data.update({"tw": tw, "rw": rw, "fill": min(rw/tw, 1.0)*100})
            tab1_cards.append(card_data)
        else: tab2_cards.append(card_data)
    except: continue

# DASHBOARD TỔNG (FIXED FLEXBOX)
pnl_total = total_val - total_invest
pnl_color = "#3fb950" if pnl_total >= 0 else "#f85149"
dash_html = f"""<div style="display:flex;gap:20px;font-family:sans-serif;"><div style="flex:1;background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Cash Còn Lại</div><div style="color:#58a6ff;font-size:38px;font-weight:900;margin-top:5px;">${(budget-total_invest):,.2f}</div></div><div style="flex:1;background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Lời / Lỗ</div><div style="color:{pnl_color};font-size:38px;font-weight:900;margin-top:5px;">${pnl_total:,.2f}</div></div><div style="flex:1;background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Tổng Tài Sản</div><div style="color:white;font-size:38px;font-weight:900;margin-top:5px;">${total_val:,.2f}</div></div></div>"""
components.html(dash_html, height=150)

t1, t2 = st.tabs(["🛡️ CHIẾN LƯỢC RWA", "🔍 MÁY QUÉT HUNTER"])
def render_ui(data, is_rwa):
    for d in data:
        header = f"""<div style="font-size:36px;font-weight:900;color:#58a6ff;">{d['coin']} {"" if is_rwa else "(Hunter)"}</div>"""
        progress = f"""<div style="font-size:14px;color:#8b949e;margin-top:8px;">Tiến độ: <b>{d['rw']:.1f}%</b> / {d['tw']}%</div><div style="background:#30363d;border-radius:20px;height:10px;width:100%;margin-top:10px;"><div style="background:#1f6feb;height:100%;border-radius:20px;width:{d['fill']}%;"></div></div>""" if is_rwa else ""
        html_card = f"""<div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;font-family:sans-serif;color:white;margin-bottom:20px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div>{header}{progress}</div><div style="text-align:right;"><div style="font-size:46px;font-weight:900;">${d['cp']:.3f}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:22px;font-weight:800;">{d['pnl']:+.1f}%</div></div></div><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;text-align:center;background:rgba(0,0,0,0.3);padding:20px;border-radius:15px;margin-top:20px;"><div><div style="color:#8b949e;font-size:10px;">VỐN VÀO</div><div style="font-size:18px;font-weight:700;color:#58a6ff;">${d['invested']:,.1f}</div></div><div><div style="color:#8b949e;font-size:10px;">VỐN AVG</div><div style="font-size:18px;font-weight:700;">${d['e']:.3f}</div></div><div><div style="color:#8b949e;font-size:10px;">🛡️ HỖ TRỢ</div><div style="font-size:18px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div><div><div style="color:#8b949e;font-size:10px;">⛔ KHÁNG CỰ</div><div style="font-size:18px;font-weight:700;color:#f85149;">${d['res']:.3f}</div></div><div><div style="color:#8b949e;font-size:10px;">🏆 ĐỈNH</div><div style="font-size:18px;font-weight:700;color:#d29922;">${d['ath']:.1f}</div></div></div><div style="margin-top:20px;padding:15px;border-radius:12px;border-left:8px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;font-size:16px;">{d['stt']}<br><span style="font-size:13px;font-weight:400;color:#f0f6fc;">{d['rs']}</span></div></div>"""
        components.html(html_card, height=410)

with t1: render_ui(tab1_cards, True)
with t2: render_ui(tab2_cards, False)
