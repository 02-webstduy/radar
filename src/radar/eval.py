"""离线评测：在已标注的子集上比较「关键词基线」和「画像排序」的 nDCG。"""

from __future__ import annotations

import math

from .config import Config
from .storage import Store


def ndcg_at_k(ranked: list[int], labels: dict[int, int], k: int) -> float:
    gains = [labels.get(item_id, 0) for item_id in ranked[:k]]
    dcg = sum((2 ** g - 1) / math.log2(pos + 2) for pos, g in enumerate(gains))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(pos + 2) for pos, g in enumerate(ideal))
    return round(dcg / idcg, 3) if idcg else 0.0


def precision_at_k(ranked: list[int], labels: dict[int, int], k: int) -> float:
    top = ranked[:k]
    return round(sum(labels.get(i, 0) for i in top) / k, 3) if top else 0.0


def _keyword_score(item: dict, cfg: Config) -> float:
    text = f"{item['title']} {item['summary']}".lower()
    hits = [k for k in cfg.profile.keywords if k.lower() in text]
    return len(hits) + cfg.weights.get(item["source"], 1.0)


def compare(store: Store, cfg: Config, profile: dict) -> dict:
    labeled = store.labeled_items()
    labels = store.labels()
    if not labeled:
        return {"labeled": 0, "message": "先点几条「相关 / 不相关」再评测"}

    by_keyword = sorted(labeled, key=lambda it: _keyword_score(it, cfg), reverse=True)
    by_profile = sorted(labeled, key=lambda it: it["score"], reverse=True)
    k = min(5, len(labeled))
    return {
        "labeled": len(labeled),
        "k": k,
        "keyword": {
            "ndcg": ndcg_at_k([i["id"] for i in by_keyword], labels, k),
            "precision": precision_at_k([i["id"] for i in by_keyword], labels, k),
        },
        "profile": {
            "ndcg": ndcg_at_k([i["id"] for i in by_profile], labels, k),
            "precision": precision_at_k([i["id"] for i in by_profile], labels, k),
        },
        "note": "只在已标注条目上比较；标注越多越可信",
    }
