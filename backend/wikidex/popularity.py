"""Published, deterministic popularity policy; independent of booster probabilities."""
from __future__ import annotations

import math
from typing import Iterable, Protocol

POLICY_VERSION = "log-rank-v1"
LANGUAGE_WEIGHT = 0.45
PAGEVIEW_WEIGHT = 0.55
RARITY_ORDER = ("common", "rare", "epic", "legendary", "mythic")
# These are catalogue allocations, NOT drop probabilities (which live in game.py).
CATALOGUE_SHARES = (0.50, 0.30, 0.14, 0.05, 0.01)


class PopularCard(Protocol):
    title: str
    languages: int
    monthly_views: int
    rarity: str


def popularity_score(languages: int, monthly_views: int) -> float:
    """Logarithmic weighting prevents a single traffic spike dominating linearly."""
    return LANGUAGE_WEIGHT * math.log1p(max(0, languages)) + PAGEVIEW_WEIGHT * math.log1p(max(0, monthly_views))


def rarity_counts(size: int) -> list[int]:
    """Reserve each tier then use Hamilton allocation on the remaining cards."""
    if size < 0:
        raise ValueError("Catalogue size must be non-negative")
    if size < len(RARITY_ORDER):
        return [1 if i < size else 0 for i in range(5)]
    quotas = [(size - 5) * share for share in CATALOGUE_SHARES]
    counts = [1 + math.floor(quota) for quota in quotas]
    for i in sorted(range(5), key=lambda i: (-(quotas[i] % 1), i))[:size - sum(counts)]:
        counts[i] += 1
    return counts


def assign_rarities(cards: Iterable[PopularCard]) -> None:
    """Mutate supplied active catalogue; stable title tie-break, no random state."""
    ranked = sorted(cards, key=lambda c: (popularity_score(c.languages, c.monthly_views), c.title.casefold(), c.title))
    offset = 0
    for rarity, count in zip(RARITY_ORDER, rarity_counts(len(ranked))):
        for card in ranked[offset:offset + count]:
            card.rarity = rarity
        offset += count
