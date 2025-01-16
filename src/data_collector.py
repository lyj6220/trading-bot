from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import ccxt
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
        """이동평균선 계산 (talib 제거, pandas 사용)"""
        close_prices = df['close']
        ma_periods = [5, 20, 50, 200]
        mas = {}

        for period in ma_periods:
            sma_series = close_prices.rolling(window=period).mean()
            ema_series = close_prices.ewm(span=period, adjust=False).mean()
            mas[f'ma_{period}'] = float(sma_series.iloc[-1])
            mas[f'ema_{period}'] = float(ema_series.iloc[-1])

        # 골든/데드 크로스 확인
        mas['golden_cross'] = mas['ma_5'] > mas['ma_20'] and mas['ma_20'] > mas['ma_50']
        mas['death_cross'] = mas['ma_5'] < mas['ma_20'] and mas['ma_20'] < mas['ma_50']

        return mas

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
        """RSI 계산 (talib 제거, pandas 사용)"""
        close_prices = df['close']
        delta = close_prices.diff()

        # 상승폭과 하락폭 분리
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # 지수이동평균(EMA)로 평균 상승폭, 평균 하락폭 계산
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi_current = float(rsi_series.iloc[-1])

        # RSI 다이버전스 확인(간단 버전)
        recent_close_diff = np.diff(close_prices.iloc[-5:].values).mean()
        recent_rsi_diff = np.diff(rsi_series.iloc[-5:].values).mean()

        divergence = 'none'
        if recent_close_diff < 0 and recent_rsi_diff > 0:
            divergence = 'bullish'
        elif recent_close_diff > 0 and recent_rsi_diff < 0:
            divergence = 'bearish'

        return {
            'current': rsi_current,
            'divergence': divergence
        }

    def _calculate_macd(self, df: pd.DataFrame) -> Dict[str, float]:
        """MACD 계산 (talib 제거, pandas 사용)"""
        close_prices = df['close']
        ema12 = close_prices.ewm(span=12, adjust=False).mean()
        ema26 = close_prices.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        # 교차 확인
        # 직전 값과 비교가 필요하므로 인덱스 에러를 피하기 위해 조건 처리
        if len(macd_line) < 2:
            cross_above = False
            cross_below = False
        else:
            cross_above = (macd_line.iloc[-1] > signal_line.iloc[-1]) and (macd_line.iloc[-2] <= signal_line.iloc[-2])
            cross_below = (macd_line.iloc[-1] < signal_line.iloc[-1]) and (macd_line.iloc[-2] >= signal_line.iloc[-2])

        return {
            'macd': float(macd_line.iloc[-1]),
            'signal': float(signal_line.iloc[-1]),
            'histogram': float(histogram.iloc[-1]),
            'cross_above': cross_above,
            'cross_below': cross_below
        }

    def _calculate_bollinger(self, df: pd.DataFrame, period: int = 20) -> Dict[str, float]:
        """볼린저 밴드 계산 (talib 제거, pandas 사용)"""
        close_prices = df['close']
        rolling_mean = close_prices.rolling(window=period).mean()
        rolling_std = close_prices.rolling(window=period).std()

        upper = rolling_mean + 2 * rolling_std
        middle = rolling_mean
        lower = rolling_mean - 2 * rolling_std

        current_price = close_prices.iloc[-1]
        upper_val = float(upper.iloc[-1])
        middle_val = float(middle.iloc[-1])
        lower_val = float(lower.iloc[-1])

        # 밴드폭, 현재 가격 위치
        if middle_val != 0:
            bandwidth = (upper_val - lower_val) / middle_val
        else:
            bandwidth = 0.0

        if (upper_val - lower_val) != 0:
            position = (current_price - lower_val) / (upper_val - lower_val)
        else:
            position = 0.0

        return {
            'upper': upper_val,
            'middle': middle_val,
            'lower': lower_val,
            'bandwidth': bandwidth,
            'position': position
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR 계산 (talib 제거, pandas 사용, 기본적으로 Wilder’s Moving Average 가정)"""
        high = df['high']
        low = df['low']
        close = df['close']

        # TR 계산
        df_atr = df.copy()
        df_atr['prev_close'] = df_atr['close'].shift(1)
        df_atr['tr1'] = abs(df_atr['high'] - df_atr['low'])
        df_atr['tr2'] = abs(df_atr['high'] - df_atr['prev_close'])
        df_atr['tr3'] = abs(df_atr['low'] - df_atr['prev_close'])
        df_atr['TR'] = df_atr[['tr1', 'tr2', 'tr3']].max(axis=1)

        # ATR = TR의 지수이동평균(기본적으로 Welles Wilder는 특수 계산, 여기서는 ewm으로 대체)
        df_atr['ATR'] = df_atr['TR'].ewm(span=period, adjust=False).mean()

        return float(df_atr['ATR'].iloc[-1])

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
        """ADX 계산 (talib 제거, pandas 사용, 기본 로직 구현)"""
        # ADX 는 +DI, -DI, DX 를 거쳐 계산됨
        df_adx = df.copy()
        df_adx['prev_close'] = df_adx['close'].shift(1)
        df_adx['prev_high'] = df_adx['high'].shift(1)
        df_adx['prev_low'] = df_adx['low'].shift(1)

        # DM+
        df_adx['+DM'] = np.where(
            (df_adx['high'] - df_adx['prev_high']) > (df_adx['prev_low'] - df_adx['low']),
            np.maximum(df_adx['high'] - df_adx['prev_high'], 0),
            0
        )
        # DM-
        df_adx['-DM'] = np.where(
            (df_adx['prev_low'] - df_adx['low']) > (df_adx['high'] - df_adx['prev_high']),
            np.maximum(df_adx['prev_low'] - df_adx['low'], 0),
            0
        )
        # TR
        df_adx['TR1'] = df_adx['high'] - df_adx['low']
        df_adx['TR2'] = abs(df_adx['high'] - df_adx['prev_close'])
        df_adx['TR3'] = abs(df_adx['low'] - df_adx['prev_close'])
        df_adx['TR'] = df_adx[['TR1', 'TR2', 'TR3']].max(axis=1)

        # smoothed TR, +DM, -DM (지수이동평균 사용)
        df_adx['TR_ewm'] = df_adx['TR'].ewm(span=period, adjust=False).mean()
        df_adx['+DM_ewm'] = df_adx['+DM'].ewm(span=period, adjust=False).mean()
        df_adx['-DM_ewm'] = df_adx['-DM'].ewm(span=period, adjust=False).mean()

        df_adx['+DI'] = 100 * (df_adx['+DM_ewm'] / df_adx['TR_ewm'])
        df_adx['-DI'] = 100 * (df_adx['-DM_ewm'] / df_adx['TR_ewm'])

        df_adx['DX'] = 100 * abs(df_adx['+DI'] - df_adx['-DI']) / (df_adx['+DI'] + df_adx['-DI'])
        df_adx['ADX'] = df_adx['DX'].ewm(span=period, adjust=False).mean()

        adx_value = float(df_adx['ADX'].iloc[-1])

        if adx_value > 25:
            trend_strength = 'strong'
        elif adx_value < 20:
            trend_strength = 'weak'
        else:
            trend_strength = 'moderate'

        return {
            'adx': adx_value,
            'trend_strength': trend_strength
        }

    def _analyze_volume_trend(self, df: pd.DataFrame) -> Dict[str, float]:
        """거래량 트렌드 분석 (talib 제거, pandas 사용)"""
        volume = df['volume']
        vol_sma = volume.rolling(window=20).mean()
        current_vol = float(volume.iloc[-1])
        vol_sma_current = float(vol_sma.iloc[-1])

        return {
            'current_volume': current_vol,
            'volume_sma': vol_sma_current,
            'volume_trend': 'increasing' if current_vol > vol_sma_current else 'decreasing'
        }

    def _calculate_obv(self, df: pd.DataFrame) -> Dict[str, float]:
        """OBV(On Balance Volume) 계산 (talib 제거, pandas 사용)"""
        # OBV는 close가 전 봉보다 상승하면 거래량을 더하고, 하락하면 거래량을 빼고, 동일하면 변화 없음
        obv_series = [0]
        close = df['close'].values
        volume = df['volume'].values

        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv_series.append(obv_series[-1] + volume[i])
            elif close[i] < close[i - 1]:
                obv_series.append(obv_series[-1] - volume[i])
            else:
                obv_series.append(obv_series[-1])

        df_obv = pd.Series(obv_series, index=df.index)
        obv_sma = df_obv.rolling(window=20).mean()

        current_obv = float(df_obv.iloc[-1])
        sma_obv = float(obv_sma.iloc[-1]) if not np.isnan(obv_sma.iloc[-1]) else 0.0

        trend = 'bullish' if current_obv > sma_obv else 'bearish'

        return {
            'current': current_obv,
            'sma': sma_obv,
            'trend': trend
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

2. 기술적 지표:
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

3. 거래량 분석:
- 현재 거래량: {analysis_result['volume']['volume_trend']['current_volume']:.2f}
- 20일 평균: {analysis_result['volume']['volume_trend']['volume_sma']:.2f}
- 트렌드: {analysis_result['volume']['volume_trend']['volume_trend']}
- OBV 트렌드: {analysis_result['volume']['obv']['trend']}

4. 파생상품 데이터:
- 오픈 인터레스트: {analysis_result['derivatives']['open_interest']:.2f}
- 펀딩비: {analysis_result['derivatives']['funding_rate']:.4%}
- OI 변화율: {analysis_result['derivatives']['oi_change']:.2f}%
"""
        return template

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
            'price_history': price_history,
            'indicators': self.get_technical_indicators(df),
            'volume': self.get_volume_analysis(df),
            'derivatives': self.get_derivatives_data(symbol)
        }

        return self._format_for_llm(analysis_result)
