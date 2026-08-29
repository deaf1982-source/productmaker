"""수집 건강도 점검 — 직전 회차 대비 수집량이 급감하면 '저품질 수집'으로 판정.

네이버 등 외부 소스의 인덱스/정렬 결과는 우리 통제 밖에서 통째로 흔들릴 수 있다.
특정 회차에서 수집량이 일제히 급감하면 절대 수치는 물론, 모멘텀 기반 급상승(🔥)
판정까지 왜곡된다(분모가 한두 건으로 쪼그라들어 +100% 같은 허위 급등이 뜬다).

이 모듈은 `reports/` 에 쌓인 직전 리포트들의 30일 언급 합계를 기준으로 이번 회차의
수집량을 비교해, 이상 급감을 감지한다. 감지되면 CLI/리포트는 급상승 판정을 보류하고
경고를 노출한다(원자료 수치 자체는 그대로 남긴다).

주의: 데모(합성) 리포트도 같은 파일명 규칙을 쓰므로, 건강도 점검은 실제 수집에서만
호출한다(cli 참고).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import WhiskeyStats

# 이번 수집량이 기준(과거 중앙값)의 이 비율 미만이면 이상 급감으로 본다.
_DEFAULT_LOW_RATIO = 0.5
# 비교에 사용할 직전 리포트 최대 개수 (최신순).
_HISTORY_LIMIT = 5
# 기준 수집량이 이보다 작으면 비교 자체가 무의미하므로 판정하지 않는다(초기 노이즈 방지).
_MIN_REFERENCE = 50

_REPORT_GLOB = "whisky_ranking_*.csv"
_DATE_RE = re.compile(r"whisky_ranking_(\d{4}-\d{2}-\d{2})\.csv$")


def collection_volume(stats: list[WhiskeyStats]) -> int:
    """이번 수집의 총량 지표 = 30일 언급 수 합(가장 안정적인 폭 지표)."""
    return sum(s.d30 for s in stats)


@dataclass
class HealthReport:
    """수집 건강도 판정 결과."""

    current: int                 # 이번 회차 수집량
    reference: Optional[int]     # 과거 기준 수집량(중앙값). 비교 불가 시 None
    anomalous: bool              # 이상 급감 감지 여부
    message: Optional[str]       # 경고 메시지(정상이면 None)

    @property
    def suppress_rising(self) -> bool:
        """급상승(🔥) 판정을 보류해야 하는가."""
        return self.anomalous


def assess(
    stats: list[WhiskeyStats],
    out_dir: str | Path,
    stamp: str,
    low_ratio: float = _DEFAULT_LOW_RATIO,
) -> HealthReport:
    """이번 수집을 직전 리포트들과 비교해 건강도를 판정한다.

    Args:
        stats: 이번 회차 집계 결과.
        out_dir: 리포트가 쌓이는 폴더(과거 CSV를 여기서 읽는다).
        stamp: 이번 회차 날짜(YYYY-MM-DD). 같은 날짜 파일은 기준에서 제외한다.
        low_ratio: 기준 대비 이 비율 미만이면 이상으로 본다.
    """
    current = collection_volume(stats)
    history = _historical_volumes(Path(out_dir), exclude_stamp=stamp)
    if not history:
        return HealthReport(current, None, False, None)

    reference = _median(history)
    if reference < _MIN_REFERENCE:
        # 아직 기준으로 삼을 만큼 데이터가 쌓이지 않았다.
        return HealthReport(current, int(reference), False, None)

    if current < reference * low_ratio:
        pct = (current / reference * 100) if reference else 0
        message = (
            f"수집량 급감 감지: 이번 30일 언급 합계 {current:,}건이 직전 기준(중앙값) "
            f"{int(reference):,}건의 {pct:.0f}% 수준입니다. 외부 소스(네이버 등) 인덱스 "
            "변동일 가능성이 높아, 이번 회차의 절대 수치와 급상승(🔥) 판정은 신뢰하기 "
            "어렵습니다. 하루이틀 뒤 재수집을 권장합니다."
        )
        return HealthReport(current, int(reference), True, message)

    return HealthReport(current, int(reference), False, None)


def _historical_volumes(out_dir: Path, exclude_stamp: str) -> list[int]:
    """out_dir 의 과거 리포트 CSV들에서 30일 언급 합을 최신순으로 읽는다."""
    dated: list[tuple[str, Path]] = []
    for p in out_dir.glob(_REPORT_GLOB):
        m = _DATE_RE.search(p.name)
        if not m or m.group(1) == exclude_stamp:
            continue
        dated.append((m.group(1), p))

    dated.sort(reverse=True)  # 날짜 문자열(YYYY-MM-DD)은 사전식 = 시간순
    volumes: list[int] = []
    for _, p in dated[:_HISTORY_LIMIT]:
        total = _read_d30_sum(p)
        if total is not None:
            volumes.append(total)
    return volumes


def _read_d30_sum(path: Path) -> Optional[int]:
    """리포트 CSV 한 개의 d30 합계. 읽기/파싱 실패 시 None."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "d30" not in reader.fieldnames:
                return None
            total = 0
            found = False
            for row in reader:
                try:
                    total += int(row["d30"])
                    found = True
                except (TypeError, ValueError, KeyError):
                    continue
            return total if found else None
    except OSError:
        return None


def _median(values: list[int]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2
