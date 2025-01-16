import os
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from data_collector import MarketDataCollector
from fundamental_analyzer import FundamentalAnalyzer
from sentiment_analyzer import SentimentAnalyzer
from external_analyzer import ExternalAnalyzer
from trading_advisor import TradingAdvisor
from wallet_position_tracker import WalletPositionTracker
from trade_executor import TradeExecutor
from database_updater import log_trade, update_trade, log_message
from models import Session, Trade, TradingLog
from sqlalchemy import func
import logging
from pyngrok import ngrok
from bybit_client import BybitClient
import json

# Flask 앱 초기화
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 라우트 정의
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/trading_stats')
def get_trading_stats():
    session = Session()
    try:
        def safe_float(value):
            if value is None or str(value).strip() == '' or str(value).strip() == 'None':
                return None
            try:
                return float(str(value).strip())
            except (ValueError, TypeError):
                return None

        # DB에서 모든 거래 내역 조회
        all_trades = session.query(Trade).all()
        
        # 현재 활성 포지션의 수익률 계산Trading History
        current_trade = session.query(Trade).filter(
            Trade.status.ilike('open')
        ).order_by(Trade.timestamp.desc()).first()
        
        current_profit_rate = 0.0
        if current_trade:
            client = BybitClient()
            position = client.client.get_positions(
                category="linear",
                symbol=current_trade.symbol
            )
            
            if position and position.get('result', {}).get('list'):
                pos_info = position['result']['list'][0]
                unrealized_pnl = safe_float(pos_info.get('unrealisedPnl', '0'))
                position_value = safe_float(pos_info.get('positionValue', '0'))
                if position_value and position_value > 0:
                    current_profit_rate = (unrealized_pnl / position_value) * 100
        
        # 거래 내역 정규화
        trades = []
        for t in all_trades:
            try:
                position = str(t.position_type).upper().strip() if t.position_type else ''
                if position in ['LONG', 'SHORT->LONG']:
                    normalized_position = 'LONG'
                elif position in ['SHORT', 'LONG->SHORT']:
                    normalized_position = 'SHORT'
                else:
                    normalized_position = 'UNKNOWN'
                
                profit_loss = safe_float(t.profit_loss)
                profit_loss_percentage = safe_float(t.profit_loss_percentage)
                
                if t.status and t.status.lower() == 'closed' and profit_loss_percentage is not None:
                    trades.append({
                        'position_type': normalized_position,
                        'profit_loss': profit_loss if profit_loss is not None else 0.0,
                        'profit_loss_percentage': profit_loss_percentage,
                        'status': 'closed'
                    })
                
            except Exception as e:
                logger.error(f"거래 데이터 처리 중 오류: {e}, trade_id: {t.id}")
                continue
        
        # 통계 계산
        total_trades = len([t for t in all_trades if t.status and t.status.lower() == 'closed'])
        long_trades = sum(1 for t in all_trades if t.status and t.status.lower() == 'closed' and 
                         str(t.position_type).upper().strip() in ['LONG', 'SHORT->LONG'])
        short_trades = sum(1 for t in all_trades if t.status and t.status.lower() == 'closed' and 
                          str(t.position_type).upper().strip() in ['SHORT', 'LONG->SHORT'])
        
        # 평균 수익률과 누적 수익률 계산
        profit_percentages = [t['profit_loss_percentage'] for t in trades if abs(t['profit_loss_percentage']) > 0.0001]
        
        if profit_percentages:
            # 누적 수익률 = 각 거래의 수익률의 합
            cumulative_profit = sum(profit_percentages)
            
            # 평균 수익률 = 각 거래의 수익률의 평균
            avg_profit = sum(profit_percentages) / len(profit_percentages)
            
            # 소수점 2자리로 반올림
            cumulative_profit = round(cumulative_profit, 2)
            avg_profit = round(avg_profit, 2)
        else:
            cumulative_profit = 0.0
            avg_profit = 0.0
        
        response = {
            'current_position': {
                'current_profit': round(current_profit_rate, 2)
            },
            'trading_stats': {
                'total_trades': int(total_trades),
                'long_trades': int(long_trades),
                'short_trades': int(short_trades),
                'avg_profit': cumulative_profit,  # 누적 수익률
                'cumulative_profit': avg_profit   # 평균 수익률
            }
        }
        
        logger.info(f"수익률 계산:")
        logger.info(f"원본 수익률 목록: {profit_percentages}")
        logger.info(f"누적 수익률 (합계): {cumulative_profit}")
        logger.info(f"평균 수익률: {avg_profit}")
        logger.info(f"최종 응답 (JSON): {json.dumps(response)}")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"거래 통계 조회 실패: {str(e)}")
        return jsonify({
            'current_position': {
                'current_profit': 0.00
            },
            'trading_stats': {
                'total_trades': 0,
                'long_trades': 0,
                'short_trades': 0,
                'avg_profit': 0.00,
                'cumulative_profit': 0.00
            }
        })
    finally:
        session.close()

def safe_float(value, default=0.0):
    """안전한 float 변환 함수"""
    if value is None or str(value).strip() == '' or str(value).strip() == 'None':
        return default
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default

@app.route('/api/trading_history')
def get_trading_history():
    session = Session()
    try:
        trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(100).all()
        
        if not trades:
            return jsonify({
                'trades': [],
                'pagination': {
                    'current_page': 1,
                    'total_pages': 0,
                    'total_trades': 0,
                    'per_page': 100
                }
            })
        
        history = [{
            'timestamp': trade.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': trade.symbol,
            'position_type': trade.position_type,
            'leverage': trade.leverage,
            'entry_price': f"{safe_float(trade.entry_price):.2f}" if trade.entry_price else "-",
            'exit_price': f"{safe_float(trade.exit_price):.2f}" if trade.exit_price and trade.status == 'Closed' else "-",
            'profit_loss': round(safe_float(trade.profit_loss), 2),
            'profit_loss_percentage': round(safe_float(trade.profit_loss_percentage), 2),
            'status': trade.status,
            'investment_ratio': trade.investment_ratio,
            'decision_reason': trade.decision_reason
        } for trade in trades]
        
        return jsonify({
            'trades': history,
            'pagination': {
                'current_page': 1,
                'total_pages': 1,
                'total_trades': len(trades),
                'per_page': 100
            }
        })
        
    except Exception as e:
        logger.error(f"거래 내역 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

def calculate_pnl(trade):
    """PnL % 계산 함수"""
    try:
        if trade.status == 'Closed' and trade.entry_price and trade.exit_price:
            entry_price = float(trade.entry_price)
            exit_price = float(trade.exit_price)
            leverage = float(trade.leverage)
            
            if trade.position_type == 'HOLD':
                return 0.0
            elif trade.position_type in ['LONG', 'SHORT->LONG']:
                return round(((exit_price - entry_price) / entry_price) * 100 * leverage, 2)
            elif trade.position_type in ['SHORT', 'LONG->SHORT']:
                return round(((entry_price - exit_price) / entry_price) * 100 * leverage, 2)
        return 0.0
    except Exception as e:
        logger.error(f"PnL 계산 중 오류: {e}")
        return 0.0

@app.route('/api/decision_distribution')
def get_decision_distribution():
    session = Session()
    decisions = session.query(
        Trade.position_type, 
        func.count(Trade.id)
    ).group_by(Trade.position_type).all()
    
    session.close()
    return jsonify(dict(decisions))

@app.route('/api/trading_logs')
def get_trading_logs():
    session = Session()
    try:
        logs = session.query(TradingLog).order_by(TradingLog.timestamp.desc()).limit(100).all()
        
        if not logs:
            return jsonify({
                'logs': [],
                'stats': {
                    'error_count': 0,
                    'trade_count': 0,
                    'info_count': 0
                }
            })
        
        log_list = [{
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'type': log.log_type,
            'message': log.message,
            'details': {
                'position_type': log.position_type,
                'profit_loss': round(log.profit_loss, 2) if log.profit_loss else None
            },
            'severity': 'high' if log.log_type in ['Error', 'Trade'] else 'normal'
        } for log in logs]
        
        return jsonify({
            'logs': log_list,
            'stats': {
                'error_count': sum(1 for log in logs if log.log_type == 'Error'),
                'trade_count': sum(1 for log in logs if log.log_type == 'Trade'),
                'info_count': sum(1 for log in logs if log.log_type == 'Info')
            }
        })
        
    except Exception as e:
        logger.error(f"거래 로그 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/current_position')
def get_current_position():
    try:
        executor = TradeExecutor(
            api_key=os.getenv('BYBIT_API_KEY'),
            secret_key=os.getenv('BYBIT_SECRET_KEY')
        )
        position = executor._get_current_position("BTCUSDT")
        
        # 현재가 조회
        response = executor.client.get_tickers(
            category="linear",
            symbol="BTCUSDT"
        )
        current_price = float(response['result']['list'][0]['lastPrice'])
        
        return jsonify({
            'side': position.get('side', 'NONE'),
            'entry_price': position.get('entry_price', '0'),
            'current_price': current_price,
            'size': position.get('size', '0'),
            'leverage': position.get('leverage', '0'),
            'unrealized_pnl': position.get('unrealised_pnl', '0')
        })
    except Exception as e:
        logger.error(f"현재 포지션 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500

def wait_for_next_hour():
    """다음 시간봉 시작까지 대기"""
    now = datetime.now()
    # 현재 시간이 정각 + 1분 이전이면 다음 정각 + 1분까지 대기
    # 현재 시간이 정각 + 1분 이후면 다음 정각 + 1분까지 대기
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    if now >= next_hour:
        next_hour += timedelta(hours=1)
    
    target_time = next_hour + timedelta(minutes=1)  # 정각 후 1분
    wait_seconds = (target_time - now).total_seconds()
    
    if wait_seconds > 0:
        logger.info(f"다음 실행까지 {wait_seconds:.0f}초 대기")
        logger.info(f"다음 실행 시간: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(wait_seconds)

def run_trading_bot():
    """트레이딩 봇 실행"""
    while True:
        try:
            # 다음 실행 시간까지 대기
            wait_for_next_hour()
            
            current_time = datetime.now()
            logger.info(f"=== 트레이딩 봇 실행 시작 ===")
            logger.info(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # API 키 가져오기
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_SECRET_KEY')
            
            if not api_key or not api_secret:
                raise ValueError("API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            
            # 데이터 수집 및 분석
            collector = MarketDataCollector(
                api_key=api_key,
                secret_key=api_secret
            )
            symbol = "BTCUSDT"
            technical_analysis = collector.prepare_llm_input(symbol=symbol, timeframe="1h")
            
            fundamental_analyzer = FundamentalAnalyzer()
            fundamental_analysis = fundamental_analyzer.prepare_fundamental_analysis()
            
            sentiment_analyzer = SentimentAnalyzer()
            sentiment_analysis = sentiment_analyzer.prepare_sentiment_analysis()
            
            external_analyzer = ExternalAnalyzer()
            external_analysis = external_analyzer.prepare_external_analysis()
            
            # 지갑 및 포지션 상태 조회
            wallet_tracker = WalletPositionTracker(
                api_key=api_key,
                secret_key=api_secret
            )
            account_status = wallet_tracker.prepare_account_status(symbol="BTCUSDT")
            
            # 트레이딩 조언 얻기
            trading_advisor = TradingAdvisor()
            decision, full_analysis = trading_advisor.get_trading_advice(
                f"{account_status}\n{technical_analysis}\n{fundamental_analysis}\n{sentiment_analysis}\n{external_analysis}"
            )
            
            # 트레이딩 실행
            executor = TradeExecutor(
                api_key=api_key,
                secret_key=api_secret
            )
            symbol = "BTCUSDT"
            
            # 포지션 신호 표준화
            position_mapping = {
                'CLOSE': ['CLOSE', 'Close', 'close'],
                'LONG->SHORT': ['LONG->SHORT', 'Long->Short', 'long->short'],
                'SHORT->LONG': ['SHORT->LONG', 'Short->Long', 'short->long'],
                'LONG': ['LONG', 'Long', 'long'],
                'SHORT': ['SHORT', 'Short', 'short'],
                'HOLD': ['HOLD', 'Hold', 'hold']
            }
            
            position_signal = decision.get('position', 'Hold')
            for standard_position, variants in position_mapping.items():
                if position_signal in variants:
                    decision['position'] = standard_position
                    break
            else:
                decision['position'] = 'HOLD'
            
            logger.info(f"결정된 포지션: {decision['position']}")
            
            # TradeExecutor로 거래 실행
            try:
                result = executor.execute_trade(symbol=symbol, trading_decision=decision)
                current_price = executor.get_current_price(symbol)
                
                # HOLD 포지션도 로그에 기록
                log_trade(
                    symbol=symbol,
                    position_type=decision['position'],
                    leverage=int(decision.get('leverage', 0)),
                    investment_ratio=float(decision.get('investment_ratio', 0)),
                    entry_price=current_price,
                    decision_reason=full_analysis
                )
                
                if result:
                    log_message("Info", f"{decision['position']} 포지션 실행 완료")
                    update_trade(symbol, current_price)
                else:
                    if decision['position'] == 'HOLD':
                        log_message("Info", "HOLD 포지션 유지")
                    else:
                        log_message("Info", "거래 실행 건너뜀")
                        
            except Exception as e:
                log_message("Error", "거래 실행 중 예외 발생: " + str(e))
            
            logger.info("=== 트레이딩 봇 실행 완료 ===\n")
            
        except Exception as e:
            logger.error(f"에러 발생: {e}")
            log_message("Error", f"에러 발생: {e}")
            time.sleep(60)  # 에러 발생 시 1분 대기 후 재시도

def main():
    load_dotenv()
    
    # ngrok 설정
    ngrok.set_auth_token("2rQwph3pj5pEYKaOjzdwhv8JFPX_7nfwq2BgmjEeg6vhBz6PB")
    try:
        public_url = ngrok.connect(5000)
        logger.info(f"\n=== 대시보드 접속 URL ===\n{public_url}\n")
    except Exception as e:
        logger.error(f"ngrok 연결 실패: {e}")
        logger.info("로컬 URL로 실행: http://localhost:5000")
    
    logger.info("트레이딩 봇 시작")
    
    # 트레이딩 봇 스레드 시작
    trading_thread = threading.Thread(target=run_trading_bot)
    trading_thread.daemon = True
    trading_thread.start()
    
    # Flask 웹 서버 시작
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main() 