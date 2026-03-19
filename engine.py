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
    ids = ",".join(coin_ids)
    p_url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    prices = requests.get(p_url).json()
    fng = requests.get("https://api.alternative.me/fng/").json()['data'][0]['value']
    btc_d = requests.get("https://api.coingecko.com/api/v3/global").json()['data']['market_cap_percentage']['btc']
    return prices, fng, btc_d

@st.cache_data(ttl=300)
def get_tech_radar(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        data = requests.get(url).json()
        df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
        rsi = df.ta.rsi(length=14).iloc[-1]
        macd = df.ta.macd().iloc[-1][0]
        ema20 = df.ta.ema(length=20).iloc[-1]
        return rsi, macd, ema20, df['close'].min(), df['close'].max()
    except: return 50.0, 0.0, 0.0, 0.0, 0.0

def analyze_v25_pro(cp, ath, rsi, macd, ema20):
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    if rsi < 35: return "ACCUMULATE", "#3fb950", "Vùng gom cực đẹp", dist
    if rsi > 70: return "TAKE PROFIT", "#f85149", "Hưng phấn quá đà, tỉa lãi", dist
    return "HOLD", "#d29922", "Kiên nhẫn gồng, chưa biến động", dist
