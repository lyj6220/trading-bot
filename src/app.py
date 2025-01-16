from flask import Flask, render_template, jsonify
from models import Session, Trade, TradingLog
from sqlalchemy import func
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/trading_stats')
def get_trading_stats():
    session = Session()
    
    # 전체 거래 통계
    total_trades = session.query(Trade).count()
    long_trades = session.query(Trade).filter(Trade.position_type == 'Long').count()
    short_trades = session.query(Trade).filter(Trade.position_type == 'Short').count()
    
    # 수익률 계산
    closed_trades = session.query(Trade).filter(Trade.status == 'Closed').all()
    if closed_trades:
        avg_profit = sum(trade.profit_loss_percentage for trade in closed_trades) / len(closed_trades)
    else:
        avg_profit = 0
    
    # 현재 수익률 (최근 24시간)
    recent_trades = session.query(Trade).filter(
        Trade.timestamp >= datetime.utcnow() - timedelta(days=1)
    ).all()
    current_profit = sum(trade.profit_loss_percentage or 0 for trade in recent_trades)
    
    session.close()
    
    return jsonify({
        'total_trades': total_trades,
        'long_trades': long_trades,
        'short_trades': short_trades,
        'avg_profit': round(avg_profit, 2),
        'current_profit': round(current_profit, 2)
    })

@app.route('/api/trading_history')
def get_trading_history():
    session = Session()
    trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
    
    history = [{
        'timestamp': trade.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': trade.symbol,
        'position_type': trade.position_type,
        'leverage': trade.leverage,
        'profit_loss': round(trade.profit_loss or 0, 2),
        'profit_loss_percentage': round(trade.profit_loss_percentage or 0, 2),
        'status': trade.status
    } for trade in trades]
    
    session.close()
    return jsonify(history)

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
    logs = session.query(TradingLog).order_by(TradingLog.timestamp.desc()).limit(100).all()
    
    log_list = [{
        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'type': log.log_type,
        'message': log.message
    } for log in logs]
    
    session.close()
    return jsonify(log_list)

if __name__ == '__main__':
    app.run(debug=True) 