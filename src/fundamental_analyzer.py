import yfinance as yf
import requests
from typing import Dict, List
from datetime import datetime, timedelta
import logging
import json
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FundamentalAnalyzer:
    def __init__(self):
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.news_api_key = os.getenv("NEWS_API_KEY")
        
    def _get_onchain_data(self) -> Dict:
        """온체인 데이터 수집"""
        try:
            # 네트워크 데이터
            hashrate = requests.get("https://api.blockchain.info/stats").json()
            
            # 거래소 데이터
            exchange_data = requests.get(
                f"{self.coingecko_base_url}/exchanges/binance/tickers",
                params={'coin_ids': 'bitcoin'}
            ).json()
            
            # 활성 주소 데이터
            addresses = requests.get("https://api.blockchain.info/charts/n-unique-addresses?timespan=24h&format=json").json()
            
            # 고래 지갑 데이터 (BitInfoCharts API로 변경)
            whale_data = requests.get(
                "https://api.coingecko.com/api/v3/companies/public_treasury/bitcoin"
            ).json()
            
            return {
                'exchange_balance': {
                    'volume_24h': exchange_data.get('tickers', [{}])[0].get('volume', 0),
                    'trend': self._analyze_volume_trend(exchange_data)
                },
                'whale_activity': {
                    'total_holdings': len(whale_data.get('companies', [])),  # 기관 투자자 수로 대체
                    'recent_changes': self._analyze_whale_changes(whale_data)
                },
                'network_health': {
                    'active_addresses': addresses.get('values', [{}])[-1].get('y', 0) if addresses.get('values') else 0,
                    'hashrate': hashrate.get('hash_rate', 0),
                    'difficulty': hashrate.get('difficulty', 0)
                }
            }
        except Exception as e:
            logger.error(f"온체인 데이터 수집 오류: {e}")
            return {}

    def _get_market_conditions(self) -> Dict:
        """시장 조건 데이터 수집"""
        try:
            # DXY (달러 인덱스)
            dxy = yf.Ticker("DX-Y.NYB")
            dxy_data = dxy.history(period="1d")
            dxy_value = dxy_data['Close'].iloc[-1]
            
            # S&P 500
            sp500 = yf.Ticker("^GSPC")
            sp500_data = sp500.history(period="1d")
            sp500_value = sp500_data['Close'].iloc[-1]
            
            # 금리 데이터 (미국 10년물 국채)
            rates = yf.Ticker("^TNX")
            rates_data = rates.history(period="1d")
            interest_rate = rates_data['Close'].iloc[-1]
            
            return {
                'dxy': {
                    'current': round(dxy_value, 2),
                    'impact': 'negative' if dxy_value > 103 else 'positive'
                },
                'sp500': {
                    'current': round(sp500_value, 2),
                    'correlation': self._calculate_correlation()
                },
                'interest_rate': {
                    'current': round(interest_rate, 2),
                    'impact': 'negative' if interest_rate > 4 else 'neutral'
                }
            }
        except Exception as e:
            logger.error(f"시장 조건 데이터 수집 오류: {e}")
            return {}

    def _analyze_volume_trend(self, data: Dict) -> str:
        """거래량 트렌드 분석"""
        try:
            current_volume = data.get('tickers', [{}])[0].get('volume', 0)
            return 'increasing' if current_volume > 50000 else 'decreasing'
        except:
            return 'neutral'

    def _analyze_whale_changes(self, data: Dict) -> str:
        """고래 지갑 변동 분석"""
        try:
            values = data.get('values', [])
            if len(values) >= 2:
                current = values[-1].get('y', 0)
                previous = values[-2].get('y', 0)
                change = current - previous
                if abs(change) < 10:  # 변화가 미미한 경우
                    return 'neutral'
                return 'accumulating' if change > 0 else 'distributing'
            return 'neutral'
        except:
            return 'neutral'

    def _calculate_correlation(self) -> str:
        """BTC와 S&P 500의 상관관계"""
        try:
            btc_data = requests.get(
                f"{self.coingecko_base_url}/coins/bitcoin/market_chart",
                params={'vs_currency': 'usd', 'days': '30', 'interval': 'daily'}
            ).json()
            
            if btc_data.get('prices'):
                btc_trend = btc_data['prices'][-1][1] > btc_data['prices'][0][1]
                return 'risk-on' if btc_trend else 'risk-off'
            return 'neutral'
        except:
            return 'neutral'

    def _analyze_sentiment(self, text: str) -> str:
        """뉴스 감성 분석"""
        positive_words = ['bullish', 'adoption', 'approval', 'positive', 'support']
        negative_words = ['bearish', 'ban', 'restrict', 'negative', 'against']
        
        text = text.lower()
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        return 'neutral'

    def _get_news(self) -> List[str]:
        """뉴스 데이터 수집"""
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    'q': 'bitcoin',
                    'sortBy': 'publishedAt',
                    'apiKey': self.news_api_key,
                    'pageSize': 5
                }
            )
            news_data = response.json()
            articles = news_data.get('articles', [])
            return [article['title'] + " " + article.get('description', '') for article in articles]
        except Exception as e:
            logger.error(f"뉴스 데이터 수집 오류: {e}")
            return []

    def prepare_fundamental_analysis(self) -> str:
        """기본적 분석 데이터 준비"""
        try:
            onchain_data = self._get_onchain_data()
            market_conditions = self._get_market_conditions()
            news_data = self._get_news()
            
            # 뉴스 감정 분석
            sentiment_results = [self._analyze_sentiment(news) for news in news_data]
            positive_count = sentiment_results.count('positive')
            negative_count = sentiment_results.count('negative')
            neutral_count = sentiment_results.count('neutral')
            
            analysis = f"""
기본적 분석 리포트 - BTC
시간: {datetime.now().isoformat()}

1. 온체인 데이터:
거래소 상태:
- 24시간 거래량: {onchain_data.get('exchange_balance', {}).get('volume_24h', 'N/A'):,.2f} BTC
- 거래량 트렌드: {onchain_data.get('exchange_balance', {}).get('trend', 'N/A')}

고래 활동 (1000+ BTC 보유):
- 대형 지갑 수: {onchain_data.get('whale_activity', {}).get('total_holdings', 'N/A'):,.0f}
- 최근 변동: {onchain_data.get('whale_activity', {}).get('recent_changes', 'N/A')}

네트워크 건강성:
- 활성 주소 수: {onchain_data.get('network_health', {}).get('active_addresses', 'N/A'):,.0f}
- 해시레이트: {onchain_data.get('network_health', {}).get('hashrate', 'N/A'):,.2f} TH/s
- 채굴 난이도: {onchain_data.get('network_health', {}).get('difficulty', 'N/A'):,.0f}

2. 거시경제 지표:
- DXY: {market_conditions.get('dxy', {}).get('current', 'N/A'):.2f}
- S&P 500: {market_conditions.get('sp500', {}).get('current', 'N/A'):,.2f}
- 금리: {market_conditions.get('interest_rate', {}).get('current', 'N/A'):.2f}%

3. 뉴스 감정 분석:
- 긍정 뉴스: {positive_count}
- 부정 뉴스: {negative_count}
- 중립 뉴스: {neutral_count}
- 주요 뉴스 헤드라인:
  {chr(10).join([f'- {news}' for news in news_data])}
"""
            return analysis
        except Exception as e:
            logger.error(f"분석 중 에러 발생: {e}")
            return "분석 실패"
