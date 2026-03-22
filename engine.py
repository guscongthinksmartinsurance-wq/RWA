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
    # Luôn load cache lên trước để có cái "phòng thân"
    full_data = load_cache()
    fng, btc_d = "50", 50.0
    
    try:
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
        
        # Tăng timeout lên 15 giây vì dạo này mạng quốc tế hơi chập chờn
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            p_res = response.json()
            if p_res:
                for c_id, val in p_res.items():
                    if c_id not in full_data: full_data[c_id] = {}
                    full_data[c_id].update(val)
                    # Gán thêm nhãn thời gian cập nhật giá
                    full_data[c_id]['last_price_update'] = time.time()
                save_cache(full_data)
        
        # Tương tự cho FnG và BTC Dom, lỗi thì dùng mặc định không để app chết
        fng_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        fng = fng_res['data'][0]['value']
        
        btc_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        btc_d = btc_res['data']['market_cap_percentage']['btc']
        
    except Exception as e:
        print(f"Lỗi lấy giá tổng quát: {e}")
        # Nếu lỗi, cứ để nó trả về full_data (lúc này là dữ liệu từ load_cache)
        pass
    
    return full_data, fng, btc_d

def get_tech_radar(coin_id):
    full_data = load_cache()
    current_time = time.time()
    
    # 1. Lấy dữ liệu từ Cache (Ưu tiên số 1)
    cache_entry = full_data.get(coin_id, {})
    
    # Nếu dữ liệu còn mới (dưới 15 phút), trả về luôn để app chạy siêu tốc
    if 'rsi' in cache_entry and (current_time - cache_entry.get('last_update', 0) < 900):
        return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['sup'], cache_entry['res']

    # 2. Cơ chế "Cập nhật thông minh": Kiểm tra xem gần đây có con nào vừa gọi API chưa
    # Nếu vừa gọi cách đây dưới 5 giây, thì con này tạm thời dùng lại cache cũ để tránh bị Block IP
    last_global_call = full_data.get('last_global_api_call', 0)
    if (current_time - last_global_call) < 5: 
        if 'rsi' in cache_entry:
            return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['sup'], cache_entry['res']
        return None

    # 3. Chỉ gọi API khi thực sự cần và đảm bảo khoảng cách an toàn
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        res = requests.get(url, timeout=15) # Tăng timeout lên một chút cho chắc
        
        if res.status_code == 200:
            data = res.json()
            if 'prices' in data:
                df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
                rsi = df.ta.rsi(length=14).iloc[-1]
                macd_df = df.ta.macd()
                macd = macd_df.iloc[-1][0]
                ema20 = df.ta.ema(length=20).iloc[-1]
                sup, res_val = df['close'].min(), df['close'].max()
                
                # Lưu vào cache
                if coin_id not in full_data: full_data[coin_id] = {}
                full_data[coin_id].update({
                    'rsi': rsi, 'macd': macd, 'ema20': ema20, 
                    'sup': sup, 'res': res_val, 'last_update': current_time
                })
                full_data['last_global_api_call'] = current_time # Đánh dấu vừa gọi API xong
                save_cache(full_data)
                
                return rsi, macd, ema20, sup, res_val
        elif res.status_code == 429:
            # Nếu bị chặn, ghi log nhẹ và dùng tạm cache cũ
            print(f"Rate limit hit for {coin_id}, using stale cache.")
    except Exception as e:
        print(f"Error fetching tech for {coin_id}: {e}")
    
    # 4. Cứu cánh cuối cùng: Nếu API lỗi thì bốc dữ liệu cũ nhất ra dùng, không để app trắng
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
