import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict

from config import EVENT_WEIGHTS, TOP_N

logger = logging.getLogger(__name__)


@dataclass
class ItemScore:
    item_id: str
    score: float = 0.0
    event_count: int = 0


class UserEventAggregator:
    """
    In-memory aggregator. Tracks item scores per user.
    In Stage 4 we will flush this to Postgres periodically.
    """

    def __init__(self):
        # user_id -> item_id -> ItemScore
        self._scores: DefaultDict[str, dict[str, ItemScore]] = defaultdict(dict)
        self._total_events_processed = 0

    def process(self, event: dict) -> None:
        user_id = event.get("user_id")
        item_id = event.get("item_id")
        event_type = event.get("event_type")

        if not all([user_id, item_id, event_type]):
            logger.warning("skipping_malformed_event event=%s", event)
            return

        weight = EVENT_WEIGHTS.get(event_type, 0.0)
        if weight == 0.0:
            logger.warning("unknown_event_type type=%s", event_type)
            return

        user_items = self._scores[user_id]

        if item_id not in user_items:
            user_items[item_id] = ItemScore(item_id=item_id)

        user_items[item_id].score += weight
        user_items[item_id].event_count += 1
        self._total_events_processed += 1

        logger.debug(
            "score_updated user_id=%s item_id=%s score=%.2f",
            user_id, item_id, user_items[item_id].score,
        )

    def get_top_items(self, user_id: str, n: int = TOP_N) -> list[ItemScore]:
        user_items = self._scores.get(user_id, {})
        sorted_items = sorted(
            user_items.values(),
            key=lambda x: x.score,
            reverse=True,
        )
        return sorted_items[:n]

    def get_stats(self) -> dict:
        return {
            "total_users": len(self._scores),
            "total_events_processed": self._total_events_processed,
            "total_unique_user_item_pairs": sum(
                len(items) for items in self._scores.values()
            ),
        }