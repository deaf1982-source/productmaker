"""집계·랭킹 로직 테스트 (네트워크 불필요)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whiskytrend.collector import _aggregate  # noqa: E402
from whiskytrend.dictionary import load_whiskies  # noqa: E402
from whiskytrend.models import Mention, Whiskey, WhiskeyStats, parse_yyyymmdd  # noqa: E402
from whiskytrend.ranking import Period, rank_by, rising_stars  # noqa: E402
from whiskytrend.sources.dcinside import _parse_dc_date  # noqa: E402

TODAY = date(2026, 7, 22)
W = Whiskey(id="test", display="테스트", category="etc", queries=["테스트"])


def _m(days_ago: int, link: str, source: str = "naver_blog") -> Mention:
    return Mention(source=source, link=link, title="t", date=TODAY - timedelta(days=days_ago))


def test_period_buckets():
    mentions = [_m(0, "a"), _m(3, "b"), _m(6, "c"), _m(10, "d"), _m(20, "e"), _m(40, "f")]
    s = _aggregate(W, mentions, TODAY)
    assert s.d1 == 1          # 오늘 1건
    assert s.d7 == 3          # 0,3,6일
    assert s.prev7 == 1       # 10일(8~14 구간)
    assert s.d30 == 5         # 40일 제외
    assert s.undated_total == 0


def test_dedup_by_link():
    mentions = [_m(1, "same"), _m(1, "same"), _m(2, "same")]
    s = _aggregate(W, mentions, TODAY)
    assert s.d7 == 1          # 같은 링크는 1건으로


def test_cross_source_same_link_not_deduped():
    # 서로 다른 소스의 동일 링크는 별개로 센다(dedup_key=(source,link)).
    mentions = [_m(1, "x", "naver_blog"), _m(1, "x", "dcinside")]
    s = _aggregate(W, mentions, TODAY)
    assert s.d7 == 2


def test_undated_mentions():
    mentions = [Mention(source="naver_cafe", link="c1", title="t", date=None),
                Mention(source="naver_cafe", link="c2", title="t", date=None)]
    s = _aggregate(W, mentions, TODAY)
    assert s.undated_total == 2
    assert s.d7 == 0


def test_momentum_and_rising():
    s = WhiskeyStats(whiskey=W, d7=10, prev7=4)
    assert abs(s.momentum - 1.5) < 1e-9
    assert s.is_rising is True

    flat = WhiskeyStats(whiskey=W, d7=4, prev7=4)
    assert flat.is_rising is False

    brand_new = WhiskeyStats(whiskey=W, d7=5, prev7=0)
    assert brand_new.momentum is None
    assert brand_new.is_rising is True   # 이전 기록 없이 5건 → 신규 급상승


def test_rank_and_rising_stars():
    a = WhiskeyStats(whiskey=Whiskey("a", "A", "etc", []), d1=1, d7=8, d30=20, prev7=2)
    b = WhiskeyStats(whiskey=Whiskey("b", "B", "etc", []), d1=3, d7=5, d30=30, prev7=5)
    ranked = rank_by([a, b], Period.WEEK)
    assert ranked[0] is a     # 7일 8 > 5
    ranked_day = rank_by([a, b], Period.DAY)
    assert ranked_day[0] is b  # 1일 3 > 1
    stars = rising_stars([a, b])
    assert a in stars and b not in stars


def test_parse_yyyymmdd():
    assert parse_yyyymmdd("20260722") == date(2026, 7, 22)
    assert parse_yyyymmdd("2026-07-22") is None
    assert parse_yyyymmdd("") is None


def test_parse_dc_date():
    assert _parse_dc_date("2026-07-22 14:30:00") == date(2026, 7, 22)
    assert _parse_dc_date("26.07.22") == date(2026, 7, 22)
    assert _parse_dc_date("14:30") == date.today()
    assert _parse_dc_date("07.22") == date(date.today().year, 7, 22)
    assert _parse_dc_date("garbage") is None


def test_dictionary_loads_and_unique_ids():
    whiskies = load_whiskies()
    assert len(whiskies) > 5
    ids = [w.id for w in whiskies]
    assert len(ids) == len(set(ids))         # id 유일
    for w in whiskies:
        assert w.queries                      # 질의어 최소 1개
