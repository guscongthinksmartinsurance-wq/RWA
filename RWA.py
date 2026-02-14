import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import requests
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. CHIẾN LƯỢC RWA ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

@st.cache_data(ttl=3600)
def get_fear_greed():
    try:
        r = requests.get('https://api.alternative.me/fng/').json()
        return r['data'][0]['value'], r['data'][0]['value_classification']
    except: return "50", "Neutral"

# --- 2. BỘ NÃO PHÂN TÍCH CHECKLIST ---
def analyze_checklist(df, cp, days_sel):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    lower_b, upper_b = ma20 - (2 * std20), ma20 + (2 * std20)
    sup = float(df['Low'].rolling(window=days_sel).min().iloc[-1])
    res = float(df['High'].rolling(window=days_sel).max().iloc[-1])
    
    score = 0
    checks = []
    
    # Check 4 chỉ số (Dùng icon Xanh/Đỏ)
    if rsi < 35: score += 1; checks.append(f"✅ RSI: {rsi:.1f}")
    else: checks.append(f"❌ RSI: {rsi:.1f}")
    
    if cp <= lower_b: score += 1; checks.append(f"✅ BB: Dưới biên (${lower_b:.2f})")
    else: checks.append(f"❌ BB: Cách biên dưới (${(cp-lower_b):.2f})")
    
    dist_s = ((cp/sup)-1)*100
    if dist_s < 4: score += 1; checks.append(f"✅ Support: Sát đáy (${sup:.2f})")
    else: checks.append(f"❌ Support: Cách {dist_s:.1f}%")
    
    if vol > 1.2: score += 1; checks.append(f"✅ Vol: Dòng tiền vào (x{vol:.1f})")
    else: checks.append(f"❌ Vol: Yếu (x{vol:.1f})")

    # Đề xuất trạng thái
    if cp >= upper_b * 0.98 or rsi > 70: stt, col = "🚀 ĐỀ XUẤT: BÁN / CHỐT LỜI", "#f85149"
    elif score >= 3: stt, col = "🛒 ĐỀ XUẤT: MUA MẠNH", "#3fb950"
    elif score == 2: stt, col = "🛡️ ĐỀ XUẤT: DCA THÊM", "#1f6feb"
    else: stt, col = "⌛ ĐỀ XUẤT: QUAN SÁT", "#8b949e"
    
    return rsi, vol, sup, res, stt, col, " | ".join(checks), float(df['High'].max())

# --- 3. DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open("TMC-Sales-Assistant")
    ws = sh.worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    return ws, df

# --- 4. GIAO DIỆN ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()
f_val, f_class = get_fear_greed()

with st.sidebar:
    st.header("🏢 QUẢN TRỊ")
    budget = st.number_input("TỔNG VỐN DỰ KIẾN ($)", value=2000.0)
    st.divider()
    # Sidebar gộp ô: Chọn mã hoặc gõ mã mới cùng lúc
    st.write("🏢 **TRẠM DCA**")
    c_list = sorted(list(set(["BTC", "ETH", "SOL", "LINK", "ONDO", "QNT", "PENDLE", "CFG"] + df_holdings['Coin'].tolist())))
    coin_input = st.selectbox("Chọn mã có sẵn", ["+ Nhập mã mới..."] + c_list)
    
    if coin_input == "+ Nhập mã mới...":
        final_coin = st.text_input("Nhập mã Coin mới (VD: PEPE)").upper()
    else:
        final_coin = coin_input

    with st.form("dca_fix"):
        q_add = st.number_input("Số lượng mua", min_value=0.0)
        p_add = st.number_input("Giá mua ($)", min_value=0.0)
        if st.form_submit_button("XÁC NHẬN CẬP NHẬT"):
            if final_coin:
                row = df_holdings[df_holdings['Coin'] == final_coin]
                if not row.empty:
                    old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                    t_q = old_q + q_add
                    a_e = ((old_q * old_e) + (q_add * p_add)) / t_q if t_q > 0 else 0
                    cell = ws.find(final_coin); ws.update(f"B{cell.row}:C{cell.row}", [[t_q, a_e]])
                else: ws.append_row([final_coin, q_add, p_add])
                st.rerun()
    
    days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)
    st.info(f"🎭 Tâm lý thị trường: {f_class} ({f_val}/100)")

# XỬ LÝ DỮ LIỆU THỊ TRƯỜNG
all_coins = list(set(list(RWA_STRATEGY.keys()) + df_holdings['Coin'].tolist()))
tickers = yf.Tickers(" ".join([f"{c}-USD" for c in all_coins if c]))
total_val, total_invest = 0, 0
tab1_data, tab2_data, p_labels, p_values = [], [], [], []

for coin in all_coins:
    if not coin: continue
    try:
        symbol = f"{coin}-USD"
        df_h = tickers.tickers[symbol].history(period="60d")
        cp = float(tickers.tickers[symbol].fast_info['last_price'])
        rsi, vol, sup, res, stt, col, rs, ath = analyze_checklist(df_h, cp, days_sel)
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        invested = h * e; val = cp * h
        total_val += val; total_invest += invested
        
        card = {"coin": coin, "cp": cp, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": ((cp/e)-1)*100 if e>0 else 0, "sup": sup, "res": res, "ath": ath}
        if val > 0: p_labels.append(coin); p_values.append(val)
        if coin in RWA_STRATEGY:
            tw = RWA_STRATEGY[coin]['target_w']
            card.update({"tw": tw, "rw": (val/budget*100), "fill": min((val/budget*100)/tw, 1.0)*100})
            tab1_data.append(card)
        else: tab2_data.append(card)
    except: continue

# --- DASHBOARD TỔNG (KHÔI PHỤC THIẾT KẾ ĐEN) ---
pnl_total = total_val - total_invest
p_labels.append("CASH"); p_values.append(max(0, budget - total_invest))

top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    dash_html = f"""
    <div style="display:flex;gap:15px;font-family:sans-serif;margin-bottom:15px;">
        <div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;">
            <div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Cash Còn Lại</div>
            <div style="color:#58a6ff;font-size:42px;font-weight:900;">${(budget-total_invest):,.2f}</div>
        </div>
        <div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;">
            <div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Lời / Lỗ</div>
            <div style="color:{'#3fb950' if pnl_total>=0 else '#f85149'};font-size:42px;font-weight:900;">${pnl_total:,.2f}</div>
        </div>
    </div>
    <div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;">
        <div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Tổng Giá Trị Tài Sản</div>
        <div style="color:white;font-size:48px;font-weight:900;">${total_val:,.2f}</div>
    </div>
    """
    components.html(dash_html, height=320)

with top_col2:
    fig = go.Figure(data=[go.Pie(labels=p_labels, values=p_values, hole=.5, textinfo='percent')])
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, font=dict(color="white"))
    st.plotly_chart(fig, use_container_width=True)

# --- TABS ---
t1, t2 = st.tabs(["🛡️ CHIẾN LƯỢC RWA", "🔍 MÁY QUÉT HUNTER"])
def render_master(data, is_rwa):
    for d in data:
        progress = f"""<div style="font-size:12px;color:#8b949e;margin-bottom:8px;">Tiến độ: <b>{d['rw']:.1f}%</b> / {d['tw']}%</div><div style="background:#30363d;border-radius:10px;height:8px;width:100%;"><div style="background:#1f6feb;height:100%;border-radius:10px;width:{d['fill']}%;"></div></div>""" if is_rwa else ""
        html = f"""
        <div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;font-family:sans-serif;color:white;margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="width:50%;"><div style="font-size:36px;font-weight:900;color:#58a6ff;">{d['coin']}</div>{progress}</div>
                <div style="text-align:right;"><div style="font-size:46px;font-weight:900;">${d['cp']:.3f}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:22px;font-weight:800;">{d['pnl']:+.1f}%</div></div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;text-align:center;background:rgba(0,0,0,0.3);padding:20px;border-radius:15px;margin-top:20px;">
                <div><div style="color:#8b949e;font-size:10px;">VỐN VÀO</div><div style="font-size:18px;font-weight:700;color:#58a6ff;">${d['invested']:,.0f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">VỐN AVG</div><div style="font-size:18px;font-weight:700;">${d['e']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">🛡️ HỖ TRỢ</div><div style="font-size:18px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">⛔ KHÁNG CỰ</div><div style="font-size:18px;font-weight:700;color:#f85149;">${d['res']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">🏆 ATH</div><div style="font-size:18px;font-weight:700;color:#d29922;">${d['ath']:.1f}</div></div>
            </div>
            <div style="margin-top:20px;padding:15px;border-radius:12px;border-left:8px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;font-size:18px;">
                {d['stt']}<br><span style="font-size:13px;font-weight:400;color:#f0f6fc;">{d['rs']}</span>
            </div>
        </div>"""
        components.html(html, height=410)

with t1: render_master(tab1_data, True)
with t2: render_master(tab2_data, False)
