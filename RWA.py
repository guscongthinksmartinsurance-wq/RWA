import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

# --- 1. CHIẾN LƯỢC GỐC ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"

RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- 2. KẾT NỐI ---
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
        ws.append_row(["Coin", "Holdings", "Entry_Price"])
    data = ws.get_all_records()
    return ws, pd.DataFrame(data) if data else pd.DataFrame(columns=["Coin", "Holdings", "Entry_Price"])

# --- 3. GIAO DIỆN ---
st.set_page_config(page_title="RWA Luxury Dashboard", layout="wide")

# CSS để xóa bỏ giao diện "phèn"
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #4e73df; }
    .coin-card {
        background-color: #1e2130; padding: 20px; border-radius: 15px;
        border: 1px solid #3e4259; margin-bottom: 15px;
    }
    .status-tag {
        padding: 3px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

try:
    sheet, df_holdings = load_data()
    
    # Sidebar DCA
    with st.sidebar:
        st.header("⚡ DCA Intelligence")
        with st.form("dca_form"):
            coin_sel = st.selectbox("Chọn Coin", list(RWA_STRATEGY.keys()))
            new_qty = st.number_input("Số lượng mua", min_value=0.0, step=0.1)
            new_prc = st.number_input("Giá mua ($)", min_value=0.0, step=0.01)
            if st.form_submit_button("XÁC NHẬN CỘNG DỒN"):
                user_row = df_holdings[df_holdings['Coin'] == coin_sel]
                if not user_row.empty:
                    old_q, old_e = float(user_row['Holdings'].values[0]), float(user_row['Entry_Price'].values[0])
                    total_q = old_q + new_qty
                    avg_e = ((old_q * old_e) + (new_qty * new_prc)) / total_q
                    cell = sheet.find(coin_sel)
                    sheet.update(f"B{cell.row}:C{cell.row}", [[total_q, avg_e]])
                else:
                    sheet.append_row([coin_sel, new_qty, new_prc])
                st.rerun()

    # Lấy giá & Tính toán
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_STRATEGY.values()]))
    total_val, total_invest = 0, 0
    processed_data = []

    for coin, cfg in RWA_STRATEGY.items():
        cp = tickers.tickers[cfg['symbol']].fast_info['last_price']
        user_row = df_holdings[df_holdings['Coin'] == coin]
        h = float(user_row['Holdings'].values[0]) if not user_row.empty else 0.0
        e = float(user_row['Entry_Price'].values[0]) if not user_row.empty else 0.0
        
        val = cp * h
        total_val += val
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0.0
        
        # Logic trạng thái
        if cfg['v2'][0] <= cp <= cfg['v2'][1]: st_txt, st_col = "VÙNG GOM 2", "#721c24"
        elif cfg['v1'][0] <= cp <= cfg['v1'][1]: st_txt, st_col = "VÙNG GOM 1", "#155724"
        else: st_txt, st_col = "QUAN SÁT", "#3e4259"

        processed_data.append({
            "coin": coin, "cp": cp, "val": val, "h": h, "e": e, 
            "pnl": pnl, "st": st_txt, "st_col": st_col, "target": cfg['target_w'], "ath": cfg['ath']
        })

    # HIỂN THỊ
    st.title("🛡️ RWA Iron Hand - Command Center")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("TỔNG TÀI SẢN (USDT)", f"${total_val:,.2f}")
    m2.metric("LỜI / LỖ TỔNG", f"${(total_val - total_invest):,.2f}", f"{((total_val/total_invest)-1)*100 if total_invest > 0 else 0:.1f}%")
    m3.metric("VỐN GIẢI NGÂN", f"${total_invest:,.2f}")

    st.divider()

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📡 Danh mục Tài sản")
        # Thay vì bảng Excel, ta dùng các Cards
        for d in processed_data:
            with st.container():
                st.markdown(f"""
                <div class="coin-card">
                    <table style="width:100%; border:none;">
                        <tr>
                            <td style="font-size:1.5rem; font-weight:bold; width:20%">{d['coin']}</td>
                            <td style="width:20%">Giá: <b>${d['cp']:.3f}</b></td>
                            <td style="width:20%">Vốn Avg: <b>${d['e']:.3f}</b></td>
                            <td style="width:20%; color:{'#28a745' if d['pnl']>=0 else '#dc3545'}">P&L: <b>{d['pnl']:.1f}%</b></td>
                            <td style="text-align:right"><span class="status-tag" style="background-color:{d['st_col']}">{d['st']}</span></td>
                        </tr>
                        <tr>
                            <td style="font-size:0.8rem; color:gray">ATH: ${d['ath']}</td>
                            <td style="font-size:0.8rem; color:gray">Vùng 1: {RWA_STRATEGY[d['coin']]['v1']}</td>
                            <td style="font-size:0.8rem; color:gray">Vùng 2: {RWA_STRATEGY[d['coin']]['v2']}</td>
                            <td colspan="2" style="text-align:right; font-size:1.1rem; font-weight:bold">Gia trị: ${d['val']:,.2f}</td>
                        </tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)

    with col_right:
        st.subheader("⚖️ Tỷ trọng Chiến lược")
        # Biểu đồ tròn so sánh Thực tế vs Mục tiêu
        fig = go.Figure(data=[go.Pie(
            labels=[d['coin'] for d in processed_data],
            values=[d['val'] for d in processed_data],
            hole=.4,
            marker=dict(colors=['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796'])
        )])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        
        # Bảng so sánh nhanh mục tiêu
        st.write("**Đối chiếu tỷ trọng (%)**")
        compare_df = pd.DataFrame([{
            "Coin": d['coin'], 
            "Thực tế": f"{(d['val']/total_val*100):.1f}%" if total_val > 0 else "0%",
            "Mục tiêu": f"{d['target']}%"
        } for d in processed_data])
        st.dataframe(compare_df, hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Lỗi: {e}")
