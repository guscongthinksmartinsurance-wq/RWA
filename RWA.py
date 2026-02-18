import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. BASELINE ---
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
@st.cache_data(ttl=300)
def get_all_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        return requests.get(url).json()
    except: return {}

def get_news():
    try:
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        return "<br>".join([f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in f.entries[:3]])
    except: return "⚠️ Connecting News..."

@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return ws, df

# --- 3. UI SETUP ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_h = load_data()
prices = get_all_prices()

with st.sidebar:
    st.header("🏢 MANAGEMENT")
    budget = st.number_input("TOTAL BUDGET ($)", value=2000.0)
    st.divider()
    c_sel = st.selectbox("Update", list(STRATEGY['RWA'].keys()) + list(STRATEGY['HUNTER'].keys()))
    with st.form("up_v20_2"):
        q, p = st.number_input("Qty"), st.number_input("Price")
        if st.form_submit_button("UPDATE"):
            row = df_h[df_h['Coin'] == c_sel]
            if not row.empty:
                t_q = float(row['Holdings'].values[0]) + q
                a_e = ((float(row['Holdings'].values[0])*float(row['Entry_Price'].values[0]))+(q*p))/t_q
                ws.update(f"B{ws.find(c_sel).row}:C{ws.find(c_sel).row}", [[t_q, a_e]])
            else: ws.append_row([c_sel, q, p, 0])
            st.rerun()

st.markdown(f"""<div style="background:#161b22;padding:15px;border-radius:15px;border:1px solid #30363d;margin-bottom:20px;"><div style="color:#8b949e;font-size:12px;font-weight:bold;">📰 24H INTELLIGENCE</div><div style="font-size:14px;line-height:1.6;">{get_news()}</div></div>""", unsafe_allow_html=True)

st.markdown("### 🎯 STRATEGY PERIOD")
days_sel = st.select_slider("Select Timeframe", options=[7, 30, 90, 365], value=30)

# PROCESS
total_v, total_i, total_realized = 0, 0, float(df_h['Profit_Realized'].sum())
tabs_d = {'RWA': [], 'HUNTER': []}
p_lab, p_val = [], []

for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cp = prices.get(info['id'], {}).get('usd', 0)
        ch = prices.get(info['id'], {}).get('usd_24h_change', 0)
        u_row = df_h[df_h['Coin'] == name]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        pnl = ((cp/e)-1)*100 if e > 0 else 0
        
        # Simple analysis for stability
        stt, col = ("STRONG BUY", "#3fb950") if ch < -5 else ("OBSERVE", "#8b949e")
        rs = f"24H: {ch:+.1f}% | RSI/BB: Scanning..."
        
        val = h * cp
        total_v += val; total_i += (h * e)
        if val > 0: p_lab.append(name); p_val.append(val)
        card = {"name": name, "cp": cp, "stt": stt, "col": col, "rs": rs, "inv": h*e, "e": e, "pnl": pnl, "ath": info['ath'], "eff": (pnl/10 if h > 0 else 0)}
        if cat == 'RWA': card.update({"tw": info['tw'], "rw": (val/budget*100), "fill": min((val/budget*100)/info['tw'], 1.0)*100})
        tabs_d[cat].append(card)

# DASHBOARD
cash = budget - total_i + total_realized
c1, c2 = st.columns([3, 1.2])
with c1:
    dash = f"""<div style="display:flex;gap:15px;margin-bottom:15px;"><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">CASH</div><div style="color:#58a6ff;font-size:32px;font-weight:900;">${cash:,.0f}</div></div><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">PnL</div><div style="color:{'#3fb950' if (total_v-total_i)>=0 else '#f85149'};font-size:32px;font-weight:900;">${(total_v-total_i):,.0f}</div></div></div><div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">TOTAL ASSET</div><div style="color:white;font-size:42px;font-weight:900;">${(total_v + cash):,.0f}</div></div>"""
    components.html(dash, height=320)
with c2:
    p_lab.append("CASH"); p_val.append(max(0, cash))
    fig = go.Figure(data=[go.Pie(labels=p_lab, values=p_val, hole=.5)])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=300, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER SCANNER"])
def render_ui(data, is_rwa):
    for d in data:
        p_fmt = f"{d['cp']:.7f}" if d['cp'] < 0.0001 else f"{d['cp']:.3f}"
        eff_c = "#3fb950" if d['eff'] > 1.5 else "#8b949e"
        prog = f"""<div style="font-size:11px;color:#8b949e;margin-bottom:5px;">WEIGHT: {d['rw']:.1f}% / {d['tw']}% | <span style="color:{eff_c}">EFF: {d['eff']:.1f}</span></div><div style="background:#30363d;height:6px;border-radius:10px;"><div style="background:#1f6feb;height:100%;width:{d['fill']}%;border-radius:10px;"></div></div>""" if is_rwa else f"""<div style="font-size:11px;color:{eff_c};margin-bottom:5px;">EFF SCORE: {d['eff']:.1f}</div>"""
        html = f"""<div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;color:white;margin-bottom:15px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:32px;font-weight:900;color:#58a6ff;">{d['name']}</div>{prog}</div><div style="text-align:right;"><div style="font-size:38px;font-weight:900;">${p_fmt}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:18px;">{d['pnl']:+.1f}%</div></div></div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;text-align:center;margin-top:20px;background:rgba(0,0,0,0.2);padding:15px;border-radius:15px;"><div><div style="font-size:8px;color:#8b949e;">INVESTED</div><div style="font-size:11px;font-weight:700;">${d['inv']:,.0f}</div></div><div><div style="font-size:8px;color:#8b949e;">AVG</div><div style="font-size:11px;font-weight:700;">${d['e']:.3f}</div></div><div><div style="font-size:8px;color:#8b949e;">SUPPORT</div><div style="font-size:11px;font-weight:700;color:#3fb950;">-</div></div><div><div style="font-size:8px;color:#8b949e;">RESIST</div><div style="font-size:11px;font-weight:700;color:#f85149;">-</div></div><div><div style="font-size:8px;color:#8b949e;">ATH</div><div style="font-size:11px;font-weight:700;">${d['ath']:.2f}</div></div><div><div style="font-size:8px;color:#8b949e;">TP1</div><div style="font-size:11px;font-weight:700;color:#3fb950;">${d['cp']*1.5:.2f}</div></div><div><div style="font-size:8px;color:#8b949e;">TP2</div><div style="font-size:11px;font-weight:700;color:#d29922;">${d['cp']*2:.2f}</div></div></div><div style="margin-top:15px;padding:12px;border-left:6px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;">{d['stt']}<br><span style="font-size:11px;font-weight:400;color:#f0f6fc;">{d['rs']}</span></div></div>"""
        components.html(html, height=380)

with t1: render_ui(tabs_d['RWA'], True)
with t2: render_ui(tabs_d['HUNTER'], False)
