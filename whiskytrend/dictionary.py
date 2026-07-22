"""위스키 사전 로딩."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Whiskey

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "whiskies.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """YAML 설정 전체를 dict 로 읽는다."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def load_whiskies(path: str | Path = DEFAULT_CONFIG) -> list[Whiskey]:
    """사전 항목을 Whiskey 리스트로 변환한다.

    id 중복은 설정 실수이므로 즉시 에러를 낸다.
    """
    data = load_config(path)
    raw = data.get("whiskies") or []

    whiskies: list[Whiskey] = []
    seen_ids: set[str] = set()
    for item in raw:
        wid = item["id"]
        if wid in seen_ids:
            raise ValueError(f"중복된 위스키 id: {wid!r}")
        seen_ids.add(wid)

        queries = item.get("queries") or [item["display"]]
        whiskies.append(
            Whiskey(
                id=wid,
                display=item["display"],
                category=item.get("category", "etc"),
                queries=list(queries),
            )
        )
    return whiskies
