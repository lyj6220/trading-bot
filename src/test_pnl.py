from models import Session, Trade

def check_pnl_calculation():
    session = Session()
    try:
        trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(10).all()
        
        for trade in trades:
            print("\n=== 거래 상세 정보 ===")
            print(f"시간: {trade.timestamp}")
            print(f"포지션: {trade.position_type}")
            print(f"레버리지: {trade.leverage}x")
            print(f"진입가: {trade.entry_price}")
            print(f"청산가: {trade.exit_price}")
            print(f"상태: {trade.status}")
            
            if trade.status == 'Closed' and trade.entry_price and trade.exit_price:
                entry_price = float(trade.entry_price)
                exit_price = float(trade.exit_price)
                leverage = float(trade.leverage)
                
                if trade.position_type == 'HOLD':
                    pnl = 0.0
                elif trade.position_type in ['LONG', 'SHORT->LONG']:
                    pnl = ((exit_price - entry_price) / entry_price) * 100 * leverage
                elif trade.position_type in ['SHORT', 'LONG->SHORT']:
                    pnl = ((entry_price - exit_price) / entry_price) * 100 * leverage
                
                print(f"계산된 PnL: {pnl:.2f}%")
            else:
                print("PnL 계산 불가 (미청산 또는 데이터 부족)")
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_pnl_calculation() 