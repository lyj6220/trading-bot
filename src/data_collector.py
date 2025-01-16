from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import ccxt
import talib
from datetime import datetime, timedelta
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataCollector:
    def __init__(self, api_key: str, secret_key: str):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear',
                'adjustForTimeDifference': True,
                'recvWindow': 10000
            }
        })
        
    def _get_historical_data(self, symbol: str, timeframe: str = '1h', limit: int = 500) -> pd.DataFrame:
        """과거 데이터 조회"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"Historical data fetch error: {e}")
            raise

    def _calculate_moving_averages(self, df: pd.DataFrame) -> Dict[str, float]:
        """이동평균선 계산"""
        close_prices = df['close'].values
        ma_periods = [5, 20, 50, 200]
        mas = {}
        
        for period in ma_periods:
            sma = talib.SMA(close_prices, timeperiod=period)
            ema = talib.EMA(close_prices, timeperiod=period)
            mas[f'ma_{period}'] = float(sma[-1])
            mas[f'ema_{period}'] = float(ema[-1])
        
        # 골든/데드 크로스 확인
        mas['golden_cross'] = mas['ma_5'] > mas['ma_20'] and mas['ma_20'] > mas['ma_50']
        mas['death_cross'] = mas['ma_5'] < mas['ma_20'] and mas['ma_20'] < mas['ma_50']
        
        return mas

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
        """RSI 계산"""
        close_prices = df['close'].values
        rsi = talib.RSI(close_prices, timeperiod=period)
        rsi_current = float(rsi[-1])
        
        # RSI 다이버전스 확인
        price_trend = np.diff(close_prices[-5:]).mean()
        rsi_trend = np.diff(rsi[-5:]).mean()
        
        return {
            'current': rsi_current,
            'divergence': 'bullish' if price_trend < 0 and rsi_trend > 0 else 'bearish' if price_trend > 0 and rsi_trend < 0 else 'none'
        }

    def _calculate_macd(self, df: pd.DataFrame) -> Dict[str, float]:
        """MACD 계산"""
        close_prices = df['close'].values
        macd, signal, hist = talib.MACD(close_prices)
        
        return {
            'macd': float(macd[-1]),
            'signal': float(signal[-1]),
            'histogram': float(hist[-1]),
            'cross_above': macd[-1] > signal[-1] and macd[-2] <= signal[-2],
            'cross_below': macd[-1] < signal[-1] and macd[-2] >= signal[-2]
        }

    def _calculate_bollinger(self, df: pd.DataFrame, period: int = 20) -> Dict[str, float]:
        """볼린저 밴드 계산"""
        close_prices = df['close'].values
        upper, middle, lower = talib.BBANDS(close_prices, timeperiod=period)
        current_price = close_prices[-1]
        
        return {
            'upper': float(upper[-1]),
            'middle': float(middle[-1]),
            'lower': float(lower[-1]),
            'bandwidth': float((upper[-1] - lower[-1]) / middle[-1]),
            'position': float((current_price - lower[-1]) / (upper[-1] - lower[-1]))
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR 계산"""
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        return float(talib.ATR(high, low, close, timeperiod=period)[-1])

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
        """ADX 계산"""
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        adx = talib.ADX(high, low, close, timeperiod=period)
        adx_value = float(adx[-1])
        
        return {
            'adx': adx_value,
            'trend_strength': 'strong' if adx_value > 25 else 'weak' if adx_value < 20 else 'moderate'
        }

    def _analyze_volume_trend(self, df: pd.DataFrame) -> Dict[str, float]:
        """거래량 트렌드 분석"""
        volume = df['volume'].values
        vol_sma = talib.SMA(volume, timeperiod=20)
        current_vol = float(volume[-1])
        vol_sma_current = float(vol_sma[-1])
        
        return {
            'current_volume': current_vol,
            'volume_sma': vol_sma_current,
            'volume_trend': 'increasing' if current_vol > vol_sma_current else 'decreasing'
        }

    def _calculate_obv(self, df: pd.DataFrame) -> Dict[str, float]:
        """OBV(On Balance Volume) 계산"""
        close = df['close'].values
        volume = df['volume'].values
        obv = talib.OBV(close, volume)
        obv_sma = talib.SMA(obv, timeperiod=20)
        
        return {
            'current': float(obv[-1]),
            'sma': float(obv_sma[-1]),
            'trend': 'bullish' if obv[-1] > obv_sma[-1] else 'bearish'
        }

    def _get_open_interest(self, symbol: str) -> float:
        """오픈 인터레스트 조회"""
        try:
            # 바이비트의 선물 오픈 인터레스트 데이터 조회
            oi_data = self.exchange.fetch_open_interest(symbol)
            if isinstance(oi_data, dict) and 'info' in oi_data:
                return float(oi_data['info'].get('openInterest', 0))
            return 0.0
        except Exception as e:
            logger.error(f"Open interest fetch error: {str(e)}")
            return 0.0

    def _get_funding_rate(self, symbol: str) -> float:
        """펀딩비 조회"""
        try:
            funding_data = self.exchange.fetch_funding_rate(symbol)
            if isinstance(funding_data, dict) and 'info' in funding_data:
                return float(funding_data['info'].get('fundingRate', 0))
            return 0.0
        except Exception as e:
            logger.error(f"Funding rate fetch error: {str(e)}")
            return 0.0

    def _get_oi_change(self, symbol: str) -> float:
        """오픈 인터레스트 변화율 계산"""
        try:
            # 현재 OI 조회
            current_oi = self._get_open_interest(symbol)
            
            # 24시간 전 데이터 조회
            yesterday = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
            history = self.exchange.fetch_open_interest_history(symbol, since=yesterday, limit=1)
            
            if history and len(history) > 0 and 'info' in history[0]:
                yesterday_oi = float(history[0]['info'].get('openInterest', 0))
                if yesterday_oi > 0:
                    return ((current_oi - yesterday_oi) / yesterday_oi) * 100
            return 0.0
        except Exception as e:
            logger.error(f"OI change calculation error: {str(e)}")
            return 0.0

    def _format_for_llm(self, analysis_result: Dict) -> str:
        """분석 결과를 보기 좋게 포맷팅"""
        def format_patterns(patterns_list):
            return ', '.join(f"{p['pattern']}({p['confidence']:.1f}%)" for p in patterns_list)

        template = f"""
시장 분석 리포트 - {analysis_result['symbol']}
시간: {analysis_result['timestamp']}

1. 최근 50봉 가격정보:
{json.dumps(analysis_result['price_history'], indent=2, ensure_ascii=False)}

2. 캔들스틱 패턴:
상승 반전: {format_patterns(analysis_result['patterns']['reversal_bullish'])}
하락 반전: {format_patterns(analysis_result['patterns']['reversal_bearish'])}
지속 패턴: {format_patterns(analysis_result['patterns']['continuation'])}

3. 기술적 지표:
이동평균선:
- MA5: {analysis_result['indicators']['ma']['ma_5']:.2f}
- MA20: {analysis_result['indicators']['ma']['ma_20']:.2f}
- MA50: {analysis_result['indicators']['ma']['ma_50']:.2f}
- MA200: {analysis_result['indicators']['ma']['ma_200']:.2f}
- 골든크로스: {'예' if analysis_result['indicators']['ma']['golden_cross'] else '아니오'}
- 데드크로스: {'예' if analysis_result['indicators']['ma']['death_cross'] else '아니오'}

RSI: {analysis_result['indicators']['rsi']['current']:.2f}
MACD: 
- 값: {analysis_result['indicators']['macd']['macd']:.2f}
- 시그널: {analysis_result['indicators']['macd']['signal']:.2f}
- 히스토그램: {analysis_result['indicators']['macd']['histogram']:.2f}

볼린저 밴드:
- 상단: {analysis_result['indicators']['bollinger']['upper']:.2f}
- 중간: {analysis_result['indicators']['bollinger']['middle']:.2f}
- 하단: {analysis_result['indicators']['bollinger']['lower']:.2f}
- 위치: {analysis_result['indicators']['bollinger']['position']:.2%}

ATR: {analysis_result['indicators']['atr']:.2f}
ADX: {analysis_result['indicators']['adx']['adx']:.2f} ({analysis_result['indicators']['adx']['trend_strength']})

4. 거래량 분석:
- 현재 거래량: {analysis_result['volume']['volume_trend']['current_volume']:.2f}
- 20일 평균: {analysis_result['volume']['volume_trend']['volume_sma']:.2f}
- 트렌드: {analysis_result['volume']['volume_trend']['volume_trend']}
- OBV 트렌드: {analysis_result['volume']['obv']['trend']}

5. 파생상품 데이터:
- 오픈 인터레스트: {analysis_result['derivatives']['open_interest']:.2f}
- 펀딩비: {analysis_result['derivatives']['funding_rate']:.4%}
- OI 변화율: {analysis_result['derivatives']['oi_change']:.2f}%
"""
        return template

    def get_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, List[dict]]:
        """캔들스틱 패턴 감지 및 신뢰도 계산"""
        patterns = {
            'reversal_bullish': [],
            'reversal_bearish': [],
            'continuation': []
        }
        
        open_data = df['open'].values
        high_data = df['high'].values
        low_data = df['low'].values
        close_data = df['close'].values
        
        def calculate_confidence(pattern_value: int, price_movement: float, volume_confirm: bool) -> float:
            """패턴 신뢰도 계산"""
            # 패턴 강도를 0-100 스케일로 변환
            pattern_strength = abs(pattern_value)
            
            # 기본 신뢰도 (60%)
            base_confidence = (pattern_strength / 100) * 60
            
            # 가격 움직임 가중치 (20%)
            price_weight = min(abs(price_movement) * 2, 20)
            
            # 거래량 확인 가중치 (20%)
            volume_weight = 20 if volume_confirm else 0
            
            return min(round(base_confidence + price_weight + volume_weight, 1), 100)

        # 상승 반전 패턴
        pattern_funcs_bullish = {
            'hammer': (talib.CDLHAMMER, 0.5),
            'morning_star': (talib.CDLMORNINGSTAR, 0.8),
            'piercing_line': (talib.CDLPIERCING, 0.6),
            'bullish_engulfing': (talib.CDLENGULFING, 0.7),
            'three_white_soldiers': (talib.CDL3WHITESOLDIERS, 0.9)
        }
        
        # 최근 3개 봉의 거래량 평균보다 현재 거래량이 큰지 확인
        volume_data = df['volume'].values
        recent_volume_avg = np.mean(volume_data[-4:-1])
        volume_confirm = volume_data[-1] > recent_volume_avg
        
        # 가격 변동폭 계산
        recent_price_change = (close_data[-1] - open_data[-1]) / open_data[-1] * 100
        
        # 상승 반전 패턴 감지
        for pattern_name, (pattern_func, weight) in pattern_funcs_bullish.items():
            result = pattern_func(open_data, high_data, low_data, close_data)
            # 모든 결과를 포함하되, 신뢰도 계산
            confidence = calculate_confidence(
                result[-1] if result[-1] != 0 else 1,  # 패턴이 없으면 최소값
                recent_price_change,
                volume_confirm
            ) * weight
            
            patterns['reversal_bullish'].append({
                'pattern': pattern_name,
                'confidence': confidence if result[-1] != 0 else 0  # 패턴이 없으면 0%
            })
        
        # 하락 반전 패턴
        pattern_funcs_bearish = {
            'shooting_star': (talib.CDLSHOOTINGSTAR, 0.5),
            'evening_star': (talib.CDLEVENINGSTAR, 0.8),
            'bearish_engulfing': (talib.CDLENGULFING, 0.7),
            'three_black_crows': (talib.CDL3BLACKCROWS, 0.9)
        }
        
        for pattern_name, (pattern_func, weight) in pattern_funcs_bearish.items():
            result = pattern_func(open_data, high_data, low_data, close_data)
            confidence = calculate_confidence(
                result[-1] if result[-1] != 0 else 1,
                recent_price_change,
                volume_confirm
            ) * weight
            
            patterns['reversal_bearish'].append({
                'pattern': pattern_name,
                'confidence': confidence if result[-1] != 0 else 0
            })
        
        # 지속 패턴
        pattern_funcs_continuation = {
            'doji': (talib.CDLDOJI, 0.4),
            'spinning_top': (talib.CDLSPINNINGTOP, 0.3),
            'marubozu': (talib.CDLMARUBOZU, 0.6)
        }
        
        for pattern_name, (pattern_func, weight) in pattern_funcs_continuation.items():
            result = pattern_func(open_data, high_data, low_data, close_data)
            confidence = calculate_confidence(
                result[-1] if result[-1] != 0 else 1,
                recent_price_change,
                volume_confirm
            ) * weight
            
            patterns['continuation'].append({
                'pattern': pattern_name,
                'confidence': confidence if result[-1] != 0 else 0
            })
        
        # 각 카테고리별로 신뢰도 순으로 정렬
        for category in patterns:
            patterns[category] = sorted(patterns[category], 
                                      key=lambda x: x['confidence'], 
                                      reverse=True)
        
        return patterns
    
    def get_technical_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """기술적 지표 계산"""
        indicators = {
            'ma': self._calculate_moving_averages(df),
            'rsi': self._calculate_rsi(df),
            'macd': self._calculate_macd(df),
            'bollinger': self._calculate_bollinger(df),
            'atr': self._calculate_atr(df),
            'adx': self._calculate_adx(df)
        }
        return indicators
    
    def get_volume_analysis(self, df: pd.DataFrame) -> Dict[str, dict]:
        """거래량 분석"""
        volume_data = {
            'volume_trend': self._analyze_volume_trend(df),
            'obv': self._calculate_obv(df)
        }
        return volume_data
    
    def get_derivatives_data(self, symbol: str) -> Dict[str, float]:
        """파생상품 데이터 수집"""
        derivatives = {
            'open_interest': self._get_open_interest(symbol),
            'funding_rate': self._get_funding_rate(symbol),
            'oi_change': self._get_oi_change(symbol)
        }
        return derivatives

    def prepare_llm_input(self, symbol: str, timeframe: str = '1h') -> str:
        """LLM 입력용 데이터 준비"""
        df = self._get_historical_data(symbol, timeframe=timeframe)
        
        # 최근 50봉 가격정보를 JSON 형식으로 변환
        recent_candles = df.tail(50).copy()
        recent_candles['timestamp'] = recent_candles['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        price_history = recent_candles.to_dict('records')
        
        analysis_result = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'timeframe': timeframe,
            'price_history': price_history,  # 가격 이력 추가
            'patterns': self.get_candlestick_patterns(df),
            'indicators': self.get_technical_indicators(df),
            'volume': self.get_volume_analysis(df),
            'derivatives': self.get_derivatives_data(symbol)
        }
        
        return self._format_for_llm(analysis_result) 