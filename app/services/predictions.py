"""Prediction persistence shared by the single and bulk endpoints.

Mirror feature: when `user.mirror_predictions` is on, a saved prediction is
copied to every pool the user belongs to. Matches are global, so the deadline /
retroactive checks done for the source pool hold for all target pools — the
caller validates once, then calls these helpers.
"""
import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Prediction, PoolMember, User


async def get_target_pool_ids(
    db: AsyncSession, user: User, source_pool_id: int
) -> list[int]:
    """Pools that should receive the prediction.

    All of the user's pools when mirroring is on; otherwise just the source.
    """
    if not user.mirror_predictions:
        return [source_pool_id]
    rows = await db.execute(
        select(PoolMember.pool_id).where(PoolMember.user_id == user.id)
    )
    pool_ids = list(rows.scalars().all())
    if source_pool_id not in pool_ids:
        pool_ids.append(source_pool_id)
    return pool_ids


async def upsert_prediction(
    db: AsyncSession,
    user_id: int,
    pool_id: int,
    match_id: int,
    predicted_home: int,
    predicted_away: int,
    now: datetime.datetime,
) -> None:
    result = await db.execute(
        select(Prediction).where(
            Prediction.user_id == user_id,
            Prediction.pool_id == pool_id,
            Prediction.match_id == match_id,
        )
    )
    prediction = result.scalar_one_or_none()
    if prediction:
        prediction.predicted_home = predicted_home
        prediction.predicted_away = predicted_away
        prediction.submitted_at = now
    else:
        db.add(
            Prediction(
                user_id=user_id,
                pool_id=pool_id,
                match_id=match_id,
                predicted_home=predicted_home,
                predicted_away=predicted_away,
                submitted_at=now,
            )
        )


async def save_prediction(
    db: AsyncSession,
    user: User,
    source_pool_id: int,
    match_id: int,
    predicted_home: int,
    predicted_away: int,
    now: datetime.datetime,
) -> int:
    """Upsert the prediction into every target pool. Returns pools written.

    Does not commit — the caller owns the transaction.
    """
    pool_ids = await get_target_pool_ids(db, user, source_pool_id)
    for pool_id in pool_ids:
        await upsert_prediction(
            db, user.id, pool_id, match_id, predicted_home, predicted_away, now
        )
    return len(pool_ids)
