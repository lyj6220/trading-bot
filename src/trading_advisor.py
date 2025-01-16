import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
from typing import Dict, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingAdvisor:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("Gemini API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def get_trading_advice(self, market_analysis: str) -> Tuple[Dict, str]:
        """시장 분석 데이터를 기반으로 트레이딩 조언 생성"""
        prompt = f"""
당신은 암호화폐 선물 1시간봉 추세추종 트레이딩 전문가입니다. 다소 공격적인 투자성향을 지니고 있습니다. 다음 "시장 분석 리포트"와 "지갑정보" 및 "포지션 정보"를 기반으로 트레이딩 추천을 제공해주세요.

{market_analysis}
[주의사항]
1. 포지션 설정:
   - 현재 포지션이 없을 때: Long, Short, Hold 중 하나를 표시.
   - 현재 포지션 방향이 롱 일 때: Short->Long, Hold, Close 중 하나를 표시.
   - 현재 포지션 방향이 숏 일 때: Long->Short, Hold, Close 중 하나를 표시.

2. 레버리지 및 투자비중 조정:
   - 현재 BTC 가격과 계정 잔고를 확인하여 최소 거래수량(0.001 BTC) 이상이 되도록 조정.

아래 형식을 정확히 지켜서 답변해주세요:

[트레이딩 신호]
- 포지션: (Long, Short, Hold, Close, Long->Short, Short->Long 중 하나만 표시)
- 레버리지: (1-10배 사이 숫자만 표시, Hold 시 0 표시)
- 투자비중: (10-100% 사이 숫자만 표시, Hold 시 0 표시)

[결정 근거]
1. 기술적 분석:
- 가격분석:
- 이동평균선:
- RSI:
- MACD:
- 볼린저밴드:
- 거래량:
- 캔들패턴:

2. 펀더멘탈 분석:
- 주요 지표:
- 시장 상황:

3. 심리 분석:
- 시장 심리:
- 투자 심리:

4. 리스크 관리:
- 리스크 요소:

5. 종합 평가:
- 종합 평가:
"""
        try:
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.error("LLM 응답 없음")
                return {
                    'position': 'HOLD',
                    'leverage': '0',
                    'investment_ratio': '0'
                }, "LLM 응답 실패"
            
            # 응답 파싱
            lines = response.text.split('\n')
            trading_decision = {}
            full_response = response.text
            
            for line in lines:
                line = line.strip()
                if '포지션:' in line:
                    position = line.split(':')[1].strip().upper()  # 대문자로 통일
                    # 허용된 포지션 값 확인
                    valid_positions = ['LONG', 'SHORT', 'HOLD', 'CLOSE', 'LONG->SHORT', 'SHORT->LONG']
                    trading_decision['position'] = position if position in valid_positions else 'HOLD'
                    
                elif '레버리지:' in line:
                    try:
                        leverage = line.split(':')[1].strip().replace('배', '')
                        leverage_value = int(leverage)
                        # 레버리지 범위 확인 (1-10)
                        if 1 <= leverage_value <= 10:
                            trading_decision['leverage'] = str(leverage_value)
                        else:
                            trading_decision['leverage'] = '0'
                    except:
                        trading_decision['leverage'] = '0'
                        
                elif '투자비중:' in line:
                    try:
                        ratio = line.split(':')[1].strip().replace('%', '')
                        ratio_value = float(ratio)
                        # 투자비중 범위 확인 (10-100)
                        if 10 <= ratio_value <= 100:
                            trading_decision['investment_ratio'] = str(ratio_value/100)  # 백분율을 소수로 변환
                        else:
                            trading_decision['investment_ratio'] = '0'
                    except:
                        trading_decision['investment_ratio'] = '0'
            
            # 필수 키가 없는 경우 기본값 설정
            if 'position' not in trading_decision:
                logger.warning("포지션 정보를 찾을 수 없음")
                trading_decision['position'] = 'HOLD'
            if 'leverage' not in trading_decision:
                trading_decision['leverage'] = '0'
            if 'investment_ratio' not in trading_decision:
                trading_decision['investment_ratio'] = '0'
            
            # 포지션 전환 시 투자비중이 0이면 기본값 설정
            if trading_decision['position'] in ['LONG->SHORT', 'SHORT->LONG'] and trading_decision['investment_ratio'] == '0':
                trading_decision['investment_ratio'] = '0.7'  # 기본 70%
                trading_decision['leverage'] = '3'  # 기본 3배
            
            logger.info(f"파싱된 트레이딩 신호: {trading_decision}")
            logger.info(f"LLM 원본 응답:\n{full_response}")
            
            return trading_decision, full_response
            
        except Exception as e:
            logger.error(f"트레이딩 조언 생성 중 에러 발생: {e}")
            return {
                'position': 'HOLD',
                'leverage': '0',
                'investment_ratio': '0'
            }, str(e)

    def format_trading_advice(self, decision: Dict, full_response: str) -> str:
        """트레이딩 조언을 보기 좋게 포맷팅"""
        return f"""
=== 트레이딩 신호 ===
포지션: {decision.get('position', 'N/A')}
레버리지: {decision.get('leverage', 'N/A')}
투자비중: {decision.get('investment_ratio', 'N/A')}

=== 분석 근거 ===
{full_response}
""" 