# config.py
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'ath': 52.8, 'desc': 'Vua Oracle - Xương sống RWA'},
        'ONDO': {'id': 'ondo-finance', 'ath': 1.48, 'desc': 'Dẫn đầu mảng trái phiếu mã hóa'},
        'OM': {'id': 'mantra-chain', 'ath': 6.16, 'desc': 'Bất động sản on-chain'},
        'ENA': {'id': 'ethena', 'ath': 1.52, 'desc': 'Tối ưu lợi nhuận Stablecoin'}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0, 'desc': 'Đầu tàu Layer 1 - Commodity'},
        'SEI': {'id': 'sei-network', 'ath': 1.14, 'desc': 'Parallel EVM - Anh đang gom 0.062'},
        'ASI': {'id': 'fetch-ai', 'ath': 3.48, 'desc': 'Liên minh AI Siêu trí tuệ'},
        'PEPE': {'id': 'pepe', 'ath': 0.000017, 'desc': 'Chỉ báo dòng tiền nhỏ lẻ'}
    }
}

SHEET_NAME = "TMC-Sales-Assistant"
WORKSHEET_NAME = "Holdings"
