from fundamental_analyzer import FundamentalAnalyzer
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_analyzer():
    try:
        logger.info("=== 기본적 분석 시작 ===")
        
        # FundamentalAnalyzer 인스턴스 생성
        analyzer = FundamentalAnalyzer()
        
        # 분석 실행
        analysis = analyzer.prepare_fundamental_analysis()
        
        # 결과 출력
        logger.info("\n=== 분석 결과 ===")
        print(analysis)
        
        return True
        
    except Exception as e:
        logger.error(f"분석 중 에러 발생: {e}")
        return False

if __name__ == "__main__":
    success = run_analyzer()
    logger.info(f"\n실행 {'성공' if success else '실패'}") 