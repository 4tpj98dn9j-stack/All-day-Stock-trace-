# All-day-Stock-trace-

Yahoo Finance 기반 주식 데이터 도구 모음.

## 설치

```bash
pip install -r requirements.txt
```

## 스크립트

- `fetch_stock_data.py` — 티커/기간을 입력받아 OHLCV(시가/고가/저가/종가/거래량)를 CSV로 저장
  ```bash
  python fetch_stock_data.py --ticker AAPL --period 6mo
  ```
- `daily_change_tracker.py` — 워치리스트(NOW, TSLA, SPCX, QCOM, PL, INFQ) 종목의 전일 대비 등락률을 계산해 CSV 로그에 누적
  ```bash
  python daily_change_tracker.py
  ```
- `app.py` — 위 6개 종목의 현재가/등락률을 카드로 보여주는 반응형 웹 대시보드 (Flask)
  ```bash
  python app.py
  # http://localhost:5000 접속, 새로고침 버튼으로 시세 갱신
  ```

## 옵션 체인 (Tradier, 선택)

나스닥/VIX 카드의 옵션 체인은 Yahoo Finance가 아니라 [Tradier](https://tradier.com) 샌드박스 API에서 가져옵니다 (Yahoo의 비공식 옵션 API가 공유 호스팅 IP에서 자주 rate-limit에 걸려서 대체함).

1. [tradier.com](https://tradier.com)에서 무료 계정 가입
2. 개발자 설정에서 **Sandbox Access Token** 발급 (실거래 계좌/입금 불필요, 15분 지연 데이터)
3. 환경변수로 설정:
   ```bash
   export TRADIER_API_TOKEN=your-sandbox-token
   ```
   Render에 배포한 경우 서비스 → **Environment** 탭에서 `TRADIER_API_TOKEN` 키로 추가

토큰을 설정하지 않으면 옵션 체인 섹션은 에러 없이 "옵션 데이터를 제공하지 않습니다"로 표시됩니다 (그 외 시세/차트/뉴스는 토큰과 무관하게 정상 동작).

## 테스트

```bash
python -m unittest discover -s tests -t .
```

## 배포 (Render, 무료)

이 저장소에는 [Render](https://render.com) Blueprint(`render.yaml`)가 포함되어 있어 GitHub 연동만으로 배포할 수 있습니다.

1. [render.com](https://render.com)에 가입/로그인 (GitHub 계정으로 가능)
2. Dashboard → **New** → **Blueprint** 선택
3. 이 저장소(`4tpj98dn9j-stack/All-day-Stock-trace-`)를 연결하고 브랜치를 `main`으로 지정
4. Render가 `render.yaml`을 자동으로 읽어 `stock-portfolio-dashboard` 서비스를 생성 (무료 플랜, `gunicorn app:app`으로 구동)
5. 배포가 끝나면 `https://stock-portfolio-dashboard-xxxx.onrender.com` 형태의 URL이 발급됩니다

Blueprint 없이 수동으로 만들 경우:
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

> 무료 플랜은 일정 시간 미접속 시 슬립 상태가 되어, 첫 접속 시 로딩이 몇 초 걸릴 수 있습니다.
