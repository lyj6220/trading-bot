import requests
import logging
from typing import Dict, List
from datetime import datetime
import json
from pytrends.request import TrendReq
from textblob import TextBlob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.dominance_url = "https://api.coingecko.com/api/v3/global"
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.pytrends = TrendReq(hl='en-US', tz=360)
        
    def _get_fear_greed_index(self) -> Dict:
        """공포와 탐욕 지수 수집"""
        try:
            # Alternative Fear & Greed Index API
            response = requests.get(
                "https://api.alternative.me/fng/"
            ).json()
            
            data = response.get('data', [{}])[0]
            return {
                'value': int(data.get('value', 0)),
                'classification': data.get('value_classification', 'Neutral'),
                'timestamp': data.get('timestamp', '')
            }
        except Exception as e:
            logger.error(f"공포/탐욕 지수 수집 오류: {e}")
            return {}

    def _get_social_trends(self) -> Dict:
        """소셜 미디어 트렌드 분석"""
        try:
            # Google Trends 데이터
            self.pytrends.build_payload(['bitcoin', 'crypto', 'btc'], timeframe='now 7-d')
            interest_over_time = self.pytrends.interest_over_time()
            
            # 최근 검색 트렌드
            recent_trend = interest_over_time['bitcoin'].iloc[-1]
            prev_trend = interest_over_time['bitcoin'].iloc[-2]
            
            return {
                'current_interest': recent_trend,
                'trend': 'increasing' if recent_trend > prev_trend else 'decreasing',
                'change_percent': ((recent_trend - prev_trend) / prev_trend * 100) if prev_trend > 0 else 0
            }
        except Exception as e:
            logger.error(f"소셜 트렌드 수집 오류: {e}")
            return {}

    def _get_news_sentiment(self) -> List[Dict]:
        """뉴스 헤드라인과 본문 기반 감성 분석"""
        try:
            response = requests.get(
                "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=BTC"
            ).json()
            
            news_data = []
            for news in response.get('Data', [])[:10]:  # 최근 10개 뉴스
                # 제목과 본문 모두 분석
                headline = news.get('title', '')
                body = news.get('body', '')
                
                # 제목과 본문의 감성 점수를 각각 계산하고 가중 평균
                headline_sentiment = TextBlob(headline).sentiment.polarity
                body_sentiment = TextBlob(body).sentiment.polarity
                
                # 제목:본문 = 40:60 비율로 가중치 부여
                weighted_sentiment = (headline_sentiment * 0.4) + (body_sentiment * 0.6)
                
                news_data.append({
                    'headline': headline,
                    'sentiment_score': round(weighted_sentiment, 2),
                    'source': news.get('source', '')
                })
            
            return news_data
        except Exception as e:
            logger.error(f"뉴스 수집 오류: {e}")
            return []

    def _get_market_dominance(self) -> Dict:
        """비트코인 도미넌스 분석"""
        try:
            # CoinGecko Global Data
            response = requests.get(
                f"{self.coingecko_base_url}/global"
            ).json()
            
            market_data = response.get('data', {}).get('market_cap_percentage', {})
            btc_dominance = market_data.get('btc', 0)
            
            return {
                'btc_dominance': round(btc_dominance, 2),
                'market_state': 'bitcoin_led' if btc_dominance > 45 else 'altcoin_season'
            }
        except Exception as e:
            logger.error(f"도미넌스 데이터 수집 오류: {e}")
            return {}

    def prepare_sentiment_analysis(self) -> str:
        """시장 심리 분석 데이터 준비"""
        try:
            # 도미넌스 데이터 수집
            response = requests.get(self.dominance_url)
            if response.status_code != 200:
                logger.error("도미넌스 데이터 수집 실패")
                return "도미넌스 데이터를 수집할 수 없습니다."
            
            dominance_data = response.json()
            btc_dominance = dominance_data.get('data', {}).get('market_cap_percentage', {}).get('btc', 0)
            
            # 공포탐욕지수 수집
            fear_response = requests.get(self.fear_greed_url)
            if fear_response.status_code != 200:
                logger.error("공포탐욕지수 수집 실패")
                return "공포탐욕지수를 수집할 수 없습니다."
            
            fear_data = fear_response.json()
            fear_value = fear_data.get('data', [{}])[0].get('value', 0)
            
            analysis = f"""시장 심리 분석:
            - BTC 도미넌스: {btc_dominance:.2f}%
            - 공포탐욕지수: {fear_value}
            """
            
            return analysis
            
        except Exception as e:
            logger.error(f"시장 심리 분석 오류: {e}")
            return "시장 심리 분석을 수행할 수 없습니다."
        
        fear_greed = self._get_fear_greed_index()
        social_trends = self._get_social_trends()
        news_data = self._get_news_sentiment()
        dominance = self._get_market_dominance()
        
        analysis = f"""
심리적 분석 리포트 - BTC
시간: {datetime.now().isoformat()}

1. 시장 심리:
공포와 탐욕 지수:
- 현재 수치: {fear_greed.get('value', 'N/A')}
- 상태: {fear_greed.get('classification', 'N/A')}

소셜 미디어 트렌드:
- 검색 관심도: {social_trends.get('current_interest', 'N/A')}
- 트렌드: {social_trends.get('trend', 'N/A')} ({social_trends.get('change_percent', 'N/A'):.1f}% 변화)

주요 뉴스 헤드라인:
{chr(10).join([f"- {news['headline']} (감성점수: {news['sentiment_score']}, 출처: {news['source']})" for news in news_data])}

2. 시장 구조:
비트코인 도미넌스:
- 현재 비중: {dominance.get('btc_dominance', 'N/A')}%
- 시장 상태: {dominance.get('market_state', 'N/A')}
"""
        return analysis 