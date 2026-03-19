# config.py
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'ath': 52.8, 'desc': 'Oracle & CCIP Standard'},
        'ONDO': {'id': 'ondo-finance', 'ath': 1.48, 'desc': 'RWA Leader - Bonds'},
        'OM': {'id': 'mantra-chain', 'ath': 6.16, 'desc': 'Real Estate focus'},
        'ENA': {'id': 'ethena', 'ath': 1.52, 'desc': 'Yield-bearing Stablecoin'}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0, 'desc': 'Main Layer 1 - Commodity'},
        'SEI': {'id': 'sei-network', 'ath': 1.14, 'desc': 'Parallel EVM Speed'},
        'ASI': {'id': 'fetch-ai', 'ath': 3.48, 'desc': 'AI Alliance Leader'},
        'PEPE': {'id': 'pepe', 'ath': 0.000017, 'desc': 'Meme Sentiment'}
    }
}

SHEET_NAME = "TMC-Sales-Assistant"
WORKSHEET_NAME = "Holdings"
