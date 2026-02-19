import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

# --- 1. CONFIG: 13 CHIẾN MÃ (OM FIXED) ---
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

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=120)
def get_current_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids},mantra&vs_currencies=usd").json()
        if 'mantra' in r and 'mantra-chain' not in r: r['mantra-chain'] = r['mantra']
        return r
    except: return {}

def get_hist_data(cg_id, days):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}").json()
        return pd.DataFrame({'Close': [x[1] for x in r['prices']], 'Volume': [x[1] for x in r['total_volumes']]})
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_intel_v2():
    try:
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        top_3 = []
        for entry in f.entries[:3]:
            top_3.append(f"🔹 <a href='{entry.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{entry.title[:55]}...</a>")
        fng = requests.get('https://api.alternative.me/fng/').json()['data'][0]['value']
        return fng, top_3
    except: return "50", ["⚠️ Market news updating..."]

# --- 3. ANALYZE ENGINE (V24.1) ---
def analyze_v24(df, cp, has_h, pnl, fng_val):
    if df.empty or len(df) < 5: return 0.0, 0.0, "SCANNING", "#30363d", "Waiting...", 0.0
    sup, res = float(df['Close'].min()), float(df['Close'].max())
    delta = df['Close'].diff(); gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = delta.where(delta < 0, 0).abs().rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    
    if rsi < 35: s, c, m = "STRONG BUY", "#3fb950", "RSI LOW • SUPPORT"
    elif rsi > 75: s, c, m = "TAKE PROFIT", "#f85149", "OVERBOUGHT"
    elif rsi < 50 and cp <= df['Close'].rolling(20).mean().iloc[-1]: s, c, m = "ACCUMULATE", "#1f6feb", "DCA ZONE"
    else: s, c, m = "OBSERVE", "#30363d", "STABLE"
    
    eff = (pnl / (df['Close'].pct_change().std() * 100)) if has_h and not df.empty else 0.0
    return sup, res, s, c, m, eff

# --- 4. INTERFACE ---
st.set_page_config(page_title="Sovereign Hub", layout="wide")
st.markdown("<style>iframe { pointer-events: auto !important; } .stSelectbox { margin-bottom: -15px; }</style>", unsafe_allow_html=True)

@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
df_h = pd.DataFrame(ws.get_all_records())
prices = get_current_prices()
fng, news_list = get_intel_v2()

# DASHBOARD HEADER
total_v, total_i, total_r = 0.0, 0.0, 0.0
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

cash = 2000.0 - total_i + total_r
st.markdown(f"""
<div style="background:#161b22; padding:15px; border-radius:12px; border:1px solid #30363d; margin-bottom:15px;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div><div style="font-size:10px; color:#8b949e;">PORTFOLIO</div><div style="font-size:24px; font-weight:900;">${(total_v+cash):,.0f}</div></div>
        <div style="text-align:right;"><div style="font-size:10px; color:#8b949e;">PnL</div><div style="font-size:20px; font-weight:900; color:{'#3fb950' if (total_v-total_i)>=0 else '#f85149'};">${(total_v-total_i):,.0f}</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ACCORDION NEWS (CHẠM ĐỂ NỞ 3 TIN)
with st.expander(f"🎭 F&G: {fng} | 📰 24H Intelligence (Latest News)", expanded=False):
    st.markdown(f"""<div style="font-size:12px; line-height:1.8; pointer-events: auto;">{"<br>".join(news_list)}</div>""", unsafe_allow_html=True)

t1, t2 = st.tabs(["🛡️ RWA", "🔍 HUNTER"])

def render_elite(name, info):
    cp = float(prices.get(info['id'], {}).get('usd', 0))
    u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
    h = float(u_row['Holdings'].iloc[0]) if not u_row.empty else 0.0
    e = float(u_row['Entry_Price'].iloc[0]) if not u_row.empty else 0.0
    pnl = ((cp/e)-1)*100 if e > 0 else 0.0
    p_fmt = f"{cp:.5f}" if cp < 1 else f"{cp:.2f}"
    
    st.markdown(f"<div style='margin-top:15px; font-weight:900; color:#58a6ff;'>{name} <span style='color:#8b949e; font-size:11px;'>• ${p_fmt} • {pnl:+.1f}%</span></div>", unsafe_allow_html=True)
    
    tl = st.selectbox("Scan", ["OFF", "7D", "30D", "90D", "1Y"], key=f"tl_{name}")
    d_val = {"7D":7, "30D":30, "90D":90, "1Y":365}.get(tl, 0)
    
    sup, res, stt, col, msg, eff = analyze_v24(get_hist_data(info['id'], d_val) if d_val > 0 else pd.DataFrame(), cp, h>0, pnl, fng)
    
    html = f"""<div style="background:#0d1117; padding:12px; border-radius:12px; border:1px solid #30363d; margin-bottom:10px;">
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:5px; text-align:center;">
            <div><div style="font-size:7px; color:#8b949e;">INV</div><div style="font-size:10px; font-weight:700;">${h*e:,.0f}</div></div>
            <div><div style="font-size:7px; color:#8b949e;">AVG</div><div style="font-size:10px; font-weight:700;">${e:.2f}</div></div>
            <div><div style="font-size:7px; color:#8b949e;">SUP</div><div style="font-size:10px; font-weight:700; color:#3fb950;">{f"{sup:.2f}" if d_val>0 else "-"}</div></div>
            <div><div style="font-size:7px; color:#8b949e;">RES</div><div style="font-size:10px; font-weight:700; color:#f85149;">{f"{res:.2f}" if d_val>0 else "-"}</div></div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:5px; text-align:center; border-top:1px solid #21262d; margin-top:8px; padding-top:8px;">
            <div><div style="font-size:7px; color:#8b949e;">ATH</div><div style="font-size:10px;">${info['ath']}</div></div>
            <div><div style="font-size:7px; color:#8b949e;">TP1</div><div style="font-size:10px; color:#3fb950;">${cp*1.5:.2f}</div></div>
            <div><div style="font-size:7px; color:#8b949e;">TP2</div><div style="font-size:10px; color:#d29922;">${cp*2:.2f}</div></div>
        </div>
        <div style="margin-top:10px; padding:8px; border-radius:6px; background:{col}; text-align:center;">
            <div style="font-size:11px; font-weight:900; color:white;">{stt}</div>
            <div style="font-size:8px; color:white; opacity:0.8;">{msg} | EFF: {eff:.1f}</div>
        </div>
    </div>"""
    st.markdown(html, unsafe_allow_html=True)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_elite(n, i)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_elite(n, i)
