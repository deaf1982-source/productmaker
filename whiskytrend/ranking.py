"""집계 결과를 정렬해 연재 글감 후보를 뽑는다."""

from __future__ import annotations

from enum import Enum

from .models import WhiskeyStats


class Period(str, Enum):
    DAY = "d1"
    WEEK = "d7"
    MONTH = "d30"


def rank_by(stats: list[WhiskeyStats], period: Period) -> list[WhiskeyStats]:
    """지정 기간 언급 수 내림차순. 동점이면 30일 누적으로 tie-break."""
    key = period.value
    return sorted(
        stats,
        key=lambda s: (getattr(s, key), s.d30),
        reverse=True,
    )


def rising_stars(stats: list[WhiskeyStats], limit: int = 5) -> list[WhiskeyStats]:
    """급상승 위스키(최근 7일 모멘텀 큰 순). 연재 우선순위 후보.

    momentum 이 None(직전 기록 없음)인 신규 급상승은 뒤로 밀되 포함한다.
    """
    rising = [s for s in stats if s.is_rising]

    def sort_key(s: WhiskeyStats) -> tuple[float, int]:
        m = s.momentum
        return (m if m is not None else 0.0, s.d7)

    rising.sort(key=sort_key, reverse=True)
    return rising[:limit]
