# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time
import os
import pickle

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
        data = client.open(sheet_name).worksheet(worksheet_name).get_all_records()
        df = pd.DataFrame(data)
        cols_to_fix = ['Holdings', 'Entry_Price']
        for c in cols_to_fix:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
                df.fillna({c: 0.0}, inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()

def get_market_data(coin_ids):
    full_data = load_cache()
    fng, btc_d = "50", 50.0
    try:
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            p_res = response.json()
            if p_res:
                for c_id, val in p_res.items():
                    if c_id not in full_data or not isinstance(full_data[c_id], dict): 
                        full_data[c_id] = {}
                    full_data[c_id].update(val)
                    full_data[c_id]['last_price_update'] = time.time()
                save_cache(full_data)
        fng_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        fng = fng_res['data'][0]['value']
        btc_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        btc_d = btc_res['data']['market_cap_percentage']['btc']
    except:
        pass
    return full_data, fng, btc_d

# TOÁN HỌC THUỒN TÚY KHÔNG DÙNG PANDAS ĐỂ TÍNH EMA VÀ RSI (CHỐNG LỖI PYTHON 3.13)
def calculate_ema(prices, period):
    if len(prices) < period: return prices[-1] if prices else 0.0
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price * k) + (ema * (1 - k))
    return float(ema)

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(diff if diff > 0 else 0.0)
        losses.append(-diff if diff < 0 else 0.0)
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))

def get_all_tech_data(strategy_dict):
    tech_results = {}
    ticker_map = {'sei-network': 'SEIUSDT', 'chainlink': 'LINKUSDT', 'pepe': 'PEPEUSDT'}
    
    for cat in strategy_dict.values():
        for symbol, info in cat.items():
            coin_id = info['id']
            binance_symbol = ticker_map.get(coin_id.lower())
            if not binance_symbol: continue
                
            try:
                url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=1d&limit=100"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    # Ép kiểu dữ liệu sang float ngay từ đầu luồng bốc tách
                    closes = [float(item[4]) for item in data]
                    
                    if len(closes) >= 50:
                        rsi = calculate_rsi(closes, 14)
                        
                        # Tính toán MACD thuần túy
                        ema12_list = []
                        ema26_list = []
                        for i in range(len(closes)):
                            ema12_list.append(calculate_ema(closes[:i+1], 12))
                            ema26_list.append(calculate_ema(closes[:i+1], 26))
                        macd_line = [e12 - e26 for e12, e26 in zip(ema12_list, ema26_list)]
                        macd = macd_line[-1]
                        
                        ema20 = calculate_ema(closes, 20)
                        ema50 = calculate_ema(closes, 50)
                        sup = float(min(closes))
                        res_val = float(max(closes))
                        
                        tech_results[coin_id] = (rsi, macd, ema20, ema50, sup, res_val)
                    else:
                        tech_results[coin_id] = (50.0, 0.0, 0.0, 0.0, 1.0, 1.0)
                else:
                    tech_results[coin_id] = (50.0, 0.0, 0.0, 0.0, 1.0, 1.0)
                time.sleep(0.1)
            except:
                tech_results[coin_id] = (50.0, 0.0, 0.0, 0.0, 1.0, 1.0)
                
    return tech_results

def analyze_v25_pro(cp, ath, tech):
    if not tech or len(tech) < 6 or tech[4] <= 0.1: 
        return "WAITING", "#8b949e", "Đang săn dữ liệu...", 0
        
    rsi, macd, ema20, ema50, sup, res = tech
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    if rsi < 35 or (cp <= sup * 1.05 and rsi < 45):
        if macd > 0: return "STRONG BUY", "#3fb950", "Đáy cứng + Dòng tiền hồi phục", dist
        return "ACCUMULATE", "#2ea043", "Vùng gom an toàn, chia vốn DCA", dist
    if ema20 > ema50 and cp > ema50:
        if macd > 0: return "STRONG BULL", "#1f6feb", "Sóng tăng khỏe (EMA Cắt + MACD Dương)", dist
        return "BULLISH", "#58a6ff", "Xu hướng tăng bảo toàn, tiếp tục giữ", dist
    if ema20 < ema50 and cp < ema50:
        return "CAUTION", "#d29922", "Xu hướng yếu, chỉ gom thêm tại hỗ trợ SUP", dist
    if rsi > 70 or (cp >= res * 0.97 and rsi > 65):
        return "TAKE PROFIT", "#f85149", "Gặp cản cứng + Quá mua ngắn hạn", dist
    return "HOLD", "#8b949e", "Kiên nhẫn quan sát thêm xu hướng", dist
