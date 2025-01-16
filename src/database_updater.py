from models import Session, Trade, TradingLog
from datetime import datetime
import pytz
import logging
from bybit_client import BybitClient
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_trade(
    symbol: str,
    position_type: str,
    leverage: int,
    investment_ratio: float,
    entry_price: float,
    decision_reason: str
):
    """새로운 거래 기록 - 매매일지 형식"""
    session = Session()
    try:
        # CLOSE가 아닌 경우에만 실제 포지션 정보 확인
        if position_type != 'CLOSE':
            client = BybitClient()
            try:
                # 실제 포지션 정보 가져오기
                position = client.client.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                if position and position.get('result', {}).get('list'):
                    pos_info = position['result']['list'][0]
                    # 실제 진입가격으로 업데이트
                    entry_price = float(pos_info.get('avgPrice', entry_price))
                    # 실제 사이즈 정보도 저장
                    size = float(pos_info.get('size', '0'))
            except Exception as e:
                logger.error(f"포지션 정보 조회 중 오류: {e}")

        # 거래 정보 DB 저장
        if position_type != 'CLOSE':
            trade = Trade(
                symbol=symbol,
                position_type=position_type,
                leverage=leverage,
                investment_ratio=investment_ratio,
                entry_price=entry_price,
                size=size,  # 사이즈 정보 추가
                status='Open',
                decision_reason=decision_reason,
                timestamp=datetime.now()
            )
            session.add(trade)
        
        # 매매일지 형식으로 포맷팅
        trading_log = f"""
=== 매매 분석 일지 ===
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
심볼: {symbol}
포지션: {position_type}
레버리지: {leverage}x
투자비중: {investment_ratio}%
진입가격: {entry_price}
포지션 크기: {size}

[결정근거]
{decision_reason}
"""
        
        # 거래 로그는 모든 경우에 기록
        log_message(
            "Trade",
            trading_log,
            position_type=position_type,
            llm_response=decision_reason
        )
        
        session.commit()
    except Exception as e:
        logger.error(f"거래 기록 중 에러 발생: {e}")
        session.rollback()
    finally:
        session.close()

def calculate_trading_stats():
    """Trading History 데이터를 기반으로 거래 통계 계산"""
    session = Session()
    try:
        # 모든 거래 내역 조회
        trades = session.query(Trade).all()
        closed_trades = [t for t in trades if t.status == 'Closed']
        
        # 현재 활성화된 포지션 찾기
        current_trade = session.query(Trade).filter(
            Trade.status == 'Open'
        ).order_by(Trade.timestamp.desc()).first()
        
        # 통계 계산
        stats = {
            'total_trades': len(closed_trades),
            'long_trades': sum(1 for t in closed_trades if t.position_type == 'LONG'),
            'short_trades': sum(1 for t in closed_trades if t.position_type == 'SHORT'),
            'cumulative_profit': sum(t.profit_loss or 0 for t in closed_trades),
            'average_profit': 0,
            'current_profit_rate': 0
        }
        
        # 평균 수익률 계산
        if stats['total_trades'] > 0:
            stats['average_profit'] = sum(t.profit_loss_percentage or 0 for t in closed_trades) / stats['total_trades']
        
        # 현재 수익률 계산 (활성 포지션이 있는 경우)
        if current_trade:
            client = BybitClient()
            position = client.client.get_positions(
                category="linear",
                symbol=current_trade.symbol
            )
            
            if position and position.get('result', {}).get('list'):
                pos_info = position['result']['list'][0]
                unrealized_pnl = float(pos_info.get('unrealisedPnl', '0'))
                position_value = float(pos_info.get('positionValue', '0'))
                if position_value > 0:
                    stats['current_profit_rate'] = (unrealized_pnl / position_value) * 100
        
        return stats
        
    except Exception as e:
        logger.error(f"거래 통계 계산 중 오류 발생: {e}")
        return None
    finally:
        session.close()

def update_trade(symbol: str, exit_price: float):
    """거래 업데이트 (포지션 종료 시)"""
    session = Session()
    try:
        # 가장 최근의 Open 상태인 거래를 찾습니다
        trade = session.query(Trade).filter(
            Trade.symbol == symbol,
            Trade.status == 'Open'
        ).order_by(Trade.timestamp.desc()).first()
        
        if trade:
            client = BybitClient()
            try:
                # 실제 포지션 정보 확인
                position = client.client.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                # 이전 거래들의 상태를 Closed로 업데이트
                previous_trades = session.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.status == 'Open',
                    Trade.id != trade.id  # 현재 거래 제외
                ).all()
                
                for prev_trade in previous_trades:
                    prev_trade.status = 'Closed'
                    prev_trade.exit_price = exit_price
                
                # 현재 포지션이 없는 경우, 가장 최근 거래도 Closed로 업데이트
                if not position or not position.get('result', {}).get('list'):
                    trade.status = 'Closed'
                    trade.exit_price = exit_price
                    
                session.commit()
                logger.info(f"거래 상태 업데이트 완료: {trade.id}")
                return True
                
            except Exception as e:
                logger.error(f"포지션 정보 조회 중 오류: {e}")
                return False
                
    except Exception as e:
        logger.error(f"거래 업데이트 중 에러 발생: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def log_message(log_type: str, message: str, position_type: str = None, profit_loss: float = None, **kwargs):
    """거래 로그 기록"""
    session = Session()
    try:
        log = TradingLog(
            timestamp=datetime.now(),
            log_type=log_type,
            message=message,
            position_type=position_type,
            profit_loss=profit_loss
        )
        session.add(log)
        session.commit()
        
    except Exception as e:
        logger.error(f"로그 기록 중 에러 발생: {e}")
        session.rollback()
    finally:
        session.close()