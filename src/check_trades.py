from models import Session, Trade

def check_trades():
    session = Session()
    try:
        trades = session.query(Trade).order_by(Trade.timestamp.desc()).all()
        print(f"총 거래 수: {len(trades)}")
        
        for trade in trades:
            print(f"""
거래 ID: {trade.id}
시간: {trade.timestamp}
심볼: {trade.symbol}
포지션: {trade.position_type}
레버리지: {trade.leverage}
진입가: {trade.entry_price}
청산가: {trade.exit_price}
상태: {trade.status}
-------------------""")
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_trades() 