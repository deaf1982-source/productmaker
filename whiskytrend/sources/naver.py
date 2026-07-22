"""네이버 검색 오픈API 소스.

https://developers.naver.com/docs/serviceapi/search/blog/blog.md

- 블로그 검색: 항목별 게시일(postdate)을 주므로 기간별(1/7/30일) 집계 가능.
- 카페글 검색: 항목별 날짜를 주지 않으므로 '날짜 미상' 언급으로만 집계(폭 지표).

인증정보(NAVER_CLIENT_ID / NAVER_CLIENT_SECRET)가 없으면 available=False 가 되어
collector 가 자동으로 이 소스를 건너뛴다. → 키 없이도 파이프라인은 동작한다.
"""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Optional

import requests

from ..models import Mention, Whiskey, parse_yyyymmdd
from .base import Source

_API_BASE = "https://openapi.naver.com/v1/search"
_DISPLAY = 100          # 페이지당 최대 100
_MAX_START = 1000       # 네이버가 허용하는 start 최댓값
_REQUEST_PAUSE = 0.1    # 호출 간 짧은 간격 (초)


class _NaverBase(Source):
    """네이버 검색 API 공통 로직."""

    endpoint: str = ""   # "blog" | "cafearticle"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET")
        self.session = session or requests.Session()

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Naver-Client-Id": self.client_id or "",
            "X-Naver-Client-Secret": self.client_secret or "",
        }

    def _search_page(self, query: str, start: int) -> dict:
        url = f"{_API_BASE}/{self.endpoint}.json"
        params = {"query": query, "display": _DISPLAY, "start": start, "sort": "date"}
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _item_date(self, item: dict) -> Optional[date]:  # noqa: D401
        """항목에서 게시일을 뽑는다. 하위 클래스에서 구현."""
        return None

    def fetch(self, whiskey: Whiskey, since: date) -> list[Mention]:
        if not self.available:
            return []

        mentions: list[Mention] = []
        seen_links: set[str] = set()

        for query in whiskey.queries:
            start = 1
            stop_query = False
            while start <= _MAX_START and not stop_query:
                try:
                    data = self._search_page(query, start)
                except requests.RequestException:
                    break  # 이 질의어는 포기하고 다음 질의어로

                items = data.get("items") or []
                if not items:
                    break

                for item in items:
                    link = item.get("link", "")
                    if not link or link in seen_links:
                        continue
                    item_date = self._item_date(item)
                    # 날짜가 있는데 조회 구간보다 오래됐으면(최신순 정렬) 이 질의어 종료
                    if item_date is not None and item_date < since:
                        stop_query = True
                        break
                    seen_links.add(link)
                    mentions.append(
                        Mention(
                            source=self.name,
                            link=link,
                            title=_strip_tags(item.get("title", "")),
                            date=item_date,
                        )
                    )

                if len(items) < _DISPLAY:
                    break
                start += _DISPLAY
                time.sleep(_REQUEST_PAUSE)

        return mentions


class NaverBlogSource(_NaverBase):
    name = "naver_blog"
    endpoint = "blog"

    def _item_date(self, item: dict) -> Optional[date]:
        # 블로그 검색은 postdate 를 'YYYYMMDD' 로 준다.
        return parse_yyyymmdd(item.get("postdate", ""))


class NaverCafeSource(_NaverBase):
    name = "naver_cafe"
    endpoint = "cafearticle"

    def _item_date(self, item: dict) -> Optional[date]:
        # 카페글 검색은 항목별 날짜를 제공하지 않는다 → 날짜 미상.
        return None


def _strip_tags(text: str) -> str:
    """검색 결과 제목의 <b> 하이라이트 태그 제거."""
    return (
        text.replace("<b>", "")
        .replace("</b>", "")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )
