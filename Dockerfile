# Python 3.10 베이스 이미지 사용
FROM python:3.10

# 필수 패키지 및 TA-Lib 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    libffi-dev \
    libssl-dev \
    && wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# 작업 디렉터리 설정
WORKDIR /app

# 프로젝트 파일 복사
COPY . .

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 시작 명령어
CMD ["python", "src/main.py"]