import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# --- CHIẾN LƯỢC CHI TIẾT ---
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

# --- KẾT NỐI DỮ LIỆU ---
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
    except:
        sh = client.open(ST_FILE_NAME)
        ws = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="10")
        ws.append_row(HEADERS)
    df = pd.DataFrame(ws.get_all_records())
    if df.empty or 'Coin' not in df.columns:
        df = pd.DataFrame(columns=HEADERS)
    return ws, df

def get_levels(symbol, days):
    try:
        hist = yf.download(symbol, period=f"{days}d", progress=False)
        if hist.empty: return 0.0, 0.0
        return float(hist['Low'].min()), float(hist['High'].max())
    except: return 0.0, 0.0

# --- GIAO DIỆN ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("💰 QUẢN TRỊ VỐN")
        total_budget = st.number_input("TỔNG VỐN CHIẾN DỊCH ($)", min_value=10.0, value=2000.0, step=100.0)
        
        st.divider()
        st.header("🏢 TRẠM DCA")
        with st.form("dca"):
            c_sel = st.selectbox("Chọn Coin", list(RWA_STRATEGY.keys()))
            q_add = st.number_input("Số lượng mua", min_value=0.0, step=0.1)
            p_add = st.number_input("Giá lúc mua ($)", min_value=0.0, step=0.01)
            if st.form_submit_button("GHI ĐÈ LỆNH MỚI"):
                row = df_holdings[df_holdings['Coin'] == c_sel]
                if not row.empty:
                    old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                    total_q = old_q + q_add
                    avg_e = ((old_q * old_e) + (q_add * p_add)) / total_q if total_q > 0 else 0
                    cell = ws.find(c_sel)
                    ws.update(f"B{cell.row}:C{cell.row}", [[total_q, avg_e]])
                else: ws.append_row([c_sel, q_add, p_add])
                st.rerun()
        days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

    # XỬ LÝ DỮ LIỆU
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_STRATEGY.values()]))
    total_val, total_invest = 0, 0
    processed = []

    for coin, cfg in RWA_STRATEGY.items():
        try: cp = float(tickers.tickers[cfg['symbol']].fast_info['last_price'])
        except: cp = 0.0
        user_row = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        h, e = (float(user_row['Holdings'].values[0]), float(user_row['Entry_Price'].values[0])) if not user_row.empty else (0.0, 0.0)
        
        val = cp * h
        total_val += val
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0
        sup, res = get_levels(cfg['symbol'], days_sel)
        
        # Tỷ trọng trên vốn dự kiến
        rw = (val / total_budget * 100)
        fill = min(rw / cfg['target_w'], 1.0) * 100

        # Khoảng cách so với Entry (DCA Gap)
        gap = ((cp / e) - 1) * 100 if e > 0 else 0

        if cp > 0:
            if cp <= sup * 1.02: rec, col, reason = "NÊN MUA MẠNH", "#3fb950", f"Chạm Hỗ trợ {days_sel}d (${sup:.3f})"
            elif cfg['v2'][0] <= cp <= cfg['v2'][1]: rec, col, reason = "VÙNG GOM 2", "#3fb950", "Vùng gom chiến lược 2"
            elif cfg['v1'][0] <= cp <= cfg['v1'][1]: rec, col, reason = "VÙNG GOM 1", "#d29922", "Vùng gom chiến lược 1"
            elif cp >= res * 0.98: rec, col, reason = "ĐỢI ĐIỀU CHỈNH", "#f85149", f"Sát Kháng cự {days_sel}d (${res:.3f})"
            else: rec, col, reason = "QUAN SÁT", "#8b949e", "Chưa có tín hiệu rõ ràng"
        else: rec, col, reason = "ĐANG TẢI", "#30363d", "Đang kết nối sàn..."

        processed.append({"coin": coin, "cp": cp, "val": val, "h": h, "e": e, "pnl": pnl, "gap": gap, "rec": rec, "col": col, "reason": reason, "ath": cfg['ath'], "sup": sup, "res": res, "tw": cfg['target_w'], "rw": rw, "fill": fill})

    # --- DASHBOARD TỔNG ---
    cash_left = total_budget - total_invest
    pnl_val = total_val - total_invest
    pnl_c = "#3fb950" if pnl_val >= 0 else "#f85149"

    header_html = f"""
    <div style="display: flex; gap: 15px; font-family: sans-serif; margin-bottom: 20px;">
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Tiền Mặt Còn Lại (Cash)</div>
            <div style="color: #58a6ff; font-size: 38px; font-weight: 900; margin-top: 5px;">${cash_left:,.2f}</div>
        </div>
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Lời / Lỗ Danh Mục</div>
            <div style="color: {pnl_c}; font-size: 38px; font-weight: 900; margin-top: 5px;">${pnl_val:,.2f}</div>
        </div>
        <div style="flex: 1; background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; text-align: center;">
            <div style="color: #8b949e; font-size: 12px; text-transform: uppercase;">Giá Trị Tài Sản</div>
            <div style="color: white; font-size: 38px; font-weight: 900; margin-top: 5px;">${total_val:,.2f}</div>
        </div>
    </div>
    """
    components.html(header_html, height=150)

    st.markdown("---")

    for d in processed:
        # Màu sắc cho GAP
        gap_info = f"Thấp hơn Entry: {abs(d['gap']):.1f}%" if d['gap'] < 0 else f"Cao hơn Entry: {d['gap']:.1f}%"
        gap_color = "#3fb950" if d['gap'] < 0 else "#8b949e"

        html_card = f"""
        <div style="background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; font-family: sans-serif; color: white; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div style="width: 55%;">
                    <div style="font-size: 36px; font-weight: 900; color: #58a6ff;">{d['coin']}</div>
                    <div style="font-size: 14px; color: #8b949e; margin-top: 8px;">Tỷ trọng mục tiêu: <b>{d['rw']:.2f}%</b> / {d['tw']}%</div>
                    <div style="background: #30363d; border-radius: 20px; height: 10px; width: 100%; margin-top: 10px;">
                        <div style="background: #1f6feb; height: 100%; border-radius: 20px; width: {d['fill']}%;"></div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 46px; font-weight: 900; color: #ffffff;">${d['cp']:.3f}</div>
                    <div style="color:{gap_color}; font-size: 16px; font-weight: 600;">{gap_info}</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; text-align: center; background: rgba(0,0,0,0.3); padding: 20px; border-radius: 15px;">
                <div><div style="color:#8b949e; font-size:11px;">Vốn Avg</div><div style="font-size:22px; font-weight:700;">${d['e']:.3f}</div></div>
                <div><div style="color:#8b949e; font-size:11px;">🛡️ Hỗ trợ</div><div style="font-size:22px; font-weight:700; color:#3fb950;">${d['sup']:.3f}</div></div>
                <div><div style="color:#8b949e; font-size:11px;">⛔ Kháng cự</div><div style="font-size:22px; font-weight:700; color:#f85149;">${d['res']:.3f}</div></div>
                <div><div style="color:#8b949e; font-size:11px;">Đỉnh ATH</div><div style="font-size:22px; font-weight:700; color:#d29922;">${d['ath']}</div></div>
            </div>
            <div style="margin-top: 20px; padding: 15px; border-radius: 12px; border-left: 8px solid {d['col']}; background: {d['col']}15; color: {d['col']}; font-weight: 800; font-size: 18px;">
                PHÂN TÍCH: {d['rec']} <br>
                <span style="font-size: 14px; font-weight: 400; color: #f0f6fc;">Lý do: {d['reason']}</span>
            </div>
        </div>
        """
        components.html(html_card, height=380)

except Exception as e:
    st.info("💡 Hệ thống đã sẵn sàng. Hãy nhập Tổng vốn đầu tư và lệnh đầu tiên.")
