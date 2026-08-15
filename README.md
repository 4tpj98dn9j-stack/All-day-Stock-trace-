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
- `daily_report.py` — 워치리스트 6종목 시세·뉴스와 나스닥 시황(코멘트 포함)을 마크다운으로 정리해 `daily/<YYYY-MM-DD>.md`로 저장
  ```bash
  python daily_report.py
  ```

## 매일 마감 리포트 자동화

`.github/workflows/daily-report.yml`이 평일 21:30 UTC(미국 나스닥 마감 이후)에 `daily_report.py`를 실행해서 `daily/<날짜>.md`를 자동으로 커밋·푸시합니다. GitHub Actions 러너는 이 저장소의 로컬 개발/CI 환경과 달리 Yahoo Finance에 정상적으로 접속되므로, 이 자동화는 실제 데이터를 안정적으로 가져올 수 있습니다.

- 수동 실행: 저장소 **Actions** 탭 → **Daily Report** → **Run workflow**
- 스케줄 변경: `.github/workflows/daily-report.yml`의 `cron` 값 수정

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
