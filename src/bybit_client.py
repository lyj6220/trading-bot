from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

class BybitClient:
    def __init__(self):
        load_dotenv()
        self.client = HTTP(
            testnet=False,
            api_key=os.getenv('BYBIT_API_KEY'),
            api_secret=os.getenv('BYBIT_SECRET_KEY')
        )

    def get_closed_pnl(self, **kwargs):
        return self.client.get_closed_pnl(**kwargs)

    def get_positions(self, **kwargs):
        return self.client.get_positions(**kwargs) 