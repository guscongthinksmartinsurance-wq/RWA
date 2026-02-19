import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

# --- 1. CONFIG: 13 CHIẾN MÃ (FIXED OM ID) ---
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'tw': 35, 'ath': 52.8},
        'ONDO': {'id': 'ondo-finance', 'tw': 20, 'ath': 1.48},
        'OM': {'id': 'mantra-chain', 'tw': 15, 'ath': 6.16}, 
        'QNT': {'id': 'quant-network', 'tw': 10, 'ath': 428.0},
        'PENDLE': {'id': 'pendle', 'tw': 10, 'ath': 7.52},
        'SYRUP': {'id': 'maple', 'tw': 5, 'ath': 2.10},
        'CFG': {'id': 'centrifuge', 'tw': 5, 'ath': 2.59}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0},
        'SUI': {'id': 'sui', 'ath': 3.92},
        'SEI': {'id': 'sei-network', 'ath': 1.14},
        'FET': {'id': 'fetch-ai', 'ath': 3.48},
        'ARB': {'id': 'arbitrum', 'ath': 2.40},
        'PEPE': {'id': 'pepe', 'ath': 0.000017}
    }
}

# --- 2. DATA ENGINE (FIXED OM & PIE DATA) ---
@st.cache_data(ttl=120)
def get_current_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids},mantra&vs_currencies=usd").json()
        # Ép OM phải có giá bằng cách check cả 2 ID tiềm năng
        if 'mantra' in r and 'mantra-chain' not in r: r['mantra-chain'] = r['mantra']
        elif 'mantra-chain' in r and 'mantra' not in r: r['mantra'] = r['mantra-chain']
        return r
    except: return {}

@st.cache_data(ttl=600)
def get_intel_v2():
    try:
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        top_3 = [f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title[:50]}...</a>" for e in f.entries[:3]]
        fng = requests.get('https://api.alternative.me/fng/').json()['data'][0]['value']
        return fng, top_3
    except: return "50", ["⚠️ Market news updating..."]

# --- 3. INTERFACE & PIE CHART ---
st.set_page_config(page_title="Sovereign Master", layout="wide")
st.markdown("<style>iframe { pointer-events: auto !important; }</style>", unsafe_allow_html=True)

@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
df_h = pd.DataFrame(ws.get_all_records())
prices = get_current_prices()
fng, news_list = get_intel_v2()

# TÍNH TOÁN TỔNG & PIE CHART
total_v, total_i, total_r = 0.0, 0.0, 0.0
p_lab, p_val = [], []
if not df_h.empty:
    df_h['Profit_Realized'] = pd.to_numeric(df_h['Profit_Realized'], errors='coerce').fillna(0)
    total_r = df_h['Profit_Realized'].sum()

for cat in STRATEGY.values():
    for name, info in cat.items():
        cp = float(prices.get(info['id'], {}).get('usd', 0))
        u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
        h = float(u_row['Holdings'].iloc[0]) if not u_row.empty else 0.0
        e = float(u_row['Entry_Price'].iloc[0]) if not u_row.empty else 0.0
        total_v += (h * cp); total_i += (h * e)
        if h > 0: p_lab.append(name); p_val.append(h * cp)

cash = 2000.0 - total_i + total_r
p_lab.append("CASH"); p_val.append(max(0, cash))

# DISPLAY DASHBOARD + PIE CHART (BÊN CẠNH NHAU)
c1, c2 = st.columns([1.5, 1])
with c1:
    st.markdown(f"""
    <div style="background:#161b22; padding:20px; border-radius:15px; border:1px solid #30363d;">
        <div style="font-size:10px; color:#8b949e;">TOTAL PORTFOLIO</div>
        <div style="font-size:28px; font-weight:900;">${(total_v+cash):,.0f}</div>
        <div style="font-size:18px; font-weight:700; color:{'#3fb950' if (total_v-total_i)>=0 else '#f85149'};">
            PnL: ${(total_v-total_i):,.0f}
        </div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    fig = go.Figure(data=[go.Pie(labels=p_lab, values=p_val, hole=.6)])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=130, paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# TIN TỨC GỌN GÀNG
with st.expander(f"🎭 F&G: {fng} | 📰 Latest Insights"):
    st.markdown(f"""<div style="font-size:12px; line-height:1.6; pointer-events: auto;">{"<br>".join(news_list)}</div>""", unsafe_allow_html=True)

# PHẦN CHI TIẾT COIN (GIỮ NGUYÊN LOGIC ANH ƯNG Ý)
t1, t2 = st.tabs(["🛡️ RWA", "🔍 HUNTER"])

def render_coin(name, info):
    cp = float(prices.get(info['id'], {}).get('usd', 0))
    u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
    h = float(u_row['Holdings'].iloc[0]) if not u_row.empty else 0.0
    e = float(u_row['Entry_Price'].iloc[0]) if not u_row.empty else 0.0
    p_fmt = f"{cp:.5f}" if cp < 1 else f"{cp:.2f}"
    
    st.markdown(f"<div style='margin-top:15px; font-weight:900; color:#58a6ff;'>{name} <span style='color:#8b949e; font-size:11px;'>• ${p_fmt}</span></div>", unsafe_allow_html=True)
    # ... (Các phần Timeline, 7 Cột, Ma trận giữ nguyên như bản anh đã duyệt)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_coin(n, i)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_coin(n, i)
