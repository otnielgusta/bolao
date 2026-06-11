"""
Background auto-sync loop.

A match becomes "pending" when the current time passes its estimated end:
  - group stage: kickoff + 110 min (90 + stoppage)
  - knockout:    kickoff + 150 min (120 + stoppage, penalties ignored)
plus a 1-minute grace period.

While at least one pending match exists, the loop calls football-data.org
once per minute until every pending match is finished and scored.
When nothing is pending it just rechecks the schedule locally (no API call).
"""
import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from app.database import async_session
from app.models import Match
from app.services.sync import sync_results

logger = logging.getLogger("autosync")

GROUP_DURATION_MIN = 110
KNOCKOUT_DURATION_MIN = 150
GRACE_MIN = 1
CHECK_INTERVAL_SECONDS = 60


def _estimated_end(match: Match) -> dt.datetime:
    duration = GROUP_DURATION_MIN if match.stage.startswith("Grupo") else KNOCKOUT_DURATION_MIN
    return match.match_datetime + dt.timedelta(minutes=duration + GRACE_MIN)


async def _has_pending() -> bool:
    now = dt.datetime.now(dt.timezone.utc)
    async with async_session() as db:
        result = await db.execute(
            select(Match).where(
                Match.is_finished.is_(False),
                Match.external_id.isnot(None),
            )
        )
        return any(_estimated_end(m) <= now for m in result.scalars())


async def auto_sync_loop():
    logger.info("Auto-sync loop started.")
    while True:
        try:
            if await _has_pending():
                async with async_session() as db:
                    summary = await sync_results(db)
                logger.info(
                    "Auto-sync: %s finished, %s predictions scored.",
                    summary["finished"], summary["predictions_scored"],
                )
        except asyncio.CancelledError:
            logger.info("Auto-sync loop stopped.")
            raise
        except Exception:
            logger.exception("Auto-sync iteration failed; will retry.")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
