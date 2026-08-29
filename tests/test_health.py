"""수집 건강도 점검 테스트 (네트워크 불필요, 임시 리포트 기반)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whiskytrend.health import assess, collection_volume  # noqa: E402
from whiskytrend.models import Whiskey, WhiskeyStats  # noqa: E402
from whiskytrend.report import write_csv  # noqa: E402


def _stats(d30_values: list[int]) -> list[WhiskeyStats]:
    """각 위스키의 d30 만 지정해 집계 결과 목록을 만든다."""
    out = []
    for i, v in enumerate(d30_values):
        w = Whiskey(id=f"w{i}", display=f"위스키{i}", category="etc", queries=["q"])
        s = WhiskeyStats(whiskey=w)
        s.d30 = v
        s.d7 = v // 4
        s.prev7 = v // 4
        out.append(s)
    return out


def _write_history(out_dir: Path, stamp: str, d30_values: list[int]) -> None:
    write_csv(_stats(d30_values), out_dir / f"whisky_ranking_{stamp}.csv")


def test_collection_volume_sums_d30():
    assert collection_volume(_stats([100, 200, 300])) == 600


def test_no_history_is_not_anomalous(tmp_path):
    report = assess(_stats([100, 100]), tmp_path, "2026-08-13")
    assert report.reference is None
    assert report.anomalous is False
    assert report.suppress_rising is False


def test_sudden_drop_flagged(tmp_path):
    # 직전 정상 회차들: 합계 6000 안팎
    _write_history(tmp_path, "2026-07-22", [3000, 3000])
    _write_history(tmp_path, "2026-08-07", [3500, 3500])
    # 이번 회차: 합계 800 (기준의 ~13%) → 이상 급감
    report = assess(_stats([400, 400]), tmp_path, "2026-08-13")
    assert report.anomalous is True
    assert report.suppress_rising is True
    assert report.reference is not None
    assert "급감" in (report.message or "")


def test_normal_volume_not_flagged(tmp_path):
    _write_history(tmp_path, "2026-07-22", [3000, 3000])
    _write_history(tmp_path, "2026-08-07", [3500, 3500])
    # 이번 회차: 합계 5800 (소폭 감소) → 정상
    report = assess(_stats([2900, 2900]), tmp_path, "2026-08-13")
    assert report.anomalous is False
    assert report.suppress_rising is False


def test_same_stamp_excluded_from_reference(tmp_path):
    # 같은 날짜의 기존 파일은 기준에서 제외되어야 한다(재실행 대비).
    _write_history(tmp_path, "2026-08-13", [400, 400])
    report = assess(_stats([400, 400]), tmp_path, "2026-08-13")
    # 비교할 과거 데이터가 없으므로 정상 처리
    assert report.reference is None
    assert report.anomalous is False


def test_tiny_reference_not_flagged(tmp_path):
    # 기준 수집량이 너무 작으면(초기) 급감 판정을 하지 않는다.
    _write_history(tmp_path, "2026-08-07", [10, 10])
    report = assess(_stats([1]), tmp_path, "2026-08-13")
    assert report.anomalous is False


def test_suppress_rising_blanks_csv_column(tmp_path):
    # 저품질 판정 시 CSV의 rising 컬럼이 비워지는지 확인.
    stats = _stats([12])
    stats[0].d7 = 10
    stats[0].prev7 = 2  # momentum +400% → 평소라면 rising=Y
    assert stats[0].is_rising is True

    path = write_csv(stats, tmp_path / "whisky_ranking_2026-08-13.csv", suppress_rising=True)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = lines[0].split(",")
    row = lines[1].split(",")
    rising_idx = header.index("rising")
    assert row[rising_idx] == ""  # 보류되어 비어 있어야 함
