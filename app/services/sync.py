"""
Result synchronization with football-data.org (v4 API).

Strategy:
- Fetch all FIFA World Cup 2026 matches from the API.
- Match API entries to local Match rows:
    1. by external_id (already linked);
    2. group stage: by team names mapped via TLA codes;
    3. knockout: by stage + closest kickoff among unlinked rows
       (placeholders get real team names once defined).
- Update kickoff datetimes from the API (authoritative).
- For FINISHED matches with a published score: store score, mark finished,
  recalculate points of every prediction across all pools.

Knockout scores use the 90-minute regular-time score for the bolao.
"""
import datetime as dt
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Match, Prediction
from app.services.ranking import create_match_snapshots_for_all_pools
from app.services.scoring import calculate_points
from app.services.teams import TEAMS

logger = logging.getLogger(__name__)

API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
Score = tuple[int, int]

STAGE_MAP = {
    "GROUP_STAGE": None,  # group stage rows already named "Grupo X"
    "LAST_32": "32-avos",
    "LAST_16": "Oitavas",
    "QUARTER_FINALS": "Quartas",
    "SEMI_FINALS": "Semifinal",
    "THIRD_PLACE": "3º Lugar",
    "FINAL": "Final",
}


async def fetch_api_matches() -> list[dict]:
    headers = {"X-Auth-Token": settings.football_data_token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(API_URL, headers=headers)
        resp.raise_for_status()
        return resp.json()["matches"]


def _parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _score_pair(score_node: dict | None) -> Score | None:
    if not score_node:
        return None
    home = score_node.get("home")
    away = score_node.get("away")
    if home is None:
        home = score_node.get("homeTeam")
    if away is None:
        away = score_node.get("awayTeam")
    if home is None or away is None:
        return None
    return int(home), int(away)


def _subtract_scores(base: Score, *deductions: Score | None) -> Score | None:
    home, away = base
    for deduction in deductions:
        if deduction is None:
            continue
        home -= deduction[0]
        away -= deduction[1]
    if home < 0 or away < 0:
        return None
    return home, away


def extract_bolao_score(api_match: dict) -> Score | None:
    """Return the score that counts for the bolao: regular time only."""
    score = api_match.get("score") or {}
    regular_time = _score_pair(score.get("regularTime"))
    if regular_time is not None:
        return regular_time

    full_time = _score_pair(score.get("fullTime"))
    if full_time is None:
        return None

    duration = score.get("duration")
    if duration in {None, "REGULAR"}:
        return full_time

    extra_time = _score_pair(score.get("extraTime"))
    if duration == "EXTRA_TIME":
        if extra_time is None:
            return None
        return _subtract_scores(full_time, extra_time)

    penalties = _score_pair(score.get("penalties"))
    if duration == "PENALTY_SHOOTOUT":
        if extra_time is None or penalties is None:
            return None
        return _subtract_scores(full_time, extra_time, penalties)

    return None


async def _find_local_match(db: AsyncSession, api_match: dict) -> Match | None:
    result = await db.execute(
        select(Match).where(Match.external_id == api_match["id"])
    )
    found = result.scalar_one_or_none()
    if found:
        return found

    home_tla = (api_match.get("homeTeam") or {}).get("tla")
    away_tla = (api_match.get("awayTeam") or {}).get("tla")
    stage = api_match["stage"]

    if stage == "GROUP_STAGE":
        if not home_tla or not away_tla:
            return None
        home_name = TEAMS.get(home_tla)
        away_name = TEAMS.get(away_tla)
        if not home_name or not away_name:
            logger.warning("Unknown TLA: %s/%s", home_tla, away_tla)
            return None
        result = await db.execute(
            select(Match).where(
                Match.home_team == home_name,
                Match.away_team == away_name,
                Match.external_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # Knockout: closest unlinked row in the same stage
    local_stage = STAGE_MAP.get(stage)
    if not local_stage:
        return None
    api_dt = _parse_utc(api_match["utcDate"])
    result = await db.execute(
        select(Match).where(
            Match.stage == local_stage,
            Match.external_id.is_(None),
        )
    )
    candidates = result.scalars().all()
    if not candidates:
        return None
    return min(candidates, key=lambda m: abs((m.match_datetime - api_dt).total_seconds()))


async def _recalculate_points(db: AsyncSession, match: Match):
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


async def sync_results(db: AsyncSession) -> dict:
    """Returns summary: {linked, updated_schedule, finished, predictions_scored}."""
    api_matches = await fetch_api_matches()
    summary = {"linked": 0, "updated_schedule": 0, "finished": 0, "predictions_scored": 0}

    for api_match in api_matches:
        local = await _find_local_match(db, api_match)
        if not local:
            continue

        if local.external_id is None:
            local.external_id = api_match["id"]
            summary["linked"] += 1

        # Kickoff datetime (API is authoritative)
        api_dt = _parse_utc(api_match["utcDate"])
        if local.match_datetime != api_dt:
            local.match_datetime = api_dt
            summary["updated_schedule"] += 1

        # Knockout team names once defined
        home_tla = (api_match.get("homeTeam") or {}).get("tla")
        away_tla = (api_match.get("awayTeam") or {}).get("tla")
        if home_tla and home_tla in TEAMS and local.home_team != TEAMS[home_tla]:
            local.home_team = TEAMS[home_tla]
        if away_tla and away_tla in TEAMS and local.away_team != TEAMS[away_tla]:
            local.away_team = TEAMS[away_tla]

        # Result
        if api_match["status"] == "FINISHED" and not local.is_finished:
            bolao_score = extract_bolao_score(api_match)
            if bolao_score is not None:
                home_score, away_score = bolao_score
                local.home_score = home_score
                local.away_score = away_score
                local.is_finished = True
                summary["finished"] += 1
                summary["predictions_scored"] += await _recalculate_points(db, local)
                await create_match_snapshots_for_all_pools(db, local)

    await db.commit()
    return summary
