from collections.abc import Sequence

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, PoolMember, Prediction, RankingSnapshot
from app.templating import local_datetime


async def build_ranking(
    db: AsyncSession,
    pool_id: int,
    match_ids: Sequence[int] | None = None,
) -> list[dict]:
    members = await db.execute(
        select(PoolMember)
        .where(PoolMember.pool_id == pool_id)
        .options(selectinload(PoolMember.user))
    )
    members = members.scalars().all()

    ranking = []
    for member in members:
        if match_ids is not None and not match_ids:
            predictions = []
        else:
            query = select(Prediction).where(
                Prediction.pool_id == pool_id,
                Prediction.user_id == member.user_id,
                Prediction.points_awarded.isnot(None),
            )
            if match_ids is not None:
                query = query.where(Prediction.match_id.in_(list(match_ids)))
            result = await db.execute(query)
            predictions = result.scalars().all()

        total = sum(pred.points_awarded for pred in predictions)
        counts = {10: 0, 7: 0, 5: 0, 3: 0, 1: 0, 0: 0}
        last_submitted = 0.0
        for pred in predictions:
            counts[pred.points_awarded] = counts.get(pred.points_awarded, 0) + 1
            last_submitted = max(last_submitted, pred.submitted_at.timestamp())

        ranking.append({
            "user_id": member.user_id,
            "display_name": member.user.display_name,
            "total": total,
            "counts": counts,
            "count_10": counts[10],
            "count_7": counts[7],
            "list_submitted_at": last_submitted if predictions else float("inf"),
            "is_current_user": False,
            "position_delta": 0,
            "points_to_pass": None,
            "next_display_name": None,
        })

    ranking.sort(
        key=lambda row: (
            -row["total"],
            -row["count_10"],
            -row["count_7"],
            row["list_submitted_at"],
        )
    )

    for position, row in enumerate(ranking, 1):
        row["position"] = position

    return ranking


async def create_match_ranking_snapshots(
    db: AsyncSession,
    pool_id: int,
    match: Match,
) -> None:
    finished_match_ids = await _finished_match_ids_until(db, match)
    ranking = await build_ranking(db, pool_id, finished_match_ids)
    snapshot_date = local_datetime(match.match_datetime).date()

    await db.execute(
        delete(RankingSnapshot).where(
            RankingSnapshot.pool_id == pool_id,
            RankingSnapshot.match_id == match.id,
        )
    )
    for row in ranking:
        db.add(
            RankingSnapshot(
                pool_id=pool_id,
                match_id=match.id,
                user_id=row["user_id"],
                snapshot_date=snapshot_date,
                position=row["position"],
                total=row["total"],
                count_10=row["count_10"],
                count_7=row["count_7"],
            )
        )


async def create_match_snapshots_for_all_pools(
    db: AsyncSession,
    match: Match,
) -> None:
    pool_ids = await db.execute(select(distinct(PoolMember.pool_id)))
    for pool_id in pool_ids.scalars().all():
        await create_match_ranking_snapshots(db, pool_id, match)


async def ensure_pool_snapshots(
    db: AsyncSession,
    pool_id: int,
    matches: Sequence[Match],
) -> None:
    existing = await db.execute(
        select(RankingSnapshot.match_id, func.count(RankingSnapshot.id))
        .where(RankingSnapshot.pool_id == pool_id)
        .group_by(RankingSnapshot.match_id)
    )
    snapshot_counts = dict(existing.all())
    member_count_result = await db.execute(
        select(func.count(PoolMember.id)).where(PoolMember.pool_id == pool_id)
    )
    member_count = member_count_result.scalar() or 0
    for match in matches:
        if not match.is_finished:
            continue
        if snapshot_counts.get(match.id, 0) < member_count:
            await create_match_ranking_snapshots(db, pool_id, match)


async def _finished_match_ids_until(db: AsyncSession, match: Match) -> list[int]:
    result = await db.execute(
        select(Match.id)
        .where(
            Match.is_finished.is_(True),
            Match.match_datetime <= match.match_datetime,
        )
        .order_by(Match.match_datetime)
    )
    return list(result.scalars().all())
