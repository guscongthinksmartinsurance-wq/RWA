# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta

@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], 
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    return gspread.authorize(creds)

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        df = pd.DataFrame(get_gspread_client().open(sheet_name).worksheet(worksheet_name).get_all_records())
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=120)
def get_market_data(coin_ids):
    prices, fng, btc_d = {}, "50", 50.0
    try:
        ids = ",".join(coin_ids)
        # Lấy giá và cả Volume 24h
        p_res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true", timeout=10).json()
        if p_res: prices = p_res
        f_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        if 'data' in f_res: fng = f_res['data'][0]['value']
        g_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        if 'data' in g_res: btc_d = g_res['data']['market_cap_percentage']['btc']
    except: pass
    return prices, fng, btc_d

@st.cache_data(ttl=300)
def get_tech_radar(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        data = requests.get(url, timeout=10).json()
        if 'prices' not in data: return None # Trả về None nếu không có dữ liệu
        
        df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
        rsi = df.ta.rsi(length=14).iloc[-1]
        macd_df = df.ta.macd()
        macd = macd_df.iloc[-1][0]
        ema20 = df.ta.ema(length=20).iloc[-1]
        sup = df['close'].min()
        res = df['close'].max()
        return rsi, macd, ema20, sup, res
    except: return None

def analyze_v25_pro(cp, ath, tech_data):
    if tech_data is None:
        return "WAITING", "#8b949e", "Thiếu dữ liệu phân tích...", 0
    
    rsi, macd, ema20, sup, res = tech_data
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    # Logic thực chiến: Chỉ khuyên khi đủ dữ liệu
    if rsi < 35 and cp > ema20: return "ACCUMULATE", "#3fb950", "Dòng tiền nén, vùng gom đẹp", dist
    if rsi > 70: return "TAKE PROFIT", "#f85149", "Hưng phấn quá đà, nên tỉa lãi", dist
    if macd > 0: return "BULLISH", "#58a6ff", "Xu hướng tăng rõ rệt", dist
    return "HOLD", "#d29922", "Quan sát thêm, chưa có biến động", dist
