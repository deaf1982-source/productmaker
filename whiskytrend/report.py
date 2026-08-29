"""집계 결과를 CSV / HTML 리포트로 출력."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from jinja2 import Template

from .models import WhiskeyStats
from .ranking import Period, rank_by, rising_stars

_CSV_HEADER = [
    "rank",
    "id",
    "display",
    "category",
    "d1",
    "d7",
    "d30",
    "prev7",
    "momentum_pct",
    "rising",
    "undated_total",
    "by_source",
]


def _momentum_pct(stats: WhiskeyStats) -> str:
    m = stats.momentum
    if m is None:
        return "-"
    return f"{m * 100:+.0f}%"


def write_csv(
    stats: list[WhiskeyStats],
    path: str | Path,
    period: Period = Period.WEEK,
    suppress_rising: bool = False,
) -> Path:
    """랭킹 CSV를 쓴다.

    suppress_rising=True 이면 급상승(rising) 컬럼을 비운다. 저품질 수집으로 판정된
    회차에서 허위 급등을 원자료에 남기지 않기 위함(d7/prev7 등 수치 자체는 유지)."""
    path = Path(path)
    ranked = rank_by(stats, period)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADER)
        for i, s in enumerate(ranked, start=1):
            by_source = "; ".join(f"{k}:{v}" for k, v in sorted(s.by_source.items()))
            writer.writerow(
                [
                    i,
                    s.whiskey.id,
                    s.whiskey.display,
                    s.whiskey.category,
                    s.d1,
                    s.d7,
                    s.d30,
                    s.prev7,
                    _momentum_pct(s),
                    "" if suppress_rising else ("Y" if s.is_rising else ""),
                    s.undated_total,
                    by_source,
                ]
            )
    return path


_HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>위스키 언급량 리포트 — {{ generated }}</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
         margin: 0; padding: 24px; line-height: 1.5; }
  h1 { font-size: 1.5rem; margin: 0 0 4px; }
  .meta { color: #888; font-size: .85rem; margin-bottom: 20px; }
  .demo-badge { background: #b8860b; color: #fff; padding: 2px 8px; border-radius: 4px;
                font-size: .75rem; }
  section { margin-bottom: 32px; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { padding: 8px 10px; text-align: right; border-bottom: 1px solid #8883; }
  th:nth-child(2), td:nth-child(2) { text-align: left; }
  th { font-weight: 600; white-space: nowrap; }
  tbody tr:hover { background: #8881; }
  .rank { color: #888; width: 2rem; }
  .rise { color: #2e9e44; font-weight: 600; }
  .rise-neg { color: #c0392b; }
  .rising-card { display: inline-block; border: 1px solid #8884; border-radius: 8px;
                 padding: 10px 14px; margin: 0 10px 10px 0; }
  .rising-card b { font-size: 1.05rem; }
  .src { color: #888; font-size: .8rem; }
  .warn { border: 1px solid #c0392b; background: #c0392b1a; border-radius: 8px;
          padding: 12px 16px; margin-bottom: 20px; }
  .warn b { color: #c0392b; }
</style>
</head>
<body>
  <h1>위스키 언급량 리포트
    {% if demo %}<span class="demo-badge">DEMO — 합성 데이터</span>{% endif %}
  </h1>
  <div class="meta">
    생성: {{ generated }} · 소스: {{ sources }} · 기간 정렬: 최근 7일
  </div>

  {% if health_warning %}
  <div class="warn">
    <b>⚠️ 저품질 수집 경고</b><br>
    {{ health_warning }}
  </div>
  {% endif %}

  <section>
    <h2>🔥 급상승 위스키 (연재 우선 후보)</h2>
    {% if suppress_rising %}
      <p class="src">저품질 수집으로 판정되어 이번 회차의 급상승 판정은 보류했습니다.</p>
    {% elif rising %}
      {% for s in rising %}
        <div class="rising-card">
          <b>{{ s.whiskey.display }}</b><br>
          최근 7일 {{ s.d7 }}건
          {% if s.momentum is not none %}
            <span class="rise">({{ '%+.0f'|format(s.momentum * 100) }}%)</span>
          {% else %}
            <span class="rise">(신규 급상승)</span>
          {% endif %}
          <br><span class="src">직전 7일 {{ s.prev7 }}건</span>
        </div>
      {% endfor %}
    {% else %}
      <p class="src">급상승으로 잡힌 위스키가 없습니다.</p>
    {% endif %}
  </section>

  <section>
    <h2>📊 전체 랭킹 (최근 7일 언급 순)</h2>
    <table>
      <thead>
        <tr>
          <th class="rank">#</th>
          <th>위스키</th>
          <th>분류</th>
          <th>1일</th>
          <th>7일</th>
          <th>30일</th>
          <th>모멘텀</th>
          <th>날짜미상</th>
          <th>소스별(30일)</th>
        </tr>
      </thead>
      <tbody>
        {% for s in ranked %}
        <tr>
          <td class="rank">{{ loop.index }}</td>
          <td>{{ s.whiskey.display }}{% if s.is_rising and not suppress_rising %} 🔥{% endif %}</td>
          <td class="src">{{ s.whiskey.category }}</td>
          <td>{{ s.d1 }}</td>
          <td><b>{{ s.d7 }}</b></td>
          <td>{{ s.d30 }}</td>
          <td class="{{ 'rise' if s.momentum and s.momentum > 0 else ('rise-neg' if s.momentum and s.momentum < 0 else '') }}">
            {% if s.momentum is not none %}{{ '%+.0f'|format(s.momentum * 100) }}%{% else %}-{% endif %}
          </td>
          <td class="src">{{ s.undated_total }}</td>
          <td class="src">{% for k, v in s.by_source.items() %}{{ k }}:{{ v }} {% endfor %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    <p class="src">※ '날짜미상'은 네이버 카페글 검색처럼 게시일을 제공하지 않는 소스의
       언급 수(폭 지표)로, 기간별 집계에는 포함되지 않습니다.</p>
  </section>
</body>
</html>
"""
)


def write_html(
    stats: list[WhiskeyStats],
    path: str | Path,
    sources: list[str],
    demo: bool = False,
    period: Period = Period.WEEK,
    suppress_rising: bool = False,
    health_warning: str | None = None,
) -> Path:
    path = Path(path)
    ranked = rank_by(stats, period)
    html = _HTML_TEMPLATE.render(
        generated=date.today().isoformat(),
        sources=", ".join(sources) or "(없음)",
        demo=demo,
        ranked=ranked,
        rising=[] if suppress_rising else rising_stars(stats),
        suppress_rising=suppress_rising,
        health_warning=health_warning,
    )
    path.write_text(html, encoding="utf-8")
    return path
