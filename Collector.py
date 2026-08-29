import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# CoinGecko API Key Configuration
COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY', 'CG-JTUWHbMnceLTRSrYk6N8LCWs')

# Your application code here
class Collector:
    def __init__(self):
        self.api_key = COINGECKO_API_KEY
    
    def get_api_key(self):
        return self.api_key
