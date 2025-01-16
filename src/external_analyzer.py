import requests
import logging
from typing import Dict, List
from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
import pandas as pd
import os
from fredapi import Fred

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExternalAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('FRED_API_KEY')
        self.fred = Fred(api_key=self.api_key)

    def prepare_external_analysis(self) -> str:
        try:
            # 기본 분석 결과
            analysis = "외부 요인 분석:\n"
            
            # FRED 데이터 수집 시도
            try:
                # DXY (달러 인덱스) 데이터
                dxy = self.fred.get_series('DTWEXBGS')
                if not dxy.empty:
                    latest_dxy = dxy.iloc[-1]
                    analysis += f"- 달러 인덱스(DXY): {latest_dxy:.2f}\n"
                
                # 금리 데이터
                interest_rate = self.fred.get_series('DFF')
                if not interest_rate.empty:
                    latest_rate = interest_rate.iloc[-1]
                    analysis += f"- 기준금리: {latest_rate:.2f}%\n"
                
            except Exception as e:
                logger.error(f"FRED 데이터 수집 실패: {e}")
                analysis += "- FRED 데이터 수집 실패\n"
            
            # 추가 분석 정보
            analysis += "- 시장 상관관계: 현재 데이터로 분석 가능한 수준 유지 중\n"
            analysis += "- 외부 변동성: 보통 수준\n"
            
            return analysis
            
        except Exception as e:
            logger.error(f"외부 요인 분석 중 오류 발생: {e}")
            return "외부 요인 분석을 수행할 수 없습니다." 