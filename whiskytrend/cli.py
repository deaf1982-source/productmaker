"""whiskytrend 커맨드라인 진입점.

예)
    # 데모(합성) 데이터로 파이프라인·리포트 형태 확인 — 키 불필요
    python -m whiskytrend.cli --demo

    # 실제 수집 (.env 에 네이버 키 설정 후)
    python -m whiskytrend.cli --sources naver_blog,naver_cafe,dcinside
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path

from . import __version__
from .collector import collect
from .dictionary import load_config, load_whiskies
from .ranking import Period, rank_by, rising_stars
from .report import write_csv, write_html
from .sources import DCInsideSource, DemoSource, NaverBlogSource, NaverCafeSource

_ROOT = Path(__file__).resolve().parent.parent
_ALL_SOURCES = ["naver_blog", "naver_cafe", "dcinside"]


def _load_dotenv(path: Path) -> None:
    """의존성 없이 .env 의 KEY=VALUE 를 환경변수로 읽는다(기존 값 우선)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _build_sources(names: list[str], config: dict) -> list:
    dc_cfg = config.get("dcinside", {})
    factory = {
        "naver_blog": lambda: NaverBlogSource(),
        "naver_cafe": lambda: NaverCafeSource(),
        "dcinside": lambda: DCInsideSource(
            gallery_id=dc_cfg.get("gallery_id", "whiskey"),
            is_minor=dc_cfg.get("is_minor", True),
        ),
    }
    sources = []
    for name in names:
        if name not in factory:
            raise SystemExit(f"알 수 없는 소스: {name} (가능: {', '.join(factory)})")
        sources.append(factory[name]())
    return sources


def _print_summary(stats, period: Period, top: int) -> None:
    ranked = rank_by(stats, period)[:top]
    label = {"d1": "최근 1일", "d7": "최근 7일", "d30": "최근 30일"}[period.value]
    print(f"\n== {label} 언급 랭킹 TOP {len(ranked)} ==")
    for i, s in enumerate(ranked, 1):
        val = getattr(s, period.value)
        flag = " 🔥" if s.is_rising else ""
        print(f"{i:>2}. {s.whiskey.display:<18} {val:>4}건  (7일 {s.d7} / 30일 {s.d30}){flag}")

    stars = rising_stars(stats)
    if stars:
        print("\n== 🔥 급상승 (연재 우선 후보) ==")
        for s in stars:
            m = s.momentum
            trend = f"{m*100:+.0f}%" if m is not None else "신규"
            print(f"  - {s.whiskey.display:<18} 7일 {s.d7}건  ({trend}, 직전7일 {s.prev7})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whiskytrend",
        description="위스키 언급량을 수집해 최근 랭킹/급상승을 뽑는다.",
    )
    parser.add_argument("--demo", action="store_true", help="합성 데이터로 실행(키 불필요)")
    parser.add_argument(
        "--sources",
        default=",".join(_ALL_SOURCES),
        help=f"쉼표 구분 소스 목록. 기본: {','.join(_ALL_SOURCES)}",
    )
    parser.add_argument("--config", default=None, help="whiskies.yaml 경로")
    parser.add_argument("--out", default=str(_ROOT / "reports"), help="리포트 출력 폴더")
    parser.add_argument(
        "--period",
        choices=[p.value for p in Period],
        default=Period.WEEK.value,
        help="콘솔 요약 정렬 기간 (d1/d7/d30)",
    )
    parser.add_argument("--top", type=int, default=10, help="콘솔 요약에 출력할 개수")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그")
    parser.add_argument("--version", action="version", version=f"whiskytrend {__version__}")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    _load_dotenv(_ROOT / ".env")

    config_path = args.config
    whiskies = load_whiskies(config_path) if config_path else load_whiskies()
    config = load_config(config_path) if config_path else load_config()

    if args.demo:
        sources = [DemoSource()]
        source_names = ["demo"]
    else:
        names = [n.strip() for n in args.sources.split(",") if n.strip()]
        sources = _build_sources(names, config)
        source_names = names

    stats = collect(whiskies, sources)

    used = [s.name for s in sources if s.available]
    unavailable = [s.name for s in sources if not s.available]
    if unavailable:
        print(f"⚠️  인증정보가 없어 건너뛴 소스: {', '.join(unavailable)}")
        print("    → .env 에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 설정 후 다시 실행하세요.")
        print("    → 지금 형태만 보려면: python -m whiskytrend.cli --demo\n")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    csv_path = write_csv(stats, out_dir / f"whisky_ranking_{stamp}.csv")
    html_path = write_html(
        stats, out_dir / f"whisky_ranking_{stamp}.html",
        sources=used or source_names, demo=args.demo,
    )

    _print_summary(stats, Period(args.period), args.top)
    print(f"\n📄 CSV : {csv_path}")
    print(f"📄 HTML: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
