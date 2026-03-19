# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta

@st.cache_resource
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        df = pd.DataFrame(client.open(sheet_name).worksheet(worksheet_name).get_all_records())
        # Đồng bộ tên cột 'Coin', 'Entry_Price', 'Holdings' từ file gốc của anh Công
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def get_market_data(coin_ids):
    ids = ",".join(coin_ids)
    # Lấy giá, volume và 24h change
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
    prices = requests.get(url).json()
    
    # Lấy Fear & Greed Index
    fng = requests.get("https://api.alternative.me/fng/").json()['data'][0]['value']
    
    # Lấy BTC Dominance
    global_data = requests.get("https://api.coingecko.com/api/v3/global").json()
    btc_d = global_data['data']['market_cap_percentage']['btc']
    
    return prices, fng, btc_d

def get_technical_indicators(coin_id):
    # Lấy dữ liệu 30 ngày để tính RSI, MACD, Bollinger, EMA
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
    data = requests.get(url).json()
    df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
    
    rsi = df.ta.rsi(length=14).iloc[-1]
    macd_df = df.ta.macd()
    macd = macd_df.iloc[-1][0] # MACD Line
    bb = df.ta.bbands(length=20).iloc[-1]
    ema20 = df.ta.ema(length=20).iloc[-1]
    
    sup = df['close'].min()
    res = df['close'].max()
    
    return rsi, macd, bb, ema20, sup, res

def analyze_v25_pro(cp, ath, rsi, macd, ema20):
    dist_ath = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    # Logic tâm lý + kỹ thuật
    if rsi < 35 and cp > ema20:
        return "ACCUMULATE", "#3fb950", "Dòng tiền nén, vùng gom cực đẹp", dist_ath
    elif rsi > 70:
        return "TAKE PROFIT", "#f85149", "Hưng phấn quá đà, nên tỉa bớt lãi", dist_ath
    elif macd > 0:
        return "BULLISH", "#58a6ff", "Xu hướng tăng đang mạnh", dist_ath
    return "HOLD", "#d29922", "Kiên nhẫn đợi sóng, đừng hành động gấp", dist_ath
