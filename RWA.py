import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

# --- CHIẾN LƯỢC CHI TIẾT ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- KẾT NỐI ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open("TMC-Sales-Assistant")
    ws = sh.worksheet("Holdings")
    return ws, pd.DataFrame(ws.get_all_records())

def get_levels(symbol, days):
    hist = yf.download(symbol, period=f"{days}d", progress=False)
    if hist.empty: return 0.0, 0.0
    return float(hist['Low'].min()), float(hist['High'].max())

# --- GIAO DIỆN ---
st.set_page_config(page_title="RWA Intelligence Terminal", layout="wide")

# CSS tạo giao diện hiện đại
st.markdown("""
    <style>
    .asset-card {
        background: #111421; padding: 20px; border-radius: 15px; 
        border: 1px solid #2d3142; margin-bottom: 15px;
    }
    .recommendation-box {
        padding: 10px; border-radius: 8px; font-weight: bold; margin-top: 10px; border-left: 5px solid;
    }
    .data-label { color: #858796; font-size: 11px; text-transform: uppercase; }
    .data-value { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("🛒 Lệnh Mua DCA")
        with st.form("dca"):
            c_sel = st.selectbox("Đồng coin", list(RWA_STRATEGY.keys()))
            q_add = st.number_input("Số lượng mua", min_value=0.0)
            p_add = st.number_input("Giá lúc mua ($)", min_value=0.0)
            if st.form_submit_button("CẬP NHẬT TÀI SẢN"):
                row = df_holdings[df_holdings['Coin'] == c_sel]
                old_q = float(row['Holdings'].values[0]) if not row.empty else 0
                old_e = float(row['Entry_Price'].values[0]) if not row.empty else 0
                new_q = old_q + q_add
                new_e = ((old_q * old_e) + (q_add * p_add)) / new_q
                if not row.empty:
                    ws.update(f"B{ws.find(c_sel).row}:C{ws.find(c_sel).row}", [[new_q, new_e]])
                else:
                    ws.append_row([c_sel, new_q, new_e])
                st.rerun()
        
        st.divider()
        days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

    # LẤY GIÁ & XỬ LÝ
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_STRATEGY.values()]))
    processed = []
    total_val, total_invest = 0, 0

    for coin, cfg in RWA_STRATEGY.items():
        cp = tickers.tickers[cfg['symbol']].fast_info['last_price']
        sup, res = get_levels(cfg['symbol'], days_sel)
        u = df_holdings[df_holdings['Coin'] == coin]
        h = float(u['Holdings'].values[0]) if not u.empty else 0.0
        e = float(u['Entry_Price'].values[0]) if not u.empty else 0.0
        
        val = cp * h
        total_val += val
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0
        
        # LOGIC TƯ VẤN (REASONING)
        if cp <= sup * 1.02: 
            rec, rec_c, reason = "NÊN MUA MẠNH", "#28a745", f"Giá sát Hỗ trợ {days_sel}d (${sup:.3f})"
        elif cfg['v2'][0] <= cp <= cfg['v2'][1]:
            rec, rec_c, reason = "GOM VÙNG 2", "#1cc88a", "Giá nằm trong vùng gom chiến lược 2"
        elif cfg['v1'][0] <= cp <= cfg['v1'][1]:
            rec, rec_c, reason = "GOM VÙNG 1", "#f6c23e", "Giá nằm trong vùng gom chiến lược 1"
        elif cp >= res * 0.98:
            rec, rec_c, reason = "TẠM DỪNG / BÁN", "#dc3545", f"Giá sát Kháng cự {days_sel}d (${res:.3f})"
        else:
            rec, rec_c, reason = "QUAN SÁT THÊM", "#858796", "Giá đang ở vùng trung lập, chưa có tín hiệu đẹp"

        processed.append({
            "coin": coin, "cp": cp, "val": val, "h": h, "e": e, "pnl": pnl, 
            "rec": rec, "rec_c": rec_c, "reason": reason, "ath": cfg['ath'],
            "sup": sup, "res": res, "tw": cfg['target_w'], "v1": cfg['v1'], "v2": cfg['v2']
        })

    # UI CHÍNH
    st.title("🛡️ RWA Intelligence Terminal")
    st.caption(f"Chào anh Công. Dữ liệu tính toán dựa trên khung kỹ thuật {days_sel} ngày.")

    m1, m2, m3 = st.columns(3)
    m1.metric("TỔNG GIÁ TRỊ TÀI SẢN", f"${total_val:,.2f}")
    m2.metric("LỢI NHUẬN THỰC TẾ", f"${(total_val - total_invest):,.2f}", f"{((total_val/total_invest)-1)*100 if total_invest > 0 else 0:.1f}%")
    m3.metric("VỐN ĐÃ ĐẦU TƯ", f"${total_invest:,.2f}")

    st.divider()

    c_left, c_right = st.columns([2, 1])

    with c_left:
        for d in processed:
            st.markdown(f"""
            <div class="asset-card">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2d3142; padding-bottom: 10px; margin-bottom: 15px;">
                    <span style="font-size: 22px; font-weight: bold; color: #4e73df;">{d['coin']}</span>
                    <span style="font-size: 18px; font-weight: bold;">${d['cp']:.3f}</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
                    <div><div class="data-label">Vốn Avg</div><div class="data-value">${d['e']:.3f}</div></div>
                    <div><div class="data-label">🛡️ Hỗ trợ ({days_sel}d)</div><div class="data-value" style="color:#28a745">${d['sup']:.3f}</div></div>
                    <div><div class="data-label">⛔ Kháng cự ({days_sel}d)</div><div class="data-value" style="color:#dc3545">${d['res']:.3f}</div></div>
                    <div><div class="data-label">Đỉnh ATH</div><div class="data-value" style="color:#f6c23e">${d['ath']}</div></div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 15px;">
                    <div><div class="data-label">Vùng Gom 1</div><div style="font-size:14px"><b>{d['v1'][0]} - {d['v1'][1]}</b></div></div>
                    <div><div class="data-label">Vùng Gom 2</div><div style="font-size:14px"><b>{d['v2'][0]} - {d['v2'][1]}</b></div></div>
                </div>
                <div class="recommendation-box" style="border-left-color: {d['rec_c']}; background: {d['rec_c']}15; color: {d['rec_c']};">
                    TRẠNG THÁI: {d['rec']} <br>
                    <span style="font-size: 12px; font-weight: normal; color: #ffffff;">Lý do: {d['reason']}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 15px; font-size: 14px;">
                    <span>Tài sản: <b>${d['val']:,.2f}</b></span>
                    <span style="color:{'#28a745' if d['pnl']>=0 else '#dc3545'}">P&L: <b>{d['pnl']:.1f}%</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with c_right:
        st.subheader("⚖️ Tỷ Trọng & Kỷ Luật")
        # Donut Chart
        fig = go.Figure(data=[go.Pie(labels=[d['coin'] for d in processed], values=[d['val'] for d in processed], hole=.5)])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**Kiểm soát Tỷ trọng Mục tiêu**")
        for d in processed:
            real_w = (d['val']/total_val*100) if total_val > 0 else 0
            st.write(f"{d['coin']} (Thực tế: {real_w:.1f}% / Mục tiêu: {d['tw']}%)")
            st.progress(min(real_w/d['tw'], 1.0) if d['tw'] > 0 else 0)

except Exception as e:
    st.error(f"Lỗi: {e}")
