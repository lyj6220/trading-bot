from datetime import datetime
from models import Session, Trade, TradingLog
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_message(log_type: str, message: str, position_type: str = None, profit_loss: float = None, decision_reason: str = None, **kwargs):
    """거래 로그 기록"""
    session = Session()
    try:
        if decision_reason:
            message = f"{message}\n결정근거: {decision_reason}"
            
        log = TradingLog(
            timestamp=datetime.now(),
            log_type=log_type,
            message=message,
            position_type=position_type,
            profit_loss=profit_loss
        )
        session.add(log)
        session.commit()
        logger.info(f"로그 기록: [{log_type}] {message}")
        
    except Exception as e:
        logger.error(f"로그 기록 중 오류 발생: {e}")
        session.rollback()
    finally:
        session.close()

def update_trade(symbol: str, current_price: float):
    """거래 업데이트"""
    session = Session()
    try:
        trade = session.query(Trade).filter(
            Trade.symbol == symbol,
            Trade.status == 'Open'
        ).order_by(Trade.timestamp.desc()).first()
        
        if trade:
            trade.exit_price = current_price
            session.commit()
            logger.info(f"거래 업데이트: {symbol}, 현재가: {current_price}")
            
    except Exception as e:
        logger.error(f"거래 업데이트 중 오류 발생: {e}")
        session.rollback()
    finally:
        session.close()

def log_trade(symbol: str, position_type: str, leverage: int, 
              investment_ratio: float, entry_price: float, 
              decision_reason: str = None):
    """거래 기록"""
    session = Session()
    try:
        # CLOSE 포지션인 경우 이전 포지션 처리
        if position_type == 'CLOSE':
            open_trade = session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'Open'
            ).order_by(Trade.timestamp.desc()).first()
            
            if open_trade:
                open_trade.exit_price = entry_price
                open_trade.status = 'Closed'
                if open_trade.entry_price and entry_price:
                    leverage = float(open_trade.leverage or 1)
                    if open_trade.position_type in ['LONG', 'SHORT->LONG']:
                        pnl = ((entry_price - open_trade.entry_price) / open_trade.entry_price) * 100 * leverage
                    elif open_trade.position_type in ['SHORT', 'LONG->SHORT']:
                        pnl = ((open_trade.entry_price - entry_price) / open_trade.entry_price) * 100 * leverage
                    else:
                        pnl = 0
                    open_trade.profit_loss_percentage = pnl
                session.commit()
                log_message("Trade", f"포지션 청산 완료: {symbol}, PnL: {pnl:.2f}%", position_type=position_type, profit_loss=pnl)
                return
            
        # 포지션 스위칭 처리 (LONG->SHORT 또는 SHORT->LONG)
        if position_type in ['LONG->SHORT', 'SHORT->LONG']:
            open_trade = session.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'Open'
            ).order_by(Trade.timestamp.desc()).first()
            
            if open_trade:
                open_trade.exit_price = entry_price
                open_trade.status = 'Closed'
                if open_trade.entry_price and entry_price:
                    leverage = float(open_trade.leverage or 1)
                    if open_trade.position_type in ['LONG', 'SHORT->LONG']:
                        pnl = ((entry_price - open_trade.entry_price) / open_trade.entry_price) * 100 * leverage
                    elif open_trade.position_type in ['SHORT', 'LONG->SHORT']:
                        pnl = ((open_trade.entry_price - entry_price) / open_trade.entry_price) * 100 * leverage
                    open_trade.profit_loss_percentage = pnl
                session.commit()
                log_message("Trade", f"포지션 스위칭 - 이전 포지션 청산: {symbol}, PnL: {pnl:.2f}%", position_type=position_type, profit_loss=pnl)
            
        # HOLD 포지션 처리
        if position_type == 'HOLD':
            log_message("Info", f"HOLD 포지션 유지: {symbol}", position_type=position_type)
            return
            
        # 새로운 포지션 생성 (LONG, SHORT, LONG->SHORT, SHORT->LONG)
        if position_type not in ['CLOSE', 'HOLD'] and entry_price > 0:
            trade = Trade(
                timestamp=datetime.now(),
                symbol=symbol,
                position_type=position_type,
                leverage=leverage,
                entry_price=entry_price,
                investment_ratio=investment_ratio,
                decision_reason=decision_reason,
                status='Open'
            )
            session.add(trade)
            session.commit()
            log_message("Trade", 
                        f"새로운 포지션 진입: {symbol}, {position_type}, 진입가: {entry_price}", 
                        position_type=position_type,
                        decision_reason=decision_reason)
            
    except Exception as e:
        logger.error(f"거래 기록 중 오류 발생: {e}")
        log_message("Error", f"거래 기록 실패: {str(e)}")
        session.rollback()
    finally:
        session.close()