# RWA.py
import streamlit as st
import pandas as pd
import feedparser
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, get_technical_indicators, analyze_v25_pro

st.set_page_config(page_title="Sovereign V25", layout="wide")
apply_custom_style()

# 1. LẤY DỮ LIỆU TỔNG HỢP
df_h = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)
all_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
market_prices, fng_val, btc_dom = get_market_data(all_ids)

# 2. DASHBOARD TỔNG
st.title("🛡️ SOVEREIGN PORTFOLIO V25")
c1, c2, c3, c4 = st.columns(4)
c1.metric("F&G Index", f"{fng_val}/100", "Sợ hãi" if int(fng_val) < 30 else "Tham lam")
c2.metric("BTC Dominance", f"{btc_dom:.1f}%")
c3.info(f"📁 Sheet: {WORKSHEET_NAME}")
c4.warning("💡 Note: Gom SEI 0.062 - Quyết thắng!")

# Tin tức chọn lọc
with st.expander("📰 TOP 3 TIN TỨC CHIẾN LƯỢC TRONG NGÀY"):
    feed = feedparser.parse("https://cointelegraph.com/rss/tag/altcoin")
    for e in feed.entries[:3]:
        st.markdown(f"**• {e.title}** ([Xem ngay]({e.link}))")

# 3. TABS CHIẾN LƯỢC
t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER STRATEGY"])

def render_strategy_tab(category, tab_obj):
    with tab_obj:
        cols = st.columns(4)
        for i, (symbol, info) in enumerate(STRATEGY[category].items()):
            # Lấy giá và chỉ số kỹ thuật
            cp = market_prices.get(info['id'], {}).get('usd', 0)
            chg = market_prices.get(info['id'], {}).get('usd_24h_change', 0)
            rsi, macd, bb, ema20, sup, res = get_technical_indicators(info['id'])
            
            # Khớp dữ liệu từ Sheet (Coin, Entry_Price, Holdings)
            u = df_h[df_h['Coin'] == symbol] if not df_h.empty else pd.DataFrame()
            h, e = (u['Holdings'].iloc[0], u['Entry_Price'].iloc[0]) if not u.empty else (0.0, 0.0)
            pnl = ((cp / e) - 1) * 100 if e > 0 else 0.0
            
            # Logic Analyze V25 Pro
            stt, col, msg, dist = analyze_v25_pro(cp, info['ath'], rsi, macd, ema20)
            
            with cols[i % 4]:
                st.markdown(f"""
                <div class="coin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="font-size:16px; color:#58a6ff;">{symbol}</b>
                        <span class="status-badge" style="background:{col}; color:white;">{stt}</span>
                    </div>
                    <h2 style="margin:10px 0; color:white;">${cp:,.4f} <small style="font-size:12px; color:{'#3fb950' if chg > 0 else '#f85149'};">{chg:+.2f}%</small></h2>
                    <div style="font-size:11px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:5px; line-height:1.6;">
                        <span>Holdings: <b>{h:,.0f}</b></span>
                        <span>PnL: <b style="color:{'#3fb950' if pnl >= 0 else '#f85149'};">{pnl:+.1f}%</b></span>
                        <span>RSI: <b>{rsi:.1f}</b></span>
                        <span>Cách ATH: <b>{dist:.1f}%</b></span>
                        <span>Hỗ trợ (SUP): <b style="color:#3fb950;">{sup:,.2f}</b></span>
                        <span>Kháng cự (RES): <b style="color:#f85149;">{res:,.2f}</b></span>
                    </div>
                    <div style="margin-top:12px; font-size:11px; border-top:1px solid #30363d; padding-top:10px; display:flex; justify-content:space-between;">
                        <span style="color:#3fb950; font-weight:bold;">TP1: ${cp*1.5:,.2f}</span>
                        <span style="color:#d29922; font-weight:bold;">TP2: ${cp*2.0:,.2f}</span>
                    </div>
                    <p style="font-size:11px; color:{col}; margin-top:10px; font-style: italic;">💡 {msg}</p>
                </div>
                """, unsafe_allow_html=True)

render_strategy_tab('RWA', t1)
render_strategy_tab('HUNTER', t2)
