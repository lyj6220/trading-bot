import ccxt
import logging
from typing import Dict, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_float(value, default=0.0):
    """안전한 float 변환 함수"""
    if value is None or str(value).strip() == '' or str(value).strip() == 'None':
        return default
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default

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
                'total_equity': safe_float(usdt_balance.get('total')),
                'available_balance': safe_float(usdt_balance.get('free')),
                'used_margin': safe_float(usdt_balance.get('used')),
                'unrealized_pnl': safe_float(balance.get('info', {}).get('unrealizedPnl')),
                'realized_pnl': safe_float(balance.get('info', {}).get('realizedPnl'))
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
                'has_position': abs(safe_float(position.get('contracts'))) > 0,
                'position_side': 'long' if safe_float(position.get('contracts')) > 0 else 'short' if safe_float(position.get('contracts')) < 0 else 'none',
                'position_size': abs(safe_float(position.get('contracts'))),
                'entry_price': safe_float(position.get('entryPrice')),
                'current_price': safe_float(position.get('markPrice')),
                'liquidation_price': safe_float(position.get('liquidationPrice')),
                'leverage': safe_float(position.get('leverage')),
                'unrealized_pnl': safe_float(position.get('unrealizedPnl')),
                'roe': safe_float(position.get('percentage'))
            }
            return position_info
        except Exception as e:
            logger.error(f"포지션 정보 조회 중 에러 발생: {e}")
            raise

    def prepare_account_status(self, symbol: str = "BTCUSDT") -> str:
        """계정 상태 정보를 문자열로 포맷팅"""
        try:
            wallet = self.get_wallet_info()
            position = self.get_position_info(symbol)
            
            status = f"""
=== 계정 상태 ===
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[지갑 정보]
총 자산가치: {safe_float(wallet['total_equity']):.2f} USDT
사용 가능 잔액: {safe_float(wallet['available_balance']):.2f} USDT
사용 중인 증거금: {safe_float(wallet['used_margin']):.2f} USDT
미실현 손익: {safe_float(wallet['unrealized_pnl']):.2f} USDT
실현 손익: {safe_float(wallet['realized_pnl']):.2f} USDT

[포지션 정보]
심볼: {symbol}
포지션 여부: {'있음' if position['has_position'] else '없음'}"""

            if position['has_position']:
                status += f"""
포지션 방향: {'롱' if position['position_side'] == 'long' else '숏'}
포지션 크기: {position['position_size']} 계약
진입가격: {safe_float(position['entry_price']):.2f} USDT
현재가격: {safe_float(position['current_price']):.2f} USDT
청산가격: {safe_float(position['liquidation_price']):.2f} USDT
레버리지: {position['leverage']}x
미실현 손익: {safe_float(position['unrealized_pnl']):.2f} USDT
수익률: {safe_float(position['roe']):.2f}%"""
            
            return status
            
        except Exception as e:
            logger.error(f"계좌 상태 조회 중 에러 발생: {e}")
            return "계좌 상태 조회 실패" 