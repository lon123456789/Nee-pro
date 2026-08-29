import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Secret Key Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'CG-JTUWHbMnceLTRSrYk6N8LCWs')

# Your application code here
class Collector:
    def __init__(self):
        self.secret_key = SECRET_KEY
    
    def get_secret(self):
        return self.secret_key
