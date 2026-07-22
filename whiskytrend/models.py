"""공용 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class Whiskey:
    """사전에 정의된 위스키 한 종."""

    id: str
    display: str
    category: str
    queries: list[str]


@dataclass(frozen=True)
class Mention:
    """한 건의 언급(글) 하나.

    date 가 None 이면 게시 날짜를 알 수 없는 소스(예: 네이버 카페글 검색은
    항목별 날짜를 주지 않음)를 의미하며, 기간별 집계에서는 제외되고
    '기간 미상 총계'로만 쓰인다.
    """

    source: str          # "naver_blog", "naver_cafe", "dcinside" ...
    link: str            # 중복 제거 키
    title: str
    date: Optional[date] = None

    @property
    def dedup_key(self) -> tuple[str, str]:
        return (self.source, self.link)


@dataclass
class WhiskeyStats:
    """한 위스키의 소스 통합 집계 결과."""

    whiskey: Whiskey

    # 기간별 언급 수 (날짜가 있는 언급만 집계)
    d1: int = 0          # 최근 1일
    d7: int = 0          # 최근 7일
    d30: int = 0         # 최근 30일
    prev7: int = 0       # 8~14일 전 (모멘텀 비교용)

    # 날짜 미상 언급의 소스별 총계 (예: 카페글 검색 total)
    undated_total: int = 0

    # 소스별 30일 언급 수 (기여도 확인용)
    by_source: dict[str, int] = field(default_factory=dict)

    @property
    def momentum(self) -> Optional[float]:
        """최근 7일 대비 직전 7일 증감률. 직전 7일이 0이면 None."""
        if self.prev7 == 0:
            return None
        return (self.d7 - self.prev7) / self.prev7

    @property
    def is_rising(self) -> bool:
        """급상승 여부: 최근 7일이 직전 7일보다 유의미하게 늘었는가."""
        m = self.momentum
        if m is None:
            return self.d7 >= 3  # 이전 기록이 없는데 갑자기 언급되면 신규 급상승
        return m >= 0.5 and self.d7 >= 3


def parse_yyyymmdd(value: str) -> Optional[date]:
    """'20260722' 형태 문자열을 date 로 변환. 실패 시 None."""
    value = (value or "").strip()
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None
