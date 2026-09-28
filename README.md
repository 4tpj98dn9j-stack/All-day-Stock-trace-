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
- `daily_report.py` — 워치리스트 6종목 시세·뉴스와 미국 주식시장 시황(코멘트 포함)을 마크다운으로 정리해 `daily/<YYYY-MM-DD>.md`로 저장
  ```bash
  python daily_report.py
  ```
- `fetch_macro_data.py` — FRED(세인트루이스 연은) API에서 거시경제 지표를 가져와 `data/macro.json`으로 저장. 나스닥종합/VIX는 대시보드의 "미국 주식시장 시황" 섹션이 이미 당일 Yahoo Finance 데이터로 보여주므로 여기서는 제외
  - 금리/커브: 10년/2년/3개월물 국채금리(DGS10, DGS2, DGS3MO), 장단기 스프레드(T10Y2Y, T10Y3M), 10년 실질금리(DFII10), SOFR, 연방기금 실효금리(DFF), 연방기금금리(FEDFUNDS), CPI 전년동월비(CPIAUCSL)
  - 유동성: Fed 대차대조표 총자산(WALCL), 역레포 잔고(RRPONTSYD), 은행 지준 잔고(WRESBAL), TGA 잔고(WTREGEN), 통화량 M2(M2SL), SRF 레포 잔액(RPONTSYD)
  - 신용/리스크: 하이일드 스프레드(BAMLH0A0HYM2), 회사채-국채 스프레드(BAA10Y), 시카고연은 금융여건지수(NFCI), 세인트루이스연은 금융스트레스지수(STLFSI4), 등급 격차(CCC−BB: BAMLH0A3HYC − BAMLH0A1HYBB), MOVE 지수(채권 변동성, Yahoo `^MOVE`)
  - 주식-신용 괴리: S&P500 52주 고점 대비(SP500), HY 스프레드 20일 변화(BAMLH0A0HYM2)
  - 인플레이션 기대: 5년/10년 기대인플레이션(T5YIE, T10YIE), 5y5y forward(T5YIFR)
  - 달러: 무역가중 달러지수(DTWEXBGS)
  - 실물경제: 비농업고용 전월비(PAYEMS), 실업률(UNRATE), 신규 실업수당 청구(ICSA), 산업생산 전년동월비(INDPRO), 미시간대 소비자심리지수(UMCSENT)
  ```bash
  export FRED_API_KEY=...   # 또는 .env 파일에 FRED_API_KEY=... 저장
  python fetch_macro_data.py
  ```
- `fetch_scoos_data.py` — 연준의 SCOOS(딜러 자금조달 여건 설문) 분기 결과를 가져와 `data/scoos.json`으로 저장
  ```bash
  export FRED_API_KEY=...
  python fetch_scoos_data.py
  ```

## 매일 마감 리포트 자동화

`.github/workflows/daily-report.yml`이 평일 21:30 UTC(미국 나스닥 마감 이후)에 `daily_report.py`를 실행해서 `daily/<날짜>.md`를 자동으로 커밋·푸시합니다. GitHub Actions 러너는 이 저장소의 로컬 개발/CI 환경과 달리 Yahoo Finance에 정상적으로 접속되므로, 이 자동화는 실제 데이터를 안정적으로 가져올 수 있습니다.

- 수동 실행: 저장소 **Actions** 탭 → **Daily Report** → **Run workflow**
- 스케줄 변경: `.github/workflows/daily-report.yml`의 `cron` 값 수정

## 매크로 지표 자동화 (FRED)

`.github/workflows/macro-data.yml`이 매일 22:00 UTC에 `fetch_macro_data.py`를 실행해서 `data/macro.json`을 자동으로 커밋·푸시합니다. 대시보드는 이 파일만 읽으므로, 배포된 Flask 앱 자체에는 FRED API 키가 필요 없습니다.

설정 방법:

1. [fred.stlouisfed.org](https://fred.stlouisfed.org)에서 무료 API 키 발급
2. 저장소 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
3. Name: `FRED_API_KEY`, Value: 발급받은 키 입력 후 저장
4. (로컬 테스트용) 저장소 루트에 `.env` 파일을 만들고 `FRED_API_KEY=발급받은키`를 추가 — `.env`는 `.gitignore`에 포함되어 커밋되지 않습니다

- 수동 실행: 저장소 **Actions** 탭 → **Macro Data** → **Run workflow** (Secret 등록 후에만 성공)
- 시리즈 추가/변경: `fetch_macro_data.py`의 `MACRO_SERIES` 목록 수정 (FRED 시리즈 ID는 [fred.stlouisfed.org](https://fred.stlouisfed.org)에서 검색)
- 참고: FRED에는 "SRF(상시 레포 기구)" 사용량만 따로 집계한 시리즈가 없어서, `RPONTSYD`(Fed의 오버나이트 레포 매입 총액)를 근사치로 사용합니다. 2021년 SRF 도입 이후 이 수치는 사실상 SRF 사용량과 거의 일치합니다.
- 일부 지표는 FRED 원본 시리즈가 아니라 계산해서 만듭니다: `spread`(두 시리즈의 차이 — 등급 격차), `drawdown`(직전 N개 관측치 중 고점 대비 %  — S&P500 52주 고점 대비), `change_over`(N기간 전 대비 변화 — HY 스프레드 20일 변화). 과거 구간 전체에 대해 같은 계산을 반복해서 차트도 함께 만듭니다.
- 참고: "에너지 제외 하이일드 스프레드(ex-energy HY OAS)"는 넣지 못했습니다. FRED는 하이일드를 **신용등급별**(BB/B/CCC)로만 쪼개서 제공하고 **섹터별** 시리즈는 없어서, 직접 계산하려면 지수 편입 채권별 섹터 분류와 시가총액 가중치가 필요한데 무료 소스로는 구할 수 없습니다.
- 모든 매크로 지표는 클릭하면 시계열 차트가 뜹니다 (`MACRO_SERIES`의 `history_count`로 제어) — 일간 시리즈는 최근 2년(500개), 주간 시리즈는 최근 5년(260개), 월간 시리즈는 최근 5년(60개)치를 보여줍니다. CPI/PAYEMS/INDPRO처럼 전년비·전월비로 계산되는 시리즈는 과거 구간 전체에 대해 같은 방식으로 재계산해서 차트를 만듭니다.

## SCOOS 자동화 (딜러 자금조달 여건)

`.github/workflows/scoos-data.yml`이 매주 월요일 22:30 UTC에 `fetch_scoos_data.py`를 실행해서 `data/scoos.json`을 커밋·푸시합니다. SCOOS는 분기 설문이라 값 자체는 분기에 한 번만 바뀌지만, 발표 시점이 분기말 기준 몇 주 뒤로 유동적이라 주 1회 확인합니다. FRED를 쓰므로 `FRED_API_KEY` 시크릿을 그대로 재사용합니다.

SCOOS(Senior Credit Officer Opinion Survey on Dealer Financing Terms)는 헤지펀드·REIT 등에 자금을 대주는 대형 딜러들을 대상으로 한 연준의 분기 설문입니다. 스프레드·MOVE 같은 시장 가격 지표가 간접적으로만 보여주는 "신용시장 뒷단의 자금 사정"을 딜러들이 직접 답한 자료라, 매크로 지표와 성격이 다릅니다.

대시보드는 두 그룹으로 보여줍니다:

- **기초시장 유동성·기능 개선 응답** — 투자등급/하이일드 회사채, CMBS, Agency/Non-agency RMBS, 소비자 ABS
- **자금조달 수요 증가 응답** — 투자등급/하이일드 회사채, 주식, CMBS, Agency/Non-agency RMBS, 소비자 ABS

값은 모두 **순비율(net percentage)** 입니다 — "늘었다(좋아졌다)"고 답한 딜러 비율에서 "줄었다(나빠졌다)"고 답한 비율을 뺀 값이라, 수준이 아니라 방향을 나타냅니다.

- 연준은 이 설문을 [federalreserve.gov/data/scoos.htm](https://www.federalreserve.gov/data/scoos.htm)에 HTML/PDF exhibit으로 공개하는데, **같은 exhibit 차트의 순비율 시리즈가 FRED 릴리스 571에 `EXHE<exhibit>C<chart>Q<question>NP` 형태로 그대로 올라와 있습니다.** 그래서 문항별 응답자 수(`SFQ*NR`)로 순비율을 직접 재계산하지 않고 이 시리즈를 그대로 가져옵니다 — 연준이 인쇄한 숫자와 동일합니다.
- 패널 구성은 FRED의 차트 번호(`C1`~`C6`)를 그대로 따릅니다. 연준 Exhibit 3의 원본 배치와 같습니다.
- 한 패널당 시리즈는 최대 3개입니다. 색각 이상에서도 구분되는 범주형 색상이 3개까지만 검증되기 때문이고, 색 외에 선 모양(실선·긴 점선·짧은 점선)으로도 구분합니다.
- 차트를 누르거나 마우스를 올리면 해당 분기의 각 시리즈 값이 표시됩니다. 데이터는 2011년 4분기부터 전 구간을 담고 있습니다.

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
