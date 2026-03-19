import streamlit as st
import pandas as pd
import feedparser
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, get_tech_radar, analyze_v25_pro

st.set_page_config(page_title="Sovereign V25", layout="wide", initial_sidebar_state="expanded")
apply_custom_style()

with st.sidebar:
    st.markdown("<style>[data-testid='stSidebar']{background-color:#161b22;}.s-news{color:#58a6ff;font-weight:bold;font-size:13px;}.s-link{color:#c9d1d9;font-size:12px;text-decoration:none;}</style>", unsafe_allow_html=True)
    st.header("📰 Tin tức Chiến lược")
    f = feedparser.parse("https://cointelegraph.com/rss/tag/altcoin")
    for e in f.entries[:3]:
        st.markdown(f"<div class='s-news'>{e.title}</div><a class='s-link' href='{e.link}'>Xem chi tiết →</a><br><br>", unsafe_allow_html=True)
    st.markdown("---")
    st.write("Sovereign V25 - Anh Công")

# 1. DATA
df_h = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)
all_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
prices_cache, fng_val, btc_dom = get_market_data(all_ids)

# TÍNH TỔNG TÀI SẢN
total_v, total_pnl = 0, 0
if not df_h.empty:
    for _, r in df_h.iterrows():
        c_id = next((v['id'] for cat in STRATEGY.values() for k, v in cat.items() if k == r['Coin']), None)
        if c_id:
            cp = prices_cache.get(c_id, {}).get('usd', 0)
            total_v += r['Holdings'] * cp
            total_pnl += (cp - r['Entry_Price']) * r['Holdings']

# 2. COMMAND CENTER
st.title("🛡️ SOVEREIGN COMMAND CENTER")
d1, d2, d3, d4 = st.columns(4)
with d1: st.markdown(f'<div class="header-box"><div class="metric-label">Tổng Tài Sản</div><div class="metric-value">${total_v:,.2f}</div></div>', unsafe_allow_html=True)
with d2:
    pc = "#3fb950" if total_pnl >= 0 else "#f85149"
    st.markdown(f'<div class="header-box"><div class="metric-label">Tổng Lời/Lỗ</div><div class="metric-value" style="color:{pc};">{total_pnl:+,.2f}</div></div>', unsafe_allow_html=True)
with d3: st.markdown(f'<div class="header-box"><div class="metric-label">Tâm lý F&G</div><div class="metric-value">{fng_val}/100</div></div>', unsafe_allow_html=True)
with d4: st.markdown(f'<div class="header-box"><div class="metric-label">BTC Dom</div><div class="metric-value">{btc_dom:.1f}%</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 3. HIỂN THỊ TẤT CẢ COIN
all_coins = {}
for cat in STRATEGY.values(): all_coins.update(cat)

cols = st.columns(4)
for i, (symbol, info) in enumerate(all_coins.items()):
    coin_data = prices_cache.get(info['id'], {})
    cp = coin_data.get('usd', 0)
    chg = coin_data.get('usd_24h_change', 0)
    vol = coin_data.get('usd_24h_vol', 0)
    
    tech = get_tech_radar(info['id'])
    u = df_h[df_h['Coin'] == symbol] if not df_h.empty else pd.DataFrame()
    h, e = (u['Holdings'].iloc[0], u['Entry_Price'].iloc[0]) if not u.empty else (0.0, 0.0)
    pnl_p = ((cp/e)-1)*100 if e > 0 else 0
    stt, col, msg, dist = analyze_v25_pro(cp, info['ath'], tech)
    rsi, macd, ema20, sup, res = tech if tech else (0,0,0,0,0)
    
    p_display = f"{cp:.8f}" if cp < 0.001 else f"{cp:,.4f}"
    m_display = f"{macd:.6f}" if abs(macd) < 0.001 else f"{macd:.4f}"

    with cols[i % 4]:
        st.markdown(f"""
        <div class="coin-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="font-size:16px; color:#58a6ff;">{symbol}</b>
                <span class="status-badge" style="background:{col}; color:white;">{stt}</span>
            </div>
            <h2 style="margin:10px 0; color:white;">${p_display} <small style="font-size:12px; color:{'#3fb950' if chg > 0 else '#f85149'};">{chg:+.2f}%</small></h2>
            <div style="font-size:11px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:5px; line-height:1.6;">
                <span>Holdings: <b>{h:,.0f}</b></span>
                <span>PnL: <b style="color:{'#3fb950' if pnl_p >= 0 else '#f85149'};">{pnl_p:+.1f}%</b></span>
                <span>Vol 24h: <b>${vol/1e6:.1f}M</b></span>
                <span>RSI: <b>{rsi:.1f}</b></span>
                <span>MACD: <b style="color:{'#3fb950' if macd>0 else '#f85149'};">{m_display}</b></span>
                <span>Cách ATH: <b>{dist:.1f}%</b></span>
                <span style="color:#3fb950;">SUP: {sup:,.2f}</span>
                <span style="color:#f85149;">RES: {res:,.2f}</span>
            </div>
            <div style="margin-top:12px; font-size:11px; border-top:1px solid #30363d; padding-top:10px; display:flex; justify-content:space-between;">
                <span style="color:#3fb950; font-weight:bold;">TP1: ${cp*1.5:,.2f}</span>
                <span style="color:#d29922; font-weight:bold;">TP2: ${cp*2.0:,.2f}</span>
            </div>
            <p style="font-size:11px; color:{col}; margin-top:10px; font-style: italic;">💡 {msg}</p>
        </div>
        """, unsafe_allow_html=True)
