# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta
import time

@st.cache_resource
def get_gspread_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        df = pd.DataFrame(client.open(sheet_name).worksheet(worksheet_name).get_all_records())
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=120)
def get_market_data(coin_ids):
    prices, fng, btc_d = {}, "50", 50.0
    try:
        ids = ",".join(coin_ids)
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
        time.sleep(2.5) 
        
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        data = requests.get(url, timeout=10).json()
        
        if 'prices' not in data:
            return None
            
        df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
        rsi = df.ta.rsi(length=14).iloc[-1]
        macd = df.ta.macd().iloc[-1][0]
        ema20 = df.ta.ema(length=20).iloc[-1]
        return rsi, macd, ema20, df['close'].min(), df['close'].max()
    except:
        return None

def analyze_v25_pro(cp, ath, tech):
    if not tech: return "WAITING", "#8b949e", "Thiếu dữ liệu...", 0
    rsi, macd, ema20, sup, res = tech
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    if rsi < 35 and cp > ema20: return "ACCUMULATE", "#3fb950", "Vùng gom cực đẹp", dist
    if rsi > 70: return "TAKE PROFIT", "#f85149", "Hưng phấn quá đà, tỉa lãi", dist
    if macd > 0: return "BULLISH", "#58a6ff", "Xu hướng tăng rõ rệt", dist
    return "HOLD", "#d29922", "Quan sát thêm...", dist
# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta
import time
import os
import pickle

# Cơ chế lưu trữ bền vững
CACHE_FILE = "price_cache.pkl"

def save_cache(data):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except: return {}
    return {}

@st.cache_resource
def get_gspread_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        df = pd.DataFrame(client.open(sheet_name).worksheet(worksheet_name).get_all_records())
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except: return pd.DataFrame()

def get_market_data(coin_ids):
    # Tải dữ liệu từ sổ tay lên trước
    full_data = load_cache()
    prices, fng, btc_d = {}, "50", 50.0
    try:
        ids = ",".join(coin_ids)
        p_res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true", timeout=10).json()
        if p_res: 
            for c_id, val in p_res.items():
                if c_id not in full_data: full_data[c_id] = {}
                full_data[c_id].update(val)
            save_cache(full_data)
        
        f_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        if 'data' in f_res: fng = f_res['data'][0]['value']
        g_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        if 'data' in g_res: btc_d = g_res['data']['market_cap_percentage']['btc']
    except: pass
    return full_data, fng, btc_dom # full_data giờ đóng vai trò là prices

def get_tech_radar(coin_id):
    full_data = load_cache()
    current_time = time.time()
    cache_entry = full_data.get(coin_id, {})
    
    # Nếu đã có dữ liệu kỹ thuật và chưa quá 5 phút thì dùng luôn, không hỏi sàn
    if 'rsi' in cache_entry and (current_time - cache_entry.get('last_update', 0) < 300):
        return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['sup'], cache_entry['res']

    try:
        time.sleep(2.5) # Giữ nguyên mức sleep 2.5s anh đang dùng
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        data = requests.get(url, timeout=10).json()
        
        if 'prices' in data:
            df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
            rsi = df.ta.rsi(length=14).iloc[-1]
            macd = df.ta.macd().iloc[-1][0]
            ema20 = df.ta.ema(length=20).iloc[-1]
            sup, res_val = df['close'].min(), df['close'].max()
            
            # Lưu vào sổ tay
            if coin_id not in full_data: full_data[coin_id] = {}
            full_data[coin_id].update({
                'rsi': rsi, 'macd': macd, 'ema20': ema20, 
                'sup': sup, 'res': res_val, 'last_update': current_time
            })
            save_cache(full_data)
            return rsi, macd, ema20, sup, res_val
    except: pass
    
    # Nếu lỗi sàn, trả về dữ liệu cũ nhất trong sổ tay (nếu có)
    if 'rsi' in cache_entry:
        return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['sup'], cache_entry['res']
    return None

def analyze_v25_pro(cp, ath, tech):
    if not tech: return "WAITING", "#8b949e", "Đang săn dữ liệu...", 0
    rsi, macd, ema20, sup, res = tech
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    if rsi < 35: return "ACCUMULATE", "#3fb950", "Vùng gom cực đẹp", dist
    if rsi > 70: return "TAKE PROFIT", "#f85149", "Hưng phấn quá đà", dist
    return "HOLD", "#d29922", "Kiên nhẫn quan sát", dist
