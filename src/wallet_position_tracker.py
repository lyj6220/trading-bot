import ccxt
import logging
from typing import Dict, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WalletPositionTracker:
    def __init__(self, api_key: str, secret_key: str):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear',
                'adjustForTimeDifference': True,
                'recvWindow': 10000
            }
        })

    def get_wallet_info(self) -> Dict:
        """지갑 정보 조회"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            
            wallet_info = {
                'total_equity': float(usdt_balance.get('total', 0)),
                'available_balance': float(usdt_balance.get('free', 0)),
                'used_margin': float(usdt_balance.get('used', 0)),
                'unrealized_pnl': float(balance.get('info', {}).get('unrealizedPnl', 0)),
                'realized_pnl': float(balance.get('info', {}).get('realizedPnl', 0))
            }
            return wallet_info
        except Exception as e:
            logger.error(f"지갑 정보 조회 중 에러 발생: {e}")
            raise

    def get_position_info(self, symbol: str = "BTCUSDT") -> Dict:
        """포지션 정보 조회"""
        try:
            positions = self.exchange.fetch_positions([symbol])
            if not positions:
                return {
                    'has_position': False,
                    'position_size': 0,
                    'entry_price': 0,
                    'current_price': 0,
                    'liquidation_price': 0,
                    'leverage': 0,
                    'unrealized_pnl': 0,
                    'roe': 0
                }

            position = positions[0]
            
            position_info = {
                'has_position': abs(float(position['contracts'] or 0)) > 0,
                'position_side': 'long' if float(position['contracts'] or 0) > 0 else 'short' if float(position['contracts'] or 0) < 0 else 'none',
                'position_size': abs(float(position['contracts'] or 0)),
                'entry_price': float(position['entryPrice'] or 0),
                'current_price': float(position['markPrice'] or 0),
                'liquidation_price': float(position['liquidationPrice'] or 0),
                'leverage': float(position['leverage'] or 0),
                'unrealized_pnl': float(position['unrealizedPnl'] or 0),
                'roe': float(position['percentage'] or 0)
            }
            return position_info
        except Exception as e:
            logger.error(f"포지션 정보 조회 중 에러 발생: {e}")
            raise

    def prepare_account_status(self, symbol: str = "BTCUSDT") -> str:
        """계정 상태 정보를 문자열로 포맷팅"""
        wallet = self.get_wallet_info()
        position = self.get_position_info(symbol)
        
        status = f"""
=== 계정 상태 ===
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[지갑 정보]
총 자산가치: {wallet['total_equity']:.2f} USDT
사용 가능 잔액: {wallet['available_balance']:.2f} USDT
사용 중인 증거금: {wallet['used_margin']:.2f} USDT
미실현 손익: {wallet['unrealized_pnl']:.2f} USDT
실현 손익: {wallet['realized_pnl']:.2f} USDT

[포지션 정보]
심볼: {symbol}
포지션 여부: {'있음' if position['has_position'] else '없음'}"""

        if position['has_position']:
            status += f"""
포지션 방향: {'롱' if position['position_side'] == 'long' else '숏'}
포지션 크기: {position['position_size']} 계약
진입가격: {position['entry_price']:.2f} USDT
현재가격: {position['current_price']:.2f} USDT
청산가격: {position['liquidation_price']:.2f} USDT
레버리지: {position['leverage']}x
미실현 손익: {position['unrealized_pnl']:.2f} USDT
수익률: {position['roe']:.2f}%"""
        
        return status 