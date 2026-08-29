# whiskytrend — 위스키 언급량 추적기

주류(위스키) 블로그 **연재 글감**을 찾기 위해, 여러 소스에서 위스키별 언급 수를
수집해 **최근 1일 / 7일 / 30일 언급 랭킹**과 **급상승 위스키**를 뽑아준다.

> "세상에 위스키는 많지만, *지금 사람들이 궁금해하는* 위스키는 많지 않다."
> 요즘 많이 언급되는 위스키를 데이터로 찾아 연재 순서를 정하는 것이 목표.

---

## 소스별 현실 (중요)

크롤링 가능 여부와 정확도는 소스마다 크게 다르다. 합법성·안정성 순으로 정리:

| 소스 | 상태 | 기간별 집계 | 비고 |
|------|:---:|:---:|------|
| **네이버 블로그** | ✅ 공식 오픈API | ✅ 가능 | 게시일(postdate) 제공 → 1/7/30일 집계 정확 |
| **네이버 카페글** | ✅ 공식 오픈API | ⚠️ 날짜 미상 | 항목별 날짜 미제공 → '폭 지표'로만 사용 |
| **DCinside 위스키갤** | ⚠️ HTML 파싱 | ✅ 가능 | 공식 API 없음. 목록의 날짜(title 속성) 사용. 개편 시 파서 수정 필요 |
| **쓰레드(Threads)** | ❌ 미지원 | ❌ | 정책상 수집 불가·차단. 이 프로젝트는 다루지 않음 |

- **네이버 오픈API가 핵심 축**이다. 무료(일 25,000회)이고 검색 결과를 정직하게 준다.
- **카페글은 날짜가 없어** 최근 언급 '수'를 정확히 셀 수 없다. 얼마나 폭넓게 회자되는지의
  보조 지표(`날짜미상` 컬럼)로만 쓴다.
- **DCinside는 보조 소스**다. 사이트 구조에 의존하므로 깨질 수 있고, 실패해도
  전체 파이프라인은 계속 돈다.

---

## 빠른 시작

### 1) 설치
```bash
pip install -r requirements.txt
```

### 2) 키 없이 형태부터 보기 (데모)
네이버 키가 아직 없어도 수집→집계→리포트 전체 흐름과 결과 형태를 볼 수 있다.
```bash
python -m whiskytrend --demo
```
합성(가짜) 데이터로 콘솔 랭킹 + `reports/`에 CSV·HTML을 만든다.

### 3) 실제 수집 (네이버 키 연결)
1. https://developers.naver.com/apps/#/register 에서 애플리케이션 등록 → **검색 API** 사용 설정
2. 발급받은 Client ID/Secret 을 `.env` 에 입력 (`.env.example` 복사)
   ```bash
   cp .env.example .env
   # .env 편집: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
   ```
3. 실행
   ```bash
   python -m whiskytrend --sources naver_blog,naver_cafe,dcinside
   ```

키가 없으면 해당 소스는 자동으로 건너뛴다(오류 아님).

---

## 결과물

- **콘솔**: 기간별 TOP N 랭킹 + 급상승 위스키
- `reports/whisky_ranking_YYYY-MM-DD.csv`: 스프레드시트용 원자료
- `reports/whisky_ranking_YYYY-MM-DD.html`: 급상승 카드 + 전체 랭킹 대시보드

주요 지표:
- `d1 / d7 / d30` — 최근 1 / 7 / 30일 언급 수
- `momentum` — 최근 7일 대비 직전 7일 증감률 (연재 우선순위 판단용)
- `rising 🔥` — 급상승 위스키 (momentum ≥ +50% & 7일 3건 이상, 또는 신규 급등)
- `날짜미상` — 카페글처럼 날짜 없는 소스의 언급 수(폭 지표)

---

## 연재할 위스키 추가하기

`config/whiskies.yaml` 에 항목만 추가하면 된다. **표기 흔들림**(한글/영문/오타/애칭)을
`queries` 에 나열하면 하나의 위스키로 묶여 집계된다.

```yaml
  - id: springbank-10
    display: "스프링뱅크 10"
    category: single_malt
    queries: ["스프링뱅크 10", "스프링뱅크 텐", "Springbank 10"]
```

여러 질의어의 검색 결과는 **글 링크 기준으로 중복 제거**되어 이중 집계되지 않는다.

---

## 자주 쓰는 옵션

```bash
python -m whiskytrend --period d1        # 콘솔 요약을 '최근 1일' 기준으로 정렬
python -m whiskytrend --top 20           # 상위 20개 출력
python -m whiskytrend --sources naver_blog   # 특정 소스만
python -m whiskytrend -v                  # 상세 로그(건너뛴 소스/수집 실패 등)
python -m whiskytrend --no-health-guard   # 수집량 급감 감지 시에도 급상승 판정을 보류하지 않음
```

### 수집 건강도 가드 (저품질 수집 자동 감지)

네이버 등 외부 소스의 인덱스는 우리 통제 밖에서 통째로 흔들릴 수 있다. 특정 회차의
수집량이 일제히 급감하면 절대 수치뿐 아니라 급상승(🔥) 판정까지 왜곡된다(분모가
한두 건으로 쪼그라들어 허위 급등이 뜬다).

그래서 매 실행 시 **직전 리포트들(`reports/`)의 30일 언급 합계 중앙값**과 이번 회차를
비교해, 기준의 50% 미만이면 **저품질 수집으로 판정**한다. 이 경우:

- 콘솔·HTML에 경고를 띄우고, **급상승(🔥) 판정을 보류**한다.
- CSV의 `rising` 컬럼도 비운다(허위 급등을 원자료에 남기지 않음). 단, `d1/d7/d30` 등
  수치 자체는 그대로 유지한다.

보류가 싫으면 `--no-health-guard` 로 끌 수 있다. 기준 리포트가 없거나(첫 실행) 너무
적으면 판정하지 않는다.

정기 연재라면 cron 등으로 매일 실행해 날짜별 CSV를 쌓아두면 추세를 볼 수 있다.

---

## 구조

```
whiskytrend/
  models.py        # Mention / WhiskeyStats 등 데이터 모델
  dictionary.py    # config/whiskies.yaml 로딩·정규화
  sources/
    base.py        # Source 추상 인터페이스
    naver.py       # 네이버 블로그/카페 오픈API
    dcinside.py    # DCinside 위스키갤 파서
    demo.py        # 키 없이 쓰는 합성 소스
  collector.py     # 소스 수집 + 중복제거 + 기간 집계
  ranking.py       # 랭킹 / 급상승 산출
  report.py        # CSV / HTML 리포트
  cli.py           # 커맨드라인 진입점
```

## 테스트
```bash
pytest tests/       # 네트워크 불필요 (집계·랭킹·파서 로직 검증)
```

---

## 한계와 다음 단계

- 카페글·쓰레드의 시간별 정밀 집계는 공식 경로로는 불가. 필요하면 별도 검토 필요.
- DCinside 외 커뮤니티(위스키러브 등)는 robots.txt·로그인 정책을 개별 확인 후
  `sources/` 에 새 Source 를 추가하는 방식으로 확장할 수 있다.
- 감성분석(호불호)까지 가면 "많이 언급 + 긍정" 위스키를 골라낼 수 있다.
