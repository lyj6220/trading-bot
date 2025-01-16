from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine('sqlite:///trading_history.db')
Session = sessionmaker(bind=engine)

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    position_type = Column(String)
    leverage = Column(Integer)
    investment_ratio = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    size = Column(Float)
    status = Column(String)
    profit_loss = Column(Float, nullable=True)
    profit_loss_percentage = Column(Float, nullable=True)
    decision_reason = Column(Text)
    timestamp = Column(DateTime)

class TradingLog(Base):
    __tablename__ = 'trading_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    log_type = Column(String)
    message = Column(String)
    position_type = Column(String, nullable=True)
    profit_loss = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<TradingLog(timestamp={self.timestamp}, type={self.log_type}, message={self.message})>"

# 데이터베이스 테이블 생성
Base.metadata.create_all(engine) 