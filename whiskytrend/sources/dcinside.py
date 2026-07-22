"""DCinside 위스키 갤러리 소스.

갤러리 검색 목록을 파싱해 제목에 위스키명이 언급된 글을 수집한다.
목록 행의 날짜 칸(td.gall_date)의 title 속성에 'YYYY-MM-DD HH:MM:SS' 전체
시각이 들어 있어 기간별 집계가 가능하다.

주의: DCinside 는 공식 API 가 없어 HTML 구조에 의존한다. 사이트 개편 시
파싱이 깨질 수 있으므로 실패는 조용히 흡수하고(빈 결과) 로그로만 남긴다.
robots/과도한 요청 방지를 위해 페이지 수와 요청 간격을 제한한다.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..models import Mention, Whiskey
from .base import Source

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_MAX_PAGES = 5          # 질의어당 최대 페이지 (과도한 크롤링 방지)
_REQUEST_PAUSE = 0.5    # 요청 간격 (초)


class DCInsideSource(Source):
    name = "dcinside"

    def __init__(
        self,
        gallery_id: str = "whiskey",
        is_minor: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.gallery_id = gallery_id
        self.is_minor = is_minor
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": _UA})

    def _list_url(self) -> str:
        board = "mgallery/board" if self.is_minor else "board"
        return f"https://gall.dcinside.com/{board}/lists/"

    def _fetch_page(self, query: str, page: int) -> str:
        params = {
            "id": self.gallery_id,
            "s_type": "search_subject_memo",
            "s_keyword": query,
            "page": page,
        }
        resp = self.session.get(self._list_url(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _parse_rows(html: str) -> list[tuple[str, str, Optional[date]]]:
        """(제목, 링크, 날짜) 튜플 목록으로 파싱."""
        soup = BeautifulSoup(html, "lxml")
        rows: list[tuple[str, str, Optional[date]]] = []
        for tr in soup.select("tr.ub-content"):
            tit = tr.select_one("td.gall_tit a")
            if tit is None:
                continue
            title = tit.get_text(strip=True)
            href = tit.get("href", "")
            link = href if href.startswith("http") else f"https://gall.dcinside.com{href}"

            posted: Optional[date] = None
            date_cell = tr.select_one("td.gall_date")
            if date_cell is not None:
                raw = date_cell.get("title") or date_cell.get_text(strip=True)
                posted = _parse_dc_date(raw)
            rows.append((title, link, posted))
        return rows

    def fetch(self, whiskey: Whiskey, since: date) -> list[Mention]:
        mentions: list[Mention] = []
        seen_links: set[str] = set()

        for query in whiskey.queries:
            for page in range(1, _MAX_PAGES + 1):
                try:
                    html = self._fetch_page(query, page)
                except requests.RequestException as exc:
                    logger.warning("DCinside fetch 실패 (%s p%d): %s", query, page, exc)
                    break

                rows = self._parse_rows(html)
                if not rows:
                    break

                stop = False
                for title, link, posted in rows:
                    if posted is not None and posted < since:
                        stop = True
                        continue
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    mentions.append(
                        Mention(source=self.name, link=link, title=title, date=posted)
                    )
                if stop:  # 이 페이지에 조회 구간 밖 글이 나왔으면 다음 페이지는 더 오래됨
                    break
                time.sleep(_REQUEST_PAUSE)

        return mentions


def _parse_dc_date(raw: str) -> Optional[date]:
    """DCinside 날짜 문자열을 date 로 변환.

    - title 속성: '2026-07-22 14:30:00'  (전체)
    - 텍스트: '07.22' (당해), '26.07.22' (연.월.일), '14:30' (오늘)
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    # 전체 datetime (title 속성)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass

    today = date.today()
    if ":" in raw and "." not in raw and "-" not in raw:
        return today  # 'HH:MM' → 오늘 작성
    if raw.count(".") == 2:  # 'YY.MM.DD'
        try:
            return datetime.strptime(raw, "%y.%m.%d").date()
        except ValueError:
            return None
    if raw.count(".") == 1:  # 'MM.DD' → 올해로 간주
        try:
            md = datetime.strptime(raw, "%m.%d")
            return date(today.year, md.month, md.day)
        except ValueError:
            return None
    return None
