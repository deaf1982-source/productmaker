"""소스 공통 인터페이스."""

from __future__ import annotations

import abc
from datetime import date

from ..models import Mention, Whiskey


class Source(abc.ABC):
    """언급 데이터 소스의 추상 베이스.

    각 소스는 위스키 하나를 받아 해당 소스에서의 언급 목록을 돌려준다.
    중복 제거·기간 집계는 상위(collector)에서 처리하므로 소스는
    '최대한 많이, 중복 없이, 날짜를 채워서' 돌려주는 데만 집중한다.
    """

    #: 리포트/집계에 쓰이는 소스 식별자 (Mention.source 와 일치)
    name: str = "base"

    @property
    def available(self) -> bool:
        """호출 가능한 상태인지(예: API 키 존재). 기본값 True."""
        return True

    @abc.abstractmethod
    def fetch(self, whiskey: Whiskey, since: date) -> list[Mention]:
        """since 이후(포함)의 언급을 가능한 만큼 수집한다.

        날짜를 알 수 없는 언급도 Mention(date=None) 으로 돌려줄 수 있다.
        """
        raise NotImplementedError
