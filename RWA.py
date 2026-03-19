# RWA.py - BẢN HOÀN THIỆN 100% (V3.0)
import streamlit as st
import pandas as pd
import feedparser
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, get_tech_radar, analyze_v25_pro

st.set_page_config(page_title="Sovereign V25", layout="wide")
apply_custom_style()

# 1. LẤY DỮ LIỆU
df_h = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)
all_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
prices, fng_val, btc_dom = get_market_data(all_ids)

# TÍNH TOÁN TÀI CHÍNH TỔNG
total_v, total_pnl = 0, 0
if not df_h.empty:
    for _, r in df_h.iterrows():
        c_id = next((v['id'] for cat in STRATEGY.values() for k, v in cat.items() if k == r['Coin']), None)
        if c_id:
            cp = prices.get(c_id, {}).get('usd', 0)
            total_v += r['Holdings'] * cp
            total_pnl += (cp - r['Entry_Price']) * r['Holdings']

# 2. DASHBOARD TỔNG (TRẠM CHỈ HUY)
st.title("🛡️ SOVEREIGN COMMAND CENTER")
d1, d2, d3, d4 = st.columns(4)
with d1: st.markdown(f'<div class="header-box"><div class="metric-label">Tổng Tài Sản</div><div class="metric-value">${total_v:,.2f}</div></div>', unsafe_allow_html=True)
with d2: st.markdown(f'<div class="header-box"><div class="metric-label">Tổng Lời/Lỗ</div><div class="metric-value" style="color:{"#3fb950" if total_pnl>=0 else "#f85149"};">{total_pnl:+,.2f}</div></div>', unsafe_allow_html=True)
with d3: st.markdown(f'<div class="header-box"><div class="metric-label">Tâm lý F&G</div><div class="metric-value">{fng_val}/100</div></div>', unsafe_allow_html=True)
with d4: st.markdown(f'<div class="header-box"><div class="metric-label">BTC Dom</div><div class="metric-value">{btc_dom:.1f}%</div></div>', unsafe_allow_html=True)

# --- PHẦN TIN TỨC (TRẢ LẠI TRANG TIN) ---
with st.expander("📰 TOP 3 TIN TỨC CHIẾN LƯỢC TRONG NGÀY", expanded=True):
    feed = feedparser.parse("https://cointelegraph.com/rss/tag/altcoin")
    for e in feed.entries[:3]:
        st.markdown(f"**• {e.title}** ([Xem tin]({e.link}))")

# 3. TABS CHIẾN LƯỢC (ĐẦY ĐỦ CHỈ SỐ)
t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER STRATEGY"])

def render_tab(category, tab_obj):
    with tab_obj:
        cols = st.columns(4)
        for i, (symbol, info) in enumerate(STRATEGY[category].items()):
            # Lấy data market & kỹ thuật
            coin_data = prices.get(info['id'], {})
            cp = coin_data.get('usd', 0)
            chg = coin_data.get('usd_24h_change', 0)
            vol = coin_data.get('usd_24h_vol', 0) # Thêm Volume
            
            # Radar kỹ thuật đầy đủ
            rsi, macd, ema20, sup, res = get_tech_radar(info['id'])
            
            # Data từ Sheet
            u = df_h[df_h['Coin'] == symbol] if not df_h.empty else pd.DataFrame()
            h, e = (u['Holdings'].iloc[0], u['Entry_Price'].iloc[0]) if not u.empty else (0, 0)
            pnl_pct = ((cp / e) - 1) * 100 if e > 0 else 0
            stt, col, msg, dist = analyze_v25_pro(cp, info['ath'], rsi, macd, ema20)
            
            with cols[i % 4]:
                st.markdown(f"""
                <div class="coin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="font-size:16px; color:#58a6ff;">{symbol}</b>
                        <span class="status-badge" style="background:{col}; color:white;">{stt}</span>
                    </div>
                    <h2 style="margin:8px 0;">${cp:,.4f} <small style="font-size:12px; color:{'#3fb950' if chg > 0 else '#f85149'};">{chg:+.2f}%</small></h2>
                    
                    <div style="font-size:11px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:4px; line-height:1.4;">
                        <span>Holdings: <b>{h:,.0f}</b></span>
                        <span>PnL: <b style="color:{'#3fb950' if pnl_pct >= 0 else '#f85149'};">{pnl_pct:+.1f}%</b></span>
                        <span>Vol 24h: <b>${vol/1e6:.1f}M</b></span>
                        <span>RSI: <b>{rsi:.1f}</b></span>
                        <span>MACD: <b style="color:{'#3fb950' if macd>0 else '#f85149'};">{macd:.4f}</b></span>
                        <span>EMA20: <b>${ema20:,.2f}</b></span>
                        <span style="color:#3fb950;">SUP: {sup:,.2f}</span>
                        <span style="color:#f85149;">RES: {res:,.2f}</span>
                    </div>
                    
                    <div style="margin-top:10px; font-size:11px; border-top:1px solid #30363d; padding-top:8px; display:flex; justify-content:space-between;">
                        <span style="color:#3fb950; font-weight:bold;">TP1: ${cp*1.5:,.2f}</span>
                        <span style="color:#d29922; font-weight:bold;">TP2: ${cp*2.0:,.2f}</span>
                    </div>
                    <p style="font-size:10px; color:{col}; margin-top:8px; font-style: italic;">💡 {msg}</p>
                </div>
                """, unsafe_allow_html=True)

render_tab('RWA', t1)
render_tab('HUNTER', t2)
