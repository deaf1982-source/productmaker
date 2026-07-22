"""소스들을 돌려 위스키별 기간 통계를 만든다."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from .models import Mention, Whiskey, WhiskeyStats
from .sources.base import Source

logger = logging.getLogger(__name__)

_WINDOW_DAYS = 30  # 수집·집계 최대 기간 (모멘텀 비교용 prev7 포함)


def collect(
    whiskies: list[Whiskey],
    sources: list[Source],
    today: date | None = None,
) -> list[WhiskeyStats]:
    """각 위스키에 대해 모든 소스를 수집하고 기간별로 집계한다."""
    today = today or date.today()
    since = today - timedelta(days=_WINDOW_DAYS)

    active = [s for s in sources if s.available]
    skipped = [s.name for s in sources if not s.available]
    if skipped:
        logger.info("건너뛴 소스(인증정보 없음 등): %s", ", ".join(skipped))

    results: list[WhiskeyStats] = []
    for whiskey in whiskies:
        all_mentions: list[Mention] = []
        for source in active:
            try:
                all_mentions.extend(source.fetch(whiskey, since))
            except Exception as exc:  # 한 소스 실패가 전체를 막지 않게
                logger.warning("%s 수집 실패 (%s): %s", source.name, whiskey.id, exc)
        results.append(_aggregate(whiskey, all_mentions, today))
    return results


def _aggregate(
    whiskey: Whiskey, mentions: list[Mention], today: date
) -> WhiskeyStats:
    """언급 목록을 기간별 통계로 접는다. 링크 기준 중복 제거."""
    stats = WhiskeyStats(whiskey=whiskey)

    seen: set[tuple[str, str]] = set()
    for m in mentions:
        if m.dedup_key in seen:
            continue
        seen.add(m.dedup_key)

        if m.date is None:
            stats.undated_total += 1
            stats.by_source[m.source] = stats.by_source.get(m.source, 0) + 1
            continue

        age = (today - m.date).days
        if age < 0:
            age = 0  # 미래 날짜(파싱 오류/타임존)는 오늘로 취급
        if age < 1:
            stats.d1 += 1
        if age < 7:
            stats.d7 += 1
        if 7 <= age < 14:
            stats.prev7 += 1
        if age < 30:
            stats.d30 += 1
            stats.by_source[m.source] = stats.by_source.get(m.source, 0) + 1

    return stats
