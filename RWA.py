import streamlit as st
import pandas as pd
import feedparser
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, get_technical_indicators, analyze_v25_pro

# --- 1. KHỞI TẠO GIAO DIỆN ---
st.set_page_config(page_title="Sovereign V25", layout="wide", initial_sidebar_state="collapsed")
apply_custom_style()

# --- 2. LẤY DỮ LIỆU TỔNG HỢP ---
# Lấy dữ liệu từ Google Sheet
df_holdings = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)

# Lấy dữ liệu thị trường (Gộp API từ engine)
all_coin_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
market_prices, fng_val, btc_dom = get_market_data(all_coin_ids)

# --- 3. HEADER & DASHBOARD TỔNG ---
st.title("🛡️ SOVEREIGN PORTFOLIO V25")

col_fng, col_btc, col_sheet, col_note = st.columns(4)
with col_fng:
    st.metric("Tâm lý F&G", f"{fng_val}/100", "Extreme Fear" if int(fng_val) < 25 else "Neutral")
with col_btc:
    st.metric("BTC Dominance", f"{btc_dom:.1f}%")
with col_sheet:
    st.metric("Worksheet", WORKSHEET_NAME)
with col_note:
    st.info("💡 Anh gom SEI 0.062 - Vững tay chèo!")

# Top 3 Tin tức chấn động
with st.expander("📰 TOP 3 TIN TỨC CHIẾN LƯỢC TRONG NGÀY"):
    feed = feedparser.parse("https://cointelegraph.com/rss/tag/altcoin")
    for entry in feed.entries[:3]:
        st.markdown(f"**• {entry.title}** ([Xem tin]({entry.link}))")

# --- 4. HIỂN THỊ CHIẾN LƯỢC (TABS) ---
tab_rwa, tab_hunter = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER STRATEGY"])

def render_strategy_tab(category, tab_obj):
    with tab_obj:
        # Chia 4 cột cho 4 con mỗi hàng
        cols = st.columns(4)
        for i, (symbol, info) in enumerate(STRATEGY[category].items()):
            # 1. Lấy thông số kỹ thuật & giá
            cp = market_prices.get(info['id'], {}).get('usd', 0)
            chg = market_prices.get(info['id'], {}).get('usd_24h_change', 0)
            rsi, macd, bbands, ema20, ema50, sup, res = get_technical_indicators(info['id'])
            
            # 2. Lấy dữ liệu từ Sheet của anh Công
            u_row = df_holdings[df_holdings['Coin'] == symbol] if not df_holdings.empty else pd.DataFrame()
            h = u_row['Holdings'].iloc[0] if not u_row.empty else 0
            e = u_row['Entry_Price'].iloc[0] if not u_row.empty else 0
            pnl_pct = ((cp / e) - 1) * 100 if e > 0 else 0
            
            # 3. Phân tích Logic V25 (Từ engine)
            status, color, msg, dist_ath = analyze_v25_pro(cp, info['ath'], rsi, macd, ema20)
            
            # 4. Hiển thị Card Coin 2.0
            with cols[i % 4]:
                st.markdown(f"""
                <div class="coin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="font-size:16px; color:#58a6ff;">{symbol}</b>
                        <span class="status-badge" style="background:{color}; color:white;">{status}</span>
                    </div>
                    <h2 style="margin:10px 0; color:white;">${cp:,.4f} <small style="font-size:12px; color:{'#3fb950' if chg > 0 else '#f85149'};">{chg:+.2f}%</small></h2>
                    <div style="font-size:11px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:5px; line-height:1.5;">
                        <span>Holdings: <b>{h:,.0f}</b></span>
                        <span>PnL: <b style="color:{'#3fb950' if pnl_pct >= 0 else '#f85149'};">{pnl_pct:+.1f}%</b></span>
                        <span>RSI: <b>{rsi:.1f}</b></span>
                        <span>Cách ATH: <b>{dist_ath:.1f}%</b></span>
                        <span>SUP: <b style="color:#3fb950;">{sup:,.2f}</b></span>
                        <span>RES: <b style="color:#f85149;">{res:,.2f}</b></span>
                    </div>
                    <div style="margin-top:10px; font-size:11px; border-top:1px solid #30363d; padding-top:10px; display:flex; justify-content:space-between;">
                        <span style="color:#3fb950; font-weight:bold;">TP1: ${cp*1.5:,.2f}</span>
                        <span style="color:#d29922; font-weight:bold;">TP2: ${cp*2.0:,.2f}</span>
                    </div>
                    <p style="font-size:11px; color:{color}; margin-top:10px; font-style: italic;">💡 {msg}</p>
                </div>
                """, unsafe_allow_html=True)

# Kích hoạt hiển thị cho 2 Tab
render_strategy_tab('RWA', tab_rwa)
render_strategy_tab('HUNTER', tab_hunter)

# --- 5. FOOTER ---
st.sidebar.markdown("---")
st.sidebar.write(f"Sovereign V25 - Trợ lý của anh Công")
