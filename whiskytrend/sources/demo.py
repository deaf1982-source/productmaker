"""데모(합성) 소스.

네이버 API 키가 아직 없을 때도 수집→집계→리포트 파이프라인 전체를
확인할 수 있도록, 위스키 id 기반 결정론적 난수로 그럴듯한 언급을 만든다.
실제 데이터가 아니며 리포트에는 '데모' 표시가 붙는다.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from ..models import Mention, Whiskey
from .base import Source


class DemoSource(Source):
    name = "demo"

    def _rng(self, whiskey: Whiskey) -> random.Random:
        seed = int(hashlib.sha256(whiskey.id.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

    def fetch(self, whiskey: Whiskey, since: date) -> list[Mention]:
        rng = self._rng(whiskey)
        today = date.today()
        span = (today - since).days or 30

        base = rng.randint(0, 8)          # 일평균 기저 언급량
        rising = rng.random() < 0.3       # 일부 위스키는 최근 급상승 패턴

        mentions: list[Mention] = []
        counter = 0
        for offset in range(span + 1):
            day = today - timedelta(days=offset)
            weight = 1.0
            if rising and offset <= 7:
                weight = 2.5              # 최근 1주 언급 급증
            count = max(0, int(rng.gauss(base * weight, 2)))
            for _ in range(count):
                counter += 1
                mentions.append(
                    Mention(
                        source=self.name,
                        link=f"https://demo.example/{whiskey.id}/{counter}",
                        title=f"[데모] {whiskey.display} 시음기",
                        date=day,
                    )
                )
        return mentions
