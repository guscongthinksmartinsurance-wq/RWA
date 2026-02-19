import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. BASELINE: 13 CHIẾN MÃ ---
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

# --- 2. HÀM TRỢ NĂNG ---
@st.cache_data(ttl=300)
def get_current_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        return requests.get(url).json()
    except: return {}

def get_hist_data(cg_id, days):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        r = requests.get(url).json()
        return pd.DataFrame({'Close': [x[1] for x in r['prices']], 'Volume': [x[1] for x in r['total_volumes']]})
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_fng_news():
    try:
        fng_r = requests.get('https://api.alternative.me/fng/').json()
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        news = "<br>".join([f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in f.entries[:3]])
        return fng_r['data'][0]['value'], fng_r['data'][0]['classification'], news
    except: return "50", "Neutral", "⚠️ News Error"

# --- 3. ANALYZE ENGINE ---
def analyze_v23(df, cp, has_h, pnl, fng_val):
    if df.empty or len(df) < 5: return 0,0,"READY","#8b949e", "Scanning...", 0
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = delta.where(delta < 0, 0).abs().rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol_r = df['Volume'].iloc[-1] / (df['Volume'].rolling(min(len(df), 10)).mean().iloc[-1] + 1e-10)
    sup, res = float(df['Close'].min()), float(df['Close'].max())
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append("RSI LOW")
    if cp <= df['Close'].rolling(min(len(df), 20)).mean().iloc[-1]: score += 1; checks.append("BB LOW")
    if ((cp/sup)-1)*100 < 5: score += 1; checks.append("SUPPORT")
    if vol_r > 1.3: score += 1; checks.append("WHALE")
    if rsi > 75: s, c = "TAKE PROFIT", "#f85149"
    elif score >= 3 and int(fng_val) < 40: s, c = "STRONG BUY", "#3fb950"
    elif score >= 2: s, c = "ACCUMULATE", "#1f6feb"
    else: s, c = "OBSERVE", "#30363d"
    eff = (pnl / (df['Close'].pct_change().std() * 100)) if has_h else 0
    return sup, res, s, c, " • ".join(checks), eff

# --- 4. DATA SETUP ---
@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return ws, df

st.set_page_config(page_title="Sovereign Terminal", layout="wide")
ws, df_h = load_data()
prices = get_current_prices()
f_val, f_class, news_html = get_fng_news()

# HEADER & NEWS
st.markdown(f"""<div style="background:#161b22;padding:15px;border-radius:12px;border:1px solid #30363d;margin-bottom:20px;"><div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e;margin-bottom:8px;"><b>📰 24H INTELLIGENCE</b><span>🎭 F&G: {f_class} ({f_val})</span></div><div style="font-size:13px;line-height:1.5;">{news_html}</div></div>""", unsafe_allow_html=True)

# DASHBOARD & PIE CHART
total_v, total_i = 0.0, 0.0
total_realized = float(df_h['Profit_Realized'].sum())
p_lab, p_val = [], []
for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cp = float(prices.get(info['id'], {}).get('usd', 0.0))
        u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        total_v += (h * cp); total_i += (h * e)
        if (h*cp) > 0: p_lab.append(name); p_val.append(h*cp)

cash = 2000.0 - total_i + total_realized
c1, c2 = st.columns([3, 1.2])
with c1:
    st.markdown(f"""<div style="background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;"><div style="color:#8b949e;font-size:10px;">PORTFOLIO VALUE</div><div style="color:white;font-size:32px;font-weight:900;">${(total_v + cash):,.0f}</div><div style="color:{'#3fb950' if (total_v-total_i)>=0 else '#f85149'};font-size:18px;font-weight:700;">PnL: ${(total_v-total_i):,.0f}</div></div>""", unsafe_allow_html=True)
with c2:
    p_lab.append("CASH"); p_val.append(max(0, cash))
    fig = go.Figure(data=[go.Pie(labels=p_lab, values=p_val, hole=.5)])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=140, paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

t1, t2 = st.tabs(["🛡️ RWA", "🔍 HUNTER"])

def render_elite(name, info, is_rwa):
    cp = float(prices.get(info['id'], {}).get('usd', 0.0))
    u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
    h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
    p_fmt = f"{cp:.7f}" if cp < 0.0001 else f"{cp:.4f}"
    
    st.markdown(f"#### {name} | ${p_fmt} | {((cp/e)-1)*100 if e>0 else 0:+.1f}%")
    period = st.selectbox("Timeline", ["-", "7D", "30D", "90D", "1Y"], key=f"sel_{name}")
    d_val = {"7D": 7, "30D": 30, "90D": 90, "1Y": 365}.get(period, 0)
    
    sup, res, stt, col, rs, eff = analyze_v23(get_hist_data(info['id'], d_val) if d_val > 0 else pd.DataFrame(), cp, h>0, ((cp/e)-1)*100 if e>0 else 0, f_val)
    
    # CARD GRID & EFF
    eff_c = "#3fb950" if eff > 1.5 else "#8b949e"
    weight_html = f"""<div style="font-size:10px;color:#8b949e;margin-bottom:8px;">WEIGHT: {(h*cp/2000*100):.1f}% / {info.get('tw',0)}% | <span style="color:{eff_c}">EFF: {eff:.1f}</span></div>""" if is_rwa else f"""<div style="font-size:10px;color:{eff_c};margin-bottom:8px;">EFFICIENCY: {eff:.1f}</div>"""
    
    html = f"""<div style="background:#0d1117;padding:15px;border-radius:12px;border:1px solid #30363d;margin-bottom:25px;">
        {weight_html}
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center;margin-bottom:10px;">
            <div><div style="font-size:7px;color:#8b949e;">INVEST</div><div style="font-size:10px;font-weight:700;">${h*e:,.0f}</div></div>
            <div><div style="font-size:7px;color:#8b949e;">AVG</div><div style="font-size:10px;font-weight:700;">${e:.3f}</div></div>
            <div><div style="font-size:7px;color:#8b949e;">SUPP</div><div style="font-size:10px;font-weight:700;color:#3fb950;">{f"{sup:.2f}" if d_val>0 else "-"}</div></div>
            <div><div style="font-size:7px;color:#8b949e;">RESIST</div><div style="font-size:10px;font-weight:700;color:#f85149;">{f"{res:.2f}" if d_val>0 else "-"}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;text-align:center;border-top:1px solid #30363d;padding-top:10px;">
            <div><div style="font-size:7px;color:#8b949e;">ATH</div><div style="font-size:10px;font-weight:700;color:#d29922;">${info['ath']}</div></div>
            <div><div style="font-size:7px;color:#8b949e;">TP1</div><div style="font-size:10px;font-weight:700;color:#3fb950;">${cp*1.5:.2f}</div></div>
            <div><div style="font-size:7px;color:#8b949e;">TP2</div><div style="font-size:10px;font-weight:700;color:#d29922;">${cp*2:.2f}</div></div>
        </div>
        <div style="margin-top:12px;padding:10px;border-radius:8px;background:{col};color:white;text-align:center;">
            <div style="font-size:13px;font-weight:900;">{stt}</div><div style="font-size:9px;opacity:0.9;">{rs}</div>
        </div></div>"""
    st.markdown(html, unsafe_allow_html=True)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_elite(n, i, True)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_elite(n, i, False)
