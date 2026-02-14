import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

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

# --- KẾT NỐI AN TOÀN ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open(ST_FILE_NAME)
    try:
        ws = sh.worksheet(ST_SHEET_NAME)
    except:
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

st.markdown("""
    <style>
    .asset-card { background: #111421; padding: 22px; border-radius: 18px; border: 1px solid #2d3142; margin-bottom: 20px; }
    .rec-box { padding: 12px; border-radius: 10px; font-weight: bold; margin-top: 15px; border-left: 6px solid; }
    .data-label { color: #858796; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
    .data-value { font-size: 19px; font-weight: bold; color: #fff; margin-top: 4px; }
    .target-bar-bg { background: #2d3142; border-radius: 10px; height: 8px; width: 100%; margin: 10px 0; }
    .target-bar-fill { background: #4e73df; height: 8px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("🏢 Quản trị Danh mục")
        with st.form("dca"):
            c_sel = st.selectbox("Chọn Coin", list(RWA_STRATEGY.keys()))
            q_add = st.number_input("Số lượng mua thêm", min_value=0.0)
            p_add = st.number_input("Giá mua ($)", min_value=0.0)
            if st.form_submit_button("XÁC NHẬN CẬP NHẬT"):
                row = df_holdings[df_holdings['Coin'] == c_sel]
                old_q = float(row['Holdings'].values[0]) if not row.empty else 0
                old_e = float(row['Entry_Price'].values[0]) if not row.empty else 0
                new_q = old_q + q_add
                new_e = ((old_q * old_e) + (q_add * p_add)) / new_q if new_q > 0 else 0
                if not row.empty:
                    cell = ws.find(c_sel)
                    ws.update(f"B{cell.row}:C{cell.row}", [[new_q, new_e]])
                else: ws.append_row([c_sel, new_q, new_e])
                st.rerun()
        days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

    # XỬ LÝ DỮ LIỆU CHÍNH
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_STRATEGY.values()]))
    processed = []
    total_val, total_invest = 0, 0

    # Tính tổng tài sản trước để lấy tỷ trọng thực tế
    for coin, cfg in RWA_STRATEGY.items():
        try: cp = float(tickers.tickers[cfg['symbol']].fast_info['last_price'])
        except: cp = 0.0
        h = float(df_holdings[df_holdings['Coin'] == coin]['Holdings'].values[0]) if not df_holdings[df_holdings['Coin'] == coin].empty else 0.0
        total_val += (cp * h)

    for coin, cfg in RWA_STRATEGY.items():
        try: cp = float(tickers.tickers[cfg['symbol']].fast_info['last_price'])
        except: cp = 0.0
        sup, res = get_levels(cfg['symbol'], days_sel)
        user_row = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        h, e = (float(user_row['Holdings'].values[0]), float(user_row['Entry_Price'].values[0])) if not user_row.empty else (0.0, 0.0)
        
        val = cp * h
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0
        real_w = (val / total_val * 100) if total_val > 0 else 0
        fill_pct = min(real_w / cfg['target_w'], 1.0) * 100

        # LOGIC TƯ VẤN (Tâm lý học hành vi + Kỹ thuật)
        if cp > 0:
            if cp <= sup * 1.02: rec, col, reason = "NÊN MUA MẠNH", "#28a745", f"Giá sát Hỗ trợ cứng {days_sel}d (${sup:.3f})."
            elif cfg['v2'][0] <= cp <= cfg['v2'][1]: rec, col, reason = "VÙNG GOM 2", "#1cc88a", "Giá cực tốt, nằm trong vùng gom chiến lược 2."
            elif cfg['v1'][0] <= cp <= cfg['v1'][1]: rec, col, reason = "VÙNG GOM 1", "#f6c23e", "Giá hợp lý, nằm trong vùng gom chiến lược 1."
            elif cp >= res * 0.98: rec, col, reason = "QUÁ MUA - ĐỢI", "#dc3545", f"Giá sát Kháng cự {days_sel}d (${res:.3f}). Chưa nên vào."
            else: rec, col, reason = "QUAN SÁT", "#858796", "Giá đang ở vùng trung lập, chưa có tín hiệu rõ ràng."
        else: rec, col, reason = "ĐANG TẢI...", "#3e4259", "Đang kết nối sàn dữ liệu..."

        processed.append({
            "coin": coin, "cp": cp, "val": val, "h": h, "e": e, "pnl": pnl, 
            "rec": rec, "col": col, "reason": reason, "ath": cfg['ath'],
            "sup": sup, "res": res, "tw": cfg['target_w'], "rw": real_w, "fill": fill_pct
        })

    # UI CHÍNH
    st.title("🛡️ RWA Intelligence Terminal")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("TỔNG TÀI SẢN (USDT)", f"${total_val:,.2f}")
    c2.metric("P&L TỔNG", f"${(total_val - total_invest):,.2f}", f"{((total_val/total_invest)-1)*100 if total_invest > 0 else 0:.1f}%")
    c3.metric("TRẠNG THÁI THỊ TRƯỜNG", f"Khung {days_sel}D")

    st.divider()

    l_col, r_col = st.columns([2, 1])

    with l_col:
        for d in processed:
            st.markdown(f"""
            <div class="asset-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="font-size: 24px; font-weight: bold; color: #4e73df;">{d['coin']}</span>
                        <div style="font-size: 12px; color: #858796; margin-top: 4px;">
                            Tỷ trọng: {d['rw']:.1f}% / Mục tiêu: {d['tw']}%
                        </div>
                        <div class="target-bar-bg"><div class="target-bar-fill" style="width: {d['fill']}%;"></div></div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 20px; font-weight: bold;">${d['cp']:.3f}</div>
                        <div style="color:{'#28a745' if d['pnl']>=0 else '#dc3545'}; font-size: 14px; font-weight: bold;">P&L: {d['pnl']:.1f}%</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 20px; text-align: center;">
                    <div><div class="data-label">Vốn Avg</div><div class="data-value">${d['e']:.3f}</div></div>
                    <div><div class="data-label">🛡️ Hỗ trợ</div><div class="data-value" style="color:#28a745">${d['sup']:.3f}</div></div>
                    <div><div class="data-label">⛔ Kháng cự</div><div class="data-value" style="color:#dc3545">${d['res']:.3f}</div></div>
                    <div><div class="data-label">Đỉnh ATH</div><div class="data-value" style="color:#f6c23e">${d['ath']}</div></div>
                </div>
                <div class="rec-box" style="border-left-color: {d['col']}; background: {d['col']}15; color: {d['col']};">
                    KHUYẾN NGHỊ: {d['rec']} <br>
                    <span style="font-size: 13px; font-weight: normal; color: #fff;">Lý do: {d['reason']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with r_col:
        st.subheader("⚖️ Cấu trúc Danh mục")
        fig = go.Figure(data=[go.Pie(labels=[d['coin'] for d in processed], values=[d['val'] for d in processed], hole=.6)])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="#fff"))
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"💡 Hệ thống đang đối chiếu dữ liệu Real-time của {len(RWA_STRATEGY)} mã RWA chiến lược để đưa ra khuyến nghị.")

except Exception as e:
    st.info("Chào anh Công! Hãy nhập lệnh DCA đầu tiên ở bên trái để kích hoạt hệ thống.")
