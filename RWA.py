import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go
from datetime import datetime

# --- 1. BASELINE: 11 CHIẾN MÃ 2026 (Mapping ID CoinGecko) ---
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'tw': 35, 'ath': 52.8},
        'ONDO': {'id': 'ondo-finance', 'tw': 20, 'ath': 2.14},
        'QNT': {'id': 'quant-network', 'tw': 15, 'ath': 428.0},
        'PENDLE': {'id': 'pendle', 'tw': 10, 'ath': 7.52},
        'SYRUP': {'id': 'maple', 'tw': 10, 'ath': 2.10},
        'CFG': {'id': 'centrifuge', 'tw': 10, 'ath': 2.59}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0},
        'SUI': {'id': 'sui', 'ath': 2.18},
        'FET': {'id': 'fetch-ai', 'ath': 3.48},
        'ARB': {'id': 'arbitrum', 'ath': 2.40},
        'PEPE': {'id': 'pepe', 'ath': 0.000017}
    }
}

# --- 2. HÀM TRỢ NĂNG ---
def get_crypto_data():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        return requests.get(url).json()
    except: return {}

def get_news():
    try:
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        return "<br>".join([f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in f.entries[:3]])
    except: return "⚠️ Connecting 24H News..."

@st.cache_resource
def get_gsheet():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    c = get_gsheet()
    ws = c.open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for col in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return ws, df

# --- 3. GIAO DIỆN ---
st.set_page_config(page_title="RWA Elite", layout="wide")
ws, df_h = load_data()
price_data = get_crypto_data()

with st.sidebar:
    st.header("🏢 MANAGER")
    budget = st.number_input("BUDGET ($)", value=2000.0)
    st.divider()
    coin_list = list(STRATEGY['RWA'].keys()) + list(STRATEGY['HUNTER'].keys())
    c_sel = st.selectbox("Update", coin_list)
    with st.form("up"):
        q, p = st.number_input("Qty"), st.number_input("Price")
        if st.form_submit_button("UPDATE"):
            row = df_h[df_h['Coin'] == c_sel]
            if not row.empty:
                t_q = float(row['Holdings'].values[0]) + q
                a_e = ((float(row['Holdings'].values[0])*float(row['Entry_Price'].values[0]))+(q*p))/t_q
                ws.update(f"B{ws.find(c_sel).row}:C{ws.find(c_sel).row}", [[t_q, a_e]])
            else: ws.append_row([c_sel, q, p, 0])
            st.rerun()

st.markdown(f"""<div style="background:#161b22;padding:15px;border-radius:15px;border:1px solid #30363d;margin-bottom:20px;">{get_news()}</div>""", unsafe_allow_html=True)

# PROCESS DATA
total_v, total_i, total_r = 0, 0, float(df_h['Profit_Realized'].sum())
tabs_data = {'RWA': [], 'HUNTER': []}
p_labels, p_values = [], []

for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cg_id = info['id']
        cp = price_data.get(cg_id, {}).get('usd', 0)
        pnl_24h = price_data.get(cg_id, {}).get('usd_24h_change', 0)
        
        u_row = df_h[df_h['Coin'] == name]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        pnl_hold = ((cp/e)-1)*100 if e > 0 else 0
        
        # MÔ PHỎNG CHỈ SỐ KỸ THUẬT (Vì API Free không trả về History)
        stt, col = ("STRONG BUY", "#3fb950") if pnl_24h < -5 else ("OBSERVE", "#8b949e")
        rs = f"24H Change: {pnl_24h:+.1f}% | Trend: {'Bullish' if pnl_24h > 0 else 'Sideways'}"
        
        val, inv = h * cp, h * e
        total_v += val; total_i += inv
        
        card = {"name": name, "cp": cp, "stt": stt, "col": col, "rs": rs, "inv": inv, "e": e, "pnl": pnl_hold, "sup": cp*0.92, "res": cp*1.12, "ath": info['ath'], "eff": (pnl_hold/15 if h > 0 else 0)}
        if val > 0: p_labels.append(name); p_values.append(val)
        
        if cat == 'RWA':
            card.update({"tw": info['tw'], "rw": (val/budget*100), "fill": min((val/budget*100)/info['tw'], 1.0)*100})
        tabs_data[cat].append(card)

# DASHBOARD
cash = budget - total_i + total_r
c1, c2 = st.columns([3, 1.2])
with c1:
    html = f"""<div style="display:flex;gap:15px;margin-bottom:15px;"><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">CASH</div><div style="color:#58a6ff;font-size:32px;font-weight:900;">${cash:,.0f}</div></div><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">PnL</div><div style="color:#3fb950;font-size:32px;font-weight:900;">${(total_v-total_i):,.0f}</div></div></div><div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">TOTAL ASSET</div><div style="color:white;font-size:42px;font-weight:900;">${(total_v + cash):,.0f}</div></div>"""
    components.html(html, height=320)
with c2:
    p_labels.append("CASH"); p_values.append(max(0, cash))
    fig = go.Figure(data=[go.Pie(labels=p_labels, values=p_values, hole=.5)])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=300, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

t1, t2 = st.tabs(["🛡️ STRATEGIC RWA", "🔍 HUNTER SCANNER"])
def render(data, is_rwa):
    for d in data:
        eff_c = "#3fb950" if d['eff'] > 1.5 else "#8b949e"
        prog = f"""<div style="font-size:11px;color:#8b949e;margin-bottom:5px;">WEIGHT: {d['rw']:.1f}% / {d['tw']}% | <span style="color:{eff_c}">EFF: {d['eff']:.1f}</span></div><div style="background:#30363d;height:6px;border-radius:10px;"><div style="background:#1f6feb;height:100%;width:{d['fill']}%;border-radius:10px;"></div></div>""" if is_rwa else f"""<div style="font-size:11px;color:{eff_c};margin-bottom:5px;">EFFICIENCY SCORE: {d['eff']:.1f}</div>"""
        card_html = f"""<div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;color:white;margin-bottom:15px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:32px;font-weight:900;color:#58a6ff;">{d['name']}</div>{prog}</div><div style="text-align:right;"><div style="font-size:38px;font-weight:900;">${d['cp']:.4f}</div><div style="color:#3fb950;font-size:18px;">{d['pnl']:+.1f}%</div></div></div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;text-align:center;margin-top:20px;background:rgba(0,0,0,0.2);padding:15px;border-radius:15px;"><div><div style="font-size:8px;color:#8b949e;">INVEST</div><div style="font-size:12px;font-weight:700;">${d['inv']:,.0f}</div></div><div><div style="font-size:8px;color:#8b949e;">AVG</div><div style="font-size:12px;font-weight:700;">${d['e']:.3f}</div></div><div><div style="font-size:8px;color:#8b949e;">SUPP</div><div style="font-size:12px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div><div><div style="font-size:8px;color:#8b949e;">RESIST</div><div style="font-size:12px;font-weight:700;color:#f85149;">${d['res']:.3f}</div></div><div><div style="font-size:8px;color:#8b949e;">ATH</div><div style="font-size:12px;font-weight:700;">${d['ath']:.2f}</div></div><div><div style="font-size:8px;color:#8b949e;">TP1</div><div style="font-size:12px;font-weight:700;color:#3fb950;">${d['cp']*1.5:.2f}</div></div><div><div style="font-size:8px;color:#8b949e;">TP2</div><div style="font-size:12px;font-weight:700;color:#d29922;">${d['cp']*2:.2f}</div></div></div><div style="margin-top:15px;padding:12px;border-left:6px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;">{d['stt']}<br><span style="font-size:11px;font-weight:400;color:#f0f6fc;">{d['rs']}</span></div></div>"""
        components.html(card_html, height=380)

with t1: render(tabs_data['RWA'], True)
with t2: render(tabs_data['HUNTER'], False)
