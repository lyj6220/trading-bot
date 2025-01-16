import os
from dotenv import load_dotenv
from data_collector import MarketDataCollector
from wallet_position_tracker import WalletPositionTracker
from sentiment_analyzer import SentimentAnalyzer
from external_analyzer import ExternalAnalyzer
from fundamental_analyzer import FundamentalAnalyzer

def test_all_data_collection():
    # .env 파일 로드
    load_dotenv()
    
    # API 키 가져오기
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_SECRET_KEY')
    
    print("\n=== 테스트 시작 ===\n")
    
    try:
        # 1. 기술적 분석 데이터
        print("1. 기술적 분석 데이터 수집 중...")
        collector = MarketDataCollector(api_key=api_key, secret_key=api_secret)
        technical_data = collector.prepare_llm_input(symbol="BTCUSDT", timeframe="1h")
        print("\n[기술적 분석 결과]")
        print(technical_data)
        print("\n" + "="*50 + "\n")
        
        # 2. 지갑 및 포지션 정보
        print("2. 지갑 및 포지션 정보 수집 중...")
        wallet_tracker = WalletPositionTracker(api_key=api_key, secret_key=api_secret)
        account_status = wallet_tracker.prepare_account_status(symbol="BTCUSDT")
        print("\n[계정 상태]")
        print(account_status)
        print("\n" + "="*50 + "\n")
        
        # 3. 시장 심리 분석
        print("3. 시장 심리 분석 중...")
        sentiment_analyzer = SentimentAnalyzer()
        sentiment_data = sentiment_analyzer.prepare_sentiment_analysis()
        print("\n[시장 심리 분석]")
        print(sentiment_data)
        print("\n" + "="*50 + "\n")
        
        # 4. 외부 요인 분석
        print("4. 외부 요인 분석 중...")
        external_analyzer = ExternalAnalyzer()
        external_data = external_analyzer.prepare_external_analysis()
        print("\n[외부 요인 분석]")
        print(external_data)
        print("\n" + "="*50 + "\n")
        
        # 5. 펀더멘탈 분석
        print("5. 펀더멘탈 분석 중...")
        fundamental_analyzer = FundamentalAnalyzer()
        fundamental_data = fundamental_analyzer.prepare_fundamental_analysis()
        print("\n[펀더멘탈 분석]")
        print(fundamental_data)
        print("\n" + "="*50 + "\n")
        
        # 6. LLM에 전송될 최종 데이터
        print("6. LLM 입력 데이터 조합")
        final_input = f"""
{account_status}

{technical_data}

{fundamental_data}

{sentiment_data}

{external_data}
"""
        print("\n[LLM 최종 입력 데이터]")
        print(final_input)
        
    except Exception as e:
        print(f"\n에러 발생: {str(e)}")
    
    print("\n=== 테스트 종료 ===")

if __name__ == "__main__":
    test_all_data_collection() 