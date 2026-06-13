"""
Global match mutations (shared championship data).

These operations change rows in the global `matches` table, which is shared by
every pool. They MUST NOT be exposed to pool owners or any web user: a single
match row backs all bolões at once. Run them only from the server shell via
`manage_matches.py` (or the automatic `sync_results` job).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, Prediction
from app.services.ranking import create_match_snapshots_for_all_pools
from app.services.scoring import calculate_points


async def recalculate_all_pools(db: AsyncSession, match: Match) -> int:
    """Rescore every prediction for `match` across all pools. Returns count."""
    preds = await db.execute(
        select(Prediction).where(Prediction.match_id == match.id)
    )
    count = 0
    for pred in preds.scalars().all():
        pred.points_awarded = calculate_points(
            pred.predicted_home, pred.predicted_away,
            match.home_score, match.away_score,
        )
        count += 1
    return count


async def set_result(
    db: AsyncSession,
    match: Match,
    home_score: int,
    away_score: int,
) -> int:
    """Finish a match and score every pool's predictions. Returns scored count."""
    match.home_score = home_score
    match.away_score = away_score
    match.is_finished = True
    scored = await recalculate_all_pools(db, match)
    await create_match_snapshots_for_all_pools(db, match)
    await db.commit()
    return scored


async def set_teams(
    db: AsyncSession,
    match: Match,
    home_team: str,
    away_team: str,
) -> None:
    match.home_team = home_team.strip()
    match.away_team = away_team.strip()
    await db.commit()


async def set_retroactive(db: AsyncSession, match: Match, value: bool) -> None:
    match.allow_retroactive = value
    await db.commit()
