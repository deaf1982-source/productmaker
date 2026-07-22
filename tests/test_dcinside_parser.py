"""DCinside 목록 HTML 파싱 테스트 (네트워크 불필요, 픽스처 기반)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whiskytrend.sources.dcinside import DCInsideSource  # noqa: E402

# DCinside 마이너 갤러리 목록 행의 대표 구조 (title 속성에 전체 시각 포함)
SAMPLE_HTML = """
<table class="gall_list">
 <tbody>
  <tr class="ub-content us-post" data-no="1001">
    <td class="gall_num">1001</td>
    <td class="gall_tit ub-word">
      <a href="/mgallery/board/view/?id=whiskey&no=1001">발베니 12 시음기 남깁니다</a>
    </td>
    <td class="gall_writer">글쓴이</td>
    <td class="gall_date" title="2026-07-22 14:30:11">07.22</td>
  </tr>
  <tr class="ub-content us-post" data-no="1000">
    <td class="gall_num">1000</td>
    <td class="gall_tit ub-word">
      <a href="/mgallery/board/view/?id=whiskey&no=1000">발베니 vs 글렌피딕</a>
    </td>
    <td class="gall_writer">다른유저</td>
    <td class="gall_date" title="2026-07-10 09:05:00">07.10</td>
  </tr>
  <tr class="ub-content us-post" data-no="998">
    <td class="gall_tit ub-word"><a href="/mgallery/board/view/?id=whiskey&no=998">과거글</a></td>
    <td class="gall_date">25.12.31</td>
  </tr>
 </tbody>
</table>
"""


def test_parse_rows_extracts_title_link_date():
    rows = DCInsideSource._parse_rows(SAMPLE_HTML)
    assert len(rows) == 3

    title, link, posted = rows[0]
    assert title == "발베니 12 시음기 남깁니다"
    assert link == "https://gall.dcinside.com/mgallery/board/view/?id=whiskey&no=1001"
    assert posted == date(2026, 7, 22)          # title 속성의 전체 시각 사용

    # title 속성이 없어도 텍스트('25.12.31')로 날짜를 복구
    assert rows[2][2] == date(2025, 12, 31)


def test_parse_rows_empty_html():
    assert DCInsideSource._parse_rows("<html><body>없음</body></html>") == []
