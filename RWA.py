import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# --- 1. CHIẾN LƯỢC CHI TIẾT (TAB 1) ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"
HEADERS = ["Coin", "Holdings", "Entry_Price"]

RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- 2. HÀM KỸ THUẬT QUÁ BÁN/QUÁ MUA (TAB 2) ---
def calculate_metrics(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    avg_vol = df['Volume'].rolling(window=10).mean()
    vol_ratio = df['Volume'] / (avg_vol + 1e-10)
    return rsi.iloc[-1], vol_ratio.iloc[-1]

# --- 3. KẾT NỐI DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    try:
        sh = client.open(ST_FILE_NAME)
        ws = sh.worksheet(ST_SHEET_NAME)
    except Exception:
        sh = client.open(ST_FILE_NAME)
        ws = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="10")
        ws.append_row(HEADERS)
    data = ws.get_all_records()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=HEADERS)
    return ws, df

# --- 4. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("💰 QUẢN TRỊ VỐN")
        total_budget = st.number_input("TỔNG VỐN DỰ KIẾN ($)", min_value=1.0, value=2000.0)
        st.divider()
        st.header("🏢 TRẠM DCA")
        with st.form("dca"):
            c_sel = st.text_input("Mã Coin (VD: LINK, BTC, SOL)").upper()
            q_add = st.number_input("Số lượng mua", min_value=0.0)
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

    # LẤY DỮ LIỆU THỊ TRƯỜNG
    all_coins = list(set(list(RWA_STRATEGY.keys()) + df_holdings['Coin'].tolist()))
    tickers = yf.Tickers(" ".join([f"{c}-USD" for c in all_coins if c]))
    
    total_val, total_invest = 0, 0
    p1_data, p2_data = [], []

    for coin in all_coins:
        if not coin: continue
        try:
            symbol = f"{coin}-USD"
            df_h = tickers.tickers[symbol].history(period="60d")
            cp = float(tickers.tickers[symbol].fast_info['last_price'])
            
            u_row = df_holdings[df_holdings['Coin'] == coin]
            h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
            
            val = cp * h
            total_val += val
            total_invest += (e * h)
            pnl = ((cp / e) - 1) * 100 if e > 0 else 0
            
            if coin in RWA_STRATEGY:
                cfg = RWA_STRATEGY[coin]
                sup = float(df_h['Low'].rolling(window=days_sel).min().iloc[-1])
                res = float(df_h['High'].rolling(window=days_sel).max().iloc[-1])
                rw = (val / total_budget * 100)
                p1_data.append({"coin": coin, "cp": cp, "val": val, "e": e, "pnl": pnl, "sup": sup, "res": res, "tw": cfg['target_w'], "rw": rw, "v1": cfg['v1'], "v2": cfg['v2'], "ath": cfg['ath']})
            else:
                rsi, vol = calculate_metrics(df_h)
                s_h = float(df_h['Low'].rolling(window=days_sel).min().iloc[-1])
                r_h = float(df_h['High'].rolling(window=days_sel).max().iloc[-1])
                a_h = float(df_h['High'].max())
                p2_data.append({"coin": coin, "cp": cp, "rsi": rsi, "vol": vol, "sup": s_h, "res": r_h, "ath": a_h, "val": val, "pnl": pnl})
        except: continue

    # --- DASHBOARD TỔNG ---
    pnl_total = total_val - total_invest
    pnl_color = "#3fb950" if pnl_total >= 0 else "#f85149"
    dash_html = f"""
    <div style="display: flex; gap: 20px; margin-bottom: 20px; font-family: sans-serif;">
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Cash Còn Lại</div>
            <div style="color: #58a6ff; font-size: 38px; font-weight: 900;">${(total_budget - total_invest):,.2f}</div>
        </div>
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Lời / Lỗ Danh Mục</div>
            <div style="color: {pnl_color}; font-size: 38px; font-weight: 900;">${pnl_total:,.2f}</div>
        </div>
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Tổng Tài Sản</div>
            <div style="color: white; font-size: 38px; font-weight: 900;">${total_val:,.2f}</div>
        </div>
    </div>
    """
    components.html(dash_html, height=160)

    t1, t2 = st.tabs(["🛡️ CHIẾN LƯỢC RWA", "🔍 MÁY QUÉT HUNTER"])

    with t1:
        for d in p1_data:
            if d['cp'] <= d['sup'] * 1.02: rec, col, reason = "🎯 MUA MẠNH", "#3fb950", f"Chạm Hỗ trợ {days_sel}d (${d['sup']:.3f})"
            elif d['v2'][0] <= d['cp'] <= d['v2'][1]: rec, col, reason = "🔥 VÙNG GOM 2", "#3fb950", "Vùng gom chiến lược 2"
            elif d['v1'][0] <= d['cp'] <= d['v1'][1]: rec, col, reason = "✅ VÙNG GOM 1", "#d29922", "Vùng gom chiến lược 1"
            elif d['cp'] >= d['res'] * 0.98: rec, col, reason = "✋ TẠM DỪNG", "#f85149", f"Chạm Kháng cự {days_sel}d (${d['res']:.3f})"
            else: rec, col, reason = "⌛ QUAN SÁT", "#8b949e", "Giá vùng trung lập"

            fill = min(d['rw'] / d['tw'], 1.0) * 100
            c_html = f"""
            <div style="background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; font-family: sans-serif; color: white; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <div style="width: 55%;">
                        <div style="font-size: 36px; font-weight: 900; color: #58a6ff;">{d['coin']}</div>
                        <div style="font-size: 14px; color: #8b949e; margin-top: 8px;">Tiến độ: <b>{d['rw']:.1f}%</b> / {d['tw']}%</div>
                        <div style="background: #30363d; border-radius: 20px; height: 10px; width: 100%; margin-top: 10px;"><div style="background: #1f6feb; height: 100%; border-radius: 20px; width: {fill}%;"></div></div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 46px; font-weight: 900;">${d['cp']:.3f}</div>
                        <div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'}; font-size: 22px; font-weight: 800;">{d['pnl']:+.1f}%</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; text-align: center; background: rgba(0,0,0,0.3); padding: 20px; border-radius: 15px;">
                    <div><div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Vốn Avg</div><div style="font-size:22px; font-weight:700;">${d['e']:.3f}</div></div>
                    <div><div style="color:#8b949e; font-size:11px; text-transform:uppercase;">🛡️ Hỗ trợ</div><div style="font-size:22px; font-weight:700; color:#3fb950;">${d['sup']:.3f}</div></div>
                    <div><div style="color:#8b949e; font-size:11px; text-transform:uppercase;">⛔ Kháng cự</div><div style="font-size:22px; font-weight:700; color:#f85149;">${d['res']:.3f}</div></div>
                    <div><div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Đỉnh ATH</div><div style="font-size:22px; font-weight:700; color:#d29922;">${d['ath']}</div></div>
                </div>
                <div style="margin-top: 20px; padding: 15px; border-radius: 12px; border-left: 8px solid {col}; background: {col}15; color: {col}; font-weight: 800; font-size: 18px;">
                    PHÂN TÍCH: {rec} <br><span style="font-size: 14px; font-weight: 400; color: #f0f6fc;">Lý do: {reason}</span>
                </div>
            </div>"""
            components.html(c_html, height=410)

    with t2:
        for d in p2_data:
            dist_s = ((d['cp'] / d['sup']) - 1) * 100 if d['sup'] > 0 else 0
            if d['rsi'] < 35 and dist_s < 5: r_st, r_c, r_rs = "🎯 MUA MẠNH NHẤT", "#3fb950", f"Hội tụ RSI thấp ({d['rsi']:.1f}) + Sát Hỗ trợ"
            elif d['rsi'] > 70: r_st, r_c, r_rs = "✋ QUÁ MUA - ĐỨNG NGOÀI", "#f85149", f"Thị trường quá nóng (RSI: {d['rsi']:.1f})"
            else: r_st, r_c, r_rs = "⌛ CHỜ ĐỢI", "#8b949e", "Giá vùng trung lập, chưa có biến động mạnh"
            
            h_html = f"""
            <div style="background: #161b22; padding: 25px; border-radius: 20px; border: 2px solid {r_c}; font-family: sans-serif; color: white; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom:20px;">
                    <div><div style="font-size: 36px; font-weight: 900; color: #f6c23e;">{d['coin']} <span style="font-size: 14px; color: #8b949e;">(Hunter)</span></div>
                        <div style="margin-top: 10px; display: flex; gap: 10px;">
                            <div style="background: #21262d; padding: 5px 10px; border-radius: 8px; font-size: 12px;">RSI: <b style="color:{r_c}">{d['rsi']:.1f}</b></div>
                            <div style="background: #21262d; padding: 5px 10px; border-radius: 8px; font-size: 12px;">Vol: <b>x{d['vol']:.1f}</b></div>
                        </div>
                    </div>
                    <div style="text-align: right;"><div style="font-size: 46px; font-weight: 900;">${d['cp']:,.2f}</div></div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; text-align: center; background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px;">
                    <div><div style="color:#8b949e; font-size:11px;">HỖ TRỢ</div><div style="font-size:22px; font-weight:700; color:#3fb950;">${d['sup']:,.2f}</div></div>
                    <div><div style="color:#8b949e; font-size:11px;">KHÁNG CỰ</div><div style="font-size:22px; font-weight:700; color:#f85149;">${d['res']:,.2f}</div></div>
                    <div><div style="color:#8b949e; font-size:11px;">ĐỈNH ATH</div><div style="font-size:22px; font-weight:700; color:#d29922;">${d['ath']:,.2f}</div></div>
                </div>
                <div style="margin-top: 20px; padding: 15px; border-radius: 12px; border-left: 8px solid {r_c}; background: {r_c}15; color: {r_c}; font-weight: 800; font-size: 18px;">
                    TRẠNG THÁI: {r_st} <br><span style="font-size: 14px; font-weight: 400; color: #f0f6fc;">Lý do: {r_rs}</span>
                </div>
            </div>"""
            components.html(h_html, height=380)

except Exception as e: st.error(f"Lỗi: {e}")
