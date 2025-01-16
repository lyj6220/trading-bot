from models import Session, Trade, TradingLog
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_trades():
    """거래 내역 확인"""
    session = Session()
    try:
        trades = session.query(Trade).order_by(Trade.timestamp.desc()).all()
        logger.info(f"\n=== 전체 거래 내역 ({len(trades)}개) ===")
        
        for trade in trades:
            # 결정 이유 전체 표시
            decision_reason = trade.decision_reason if trade.decision_reason else ''
            
            logger.info(f"""
시간: {trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
심볼: {trade.symbol}
포지션: {trade.position_type}
레버리지: {trade.leverage}x
진입가격: {trade.entry_price or 0:.2f}
청산가격: {trade.exit_price or 0:.2f}
수익률: {trade.profit_loss_percentage or 0:.2f}% 
상태: {trade.status}
투자비율: {trade.investment_ratio or 0}
결정이유:
{decision_reason}
-----------------------------------------""")
    except Exception as e:
        logger.error(f"거래 내역 조회 실패: {str(e)}")
    finally:
        session.close()

def check_recent_trades(hours=24):
    """최근 거래 내역 확인"""
    session = Session()
    try:
        recent_time = datetime.now() - timedelta(hours=hours)
        trades = session.query(Trade).filter(
            Trade.timestamp >= recent_time
        ).order_by(Trade.timestamp.desc()).all()
        
        logger.info(f"\n=== 최근 {hours}시간 거래 내역 ({len(trades)}개) ===")
        
        for trade in trades:
            logger.info(f"""
시간: {trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
심볼: {trade.symbol}
포지션: {trade.position_type}
상태: {trade.status}
PnL: {trade.profit_loss_percentage or 0:.2f}%
-----------------------------------------""")
    except Exception as e:
        logger.error(f"최근 거래 내역 조회 실패: {str(e)}")
    finally:
        session.close()

def check_trading_logs():
    """거래 로그 확인"""
    session = Session()
    try:
        logs = session.query(TradingLog).order_by(TradingLog.timestamp.desc()).limit(100).all()
        logger.info(f"\n=== 최근 거래 로그 ({len(logs)}개) ===")
        
        for log in logs:
            logger.info(f"""
시간: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
타입: {log.log_type}
메시지: {log.message}
-----------------------------------------""")
    except Exception as e:
        logger.error(f"거래 로그 조회 실패: {str(e)}")
    finally:
        session.close()

def check_open_positions():
    """열린 포지션 확인"""
    session = Session()
    try:
        # 현재 열린 포지션 조회
        open_trades = session.query(Trade).filter(
            Trade.status == 'Open'
        ).order_by(Trade.timestamp.desc()).all()
        
        logger.info(f"\n=== 현재 열린 포지션 ({len(open_trades)}개) ===")
        
        for trade in open_trades:
            logger.info(f"""
시간: {trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
심볼: {trade.symbol}
포지션: {trade.position_type}
진입가격: {trade.entry_price}
레버리지: {trade.leverage}x
-----------------------------------------""")
    except Exception as e:
        logger.error(f"열린 포지션 조회 실패: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("=== 거래 내역 데이터베이스 확인 시작 ===")
    
    # 전체 거래 내역 확인
    check_trades()
    
    # 최근 24시간 거래 내역 확인
    check_recent_trades()
    
    # 거래 로그 확인
    check_trading_logs()
    
    # 열린 포지션 확인
    check_open_positions()
    
    logger.info("=== 거래 내역 데이터베이스 확인 완료 ===") 