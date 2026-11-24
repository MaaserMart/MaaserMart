"""Rank recommendations from a member's activity (§6.2.11)."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from django.conf import settings

from apps.charities.services import recommendation_charities
from apps.events.services import recommendation_signals

logger = logging.getLogger("maasermart.recommendations.audit")


@dataclass(frozen=True)
class Recommendation:
    """Fields the dashboard needs, without exposing a charity model."""

    id: int
    name: str
    tagline: str | None


def recommend_for(user_id) -> tuple[Recommendation, ...]:
    """Return published charities in tier order, excluding every prior rejection.

    Thresholds are proportions, and are strict as in the design. Defaults are
    provisional: the design leaves them and the minimum history to testing.
    Hidden events remain in the denominator but not the numerator.
    """
    total, counts, rejected = recommendation_signals(user_id)
    minimum = getattr(settings, "RECOMMENDATIONS_MIN_HISTORY", 3)
    x = Fraction(str(getattr(settings, "RECOMMENDATIONS_THRESHOLD", 0.2)))
    y = Fraction(str(getattr(settings, "RECOMMENDATIONS_SINGLE_OFFSET", 0.1)))
    z = Fraction(str(getattr(settings, "RECOMMENDATIONS_PAIR_OFFSET", 0.2)))
    if total < minimum or total == 0:
        logger.info("recommendation user_id=%s total=%s tiers=[]", user_id, total)
        return ()

    charities = recommendation_charities(counts.keys())
    by_id = {charity.id: charity for charity in charities}
    domain_counts = defaultdict(int)
    location_counts = defaultdict(int)
    pair_counts = defaultdict(int)
    for charity_id, count in counts.items():
        charity = by_id.get(charity_id)
        if charity is None:
            continue
        for domain_id in charity.domain_ids:
            domain_counts[domain_id] += count
            for location_id in charity.location_ids:
                pair_counts[domain_id, location_id] += count
        for location_id in charity.location_ids:
            location_counts[location_id] += count

    tiers = [[], [], []]
    for charity in charities:
        if not charity.is_visible or charity.id in rejected:
            continue
        if Fraction(counts.get(charity.id, 0), total) > x:
            tiers[0].append(charity)
        else:
            if any(
                Fraction(pair_counts[domain_id, location_id], total) > x + z
                for domain_id in charity.domain_ids
                for location_id in charity.location_ids
            ):
                tiers[1].append(charity)
            elif any(
                Fraction(domain_counts[domain_id], total) > x + y
                for domain_id in charity.domain_ids
            ) or any(
                Fraction(location_counts[location_id], total) > x + y
                for location_id in charity.location_ids
            ):
                tiers[2].append(charity)

    for tier in tiers:
        tier.sort(key=lambda item: (item.name.casefold(), item.id))
    ordered = [charity for tier in tiers for charity in tier]
    # Technical logs are server-side only. Do not include event IDs, text or names.
    logger.info(
        "recommendation user_id=%s total=%s domain_shares=%s location_shares=%s tiers=%s",
        user_id,
        total,
        {key: value / total for key, value in domain_counts.items()},
        {key: value / total for key, value in location_counts.items()},
        [[charity.id for charity in tier] for tier in tiers],
    )
    return tuple(Recommendation(item.id, item.name, item.tagline) for item in ordered)
