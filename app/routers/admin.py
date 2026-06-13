import datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Pool, PoolMember, Match, Prediction
from app.routers.auth import require_user
from app.services.scoring import calculate_points
from app.services.rules import PREDICTION_DEADLINE_SECONDS
from app.templating import create_templates

router = APIRouter(prefix="/admin", tags=["admin"])
templates = create_templates()


async def require_pool_owner(pool_id: int, user: User, db: AsyncSession) -> Pool:
    pool = await db.get(Pool, pool_id)
    if not pool or pool.owner_id != user.id:
        raise HTTPException(403, "Acesso negado.")
    return pool


async def _build_pending_predictions(
    db: AsyncSession,
    pool_id: int,
    matches: list[Match],
    members: list[PoolMember],
    now: datetime.datetime,
) -> dict:
    predictions = await db.execute(
        select(Prediction).where(Prediction.pool_id == pool_id)
    )
    predicted_users_by_match: dict[int, set[int]] = {}
    for prediction in predictions.scalars().all():
        predicted_users_by_match.setdefault(prediction.match_id, set()).add(
            prediction.user_id
        )

    open_matches = [
        match
        for match in matches
        if not match.is_finished
        and (
            now <= match.match_datetime - datetime.timedelta(
                seconds=PREDICTION_DEADLINE_SECONDS
            )
            or match.allow_retroactive
        )
    ]

    missing_by_member: dict[int, dict] = {}
    missing_open_predictions = 0
    for match in open_matches:
        predicted_users = predicted_users_by_match.get(match.id, set())
        for member in members:
            if member.user_id in predicted_users:
                continue
            missing_open_predictions += 1
            item = missing_by_member.setdefault(
                member.user_id,
                {"name": member.user.display_name, "count": 0},
            )
            item["count"] += 1

    return {
        "open_matches": open_matches,
        "missing_open_predictions": missing_open_predictions,
        "missing_by_member": missing_by_member,
    }


def _pending_reminder_text(
    pool: Pool,
    missing_by_member: dict[int, dict],
    base_url: str,
) -> str:
    lines = [f"Lembrete - Bolao {pool.name}", ""]
    if not missing_by_member:
        lines.append("Todo mundo esta em dia com os jogos abertos.")
    else:
        lines.append("Ainda faltam palpites nos jogos abertos:")
        for item in sorted(missing_by_member.values(), key=lambda value: value["name"]):
            lines.append(
                f"- {item['name']}: {item['count']} jogo(s) sem palpite"
            )
    lines.extend(["", f"Acesse: {base_url}/pools/{pool.id}"])
    return "\n".join(lines)


@router.get("/pool/{pool_id}", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    pool_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await require_pool_owner(pool_id, user, db)
    matches = await db.execute(select(Match).order_by(Match.match_datetime))
    matches = matches.scalars().all()
    members = await db.execute(
        select(PoolMember)
        .where(PoolMember.pool_id == pool_id)
        .options(selectinload(PoolMember.user))
    )
    members = members.scalars().all()
    now = datetime.datetime.now(datetime.timezone.utc)
    pending = await _build_pending_predictions(db, pool_id, matches, members, now)

    admin_stats = {
        "pending_results": len(
            [
                match
                for match in matches
                if not match.is_finished and match.match_datetime < now
            ]
        ),
        "open_matches": len(pending["open_matches"]),
        "missing_open_predictions": pending["missing_open_predictions"],
        "members_missing_open": len(pending["missing_by_member"]),
        "members": len(members),
    }

    return templates.TemplateResponse(request, "admin/panel.html", {
        "user": user,
        "pool": pool,
        "matches": matches,
        "members": members,
        "admin_stats": admin_stats,
    })


@router.get("/pool/{pool_id}/pending-reminder_copy", response_class=PlainTextResponse)
async def pending_reminder_copy(
    request: Request,
    pool_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await require_pool_owner(pool_id, user, db)
    matches = await db.execute(select(Match).order_by(Match.match_datetime))
    matches = matches.scalars().all()
    members = await db.execute(
        select(PoolMember)
        .where(PoolMember.pool_id == pool_id)
        .options(selectinload(PoolMember.user))
    )
    members = members.scalars().all()
    pending = await _build_pending_predictions(
        db,
        pool_id,
        matches,
        members,
        datetime.datetime.now(datetime.timezone.utc),
    )
    base_url = str(request.base_url).rstrip("/")
    return _pending_reminder_text(pool, pending["missing_by_member"], base_url)


@router.post("/pool/{pool_id}/settings")
async def update_pool_settings(
    request: Request,
    pool_id: int,
    show_predictions_before_deadline: str | None = Form(None),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await require_pool_owner(pool_id, user, db)
    pool.show_predictions_before_deadline = show_predictions_before_deadline == "1"
    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)


@router.post("/pool/{pool_id}/recalculate-points")
async def recalculate_pool_points(
    request: Request,
    pool_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await require_pool_owner(pool_id, user, db)
    matches_result = await db.execute(
        select(Match).where(
            Match.is_finished.is_(True),
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
        )
    )
    finished_matches = {match.id: match for match in matches_result.scalars().all()}
    if finished_matches:
        predictions = await db.execute(
            select(Prediction).where(
                Prediction.pool_id == pool_id,
                Prediction.match_id.in_(list(finished_matches.keys())),
            )
        )
        for prediction in predictions.scalars().all():
            match = finished_matches[prediction.match_id]
            prediction.points_awarded = calculate_points(
                prediction.predicted_home,
                prediction.predicted_away,
                match.home_score,
                match.away_score,
            )
    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)


@router.post("/match/{match_id}/retroactive")
async def toggle_retroactive(
    request: Request,
    match_id: int,
    pool_id: int = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await require_pool_owner(pool_id, user, db)
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(404)
    match.allow_retroactive = not match.allow_retroactive
    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)


@router.post("/pool/{pool_id}/member-prediction")
async def register_member_prediction(
    request: Request,
    pool_id: int,
    member_id: int = Form(...),
    match_id: int = Form(...),
    predicted_home: int = Form(...),
    predicted_away: int = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Owner registers a retroactive prediction on behalf of a member.

    Allowed even after the match is finished/synced (manual migration of an
    ongoing bolão). Points are computed immediately when the match is over.
    """
    await require_pool_owner(pool_id, user, db)

    membership = await db.execute(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == member_id
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(400, "Usuário não é membro deste bolão.")

    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Jogo não encontrado.")
    if predicted_home < 0 or predicted_away < 0:
        raise HTTPException(400, "Placar não pode ser negativo.")

    result = await db.execute(
        select(Prediction).where(
            Prediction.user_id == member_id,
            Prediction.pool_id == pool_id,
            Prediction.match_id == match_id,
        )
    )
    prediction = result.scalar_one_or_none()
    if prediction:
        prediction.predicted_home = predicted_home
        prediction.predicted_away = predicted_away
    else:
        prediction = Prediction(
            user_id=member_id,
            pool_id=pool_id,
            match_id=match_id,
            predicted_home=predicted_home,
            predicted_away=predicted_away,
        )
        db.add(prediction)

    if match.is_finished and match.home_score is not None:
        prediction.points_awarded = calculate_points(
            predicted_home, predicted_away, match.home_score, match.away_score
        )

    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)


@router.post("/match/{match_id}/teams")
async def update_teams(
    request: Request,
    match_id: int,
    pool_id: int = Form(...),
    home_team: str = Form(...),
    away_team: str = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await require_pool_owner(pool_id, user, db)
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(404)
    if match.is_finished:
        raise HTTPException(400, "Jogo já encerrado.")
    match.home_team = home_team.strip()
    match.away_team = away_team.strip()
    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)


@router.post("/match/{match_id}/result")
async def set_result(
    request: Request,
    match_id: int,
    pool_id: int = Form(...),
    home_score: int = Form(...),
    away_score: int = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await require_pool_owner(pool_id, user, db)
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(404)

    match.home_score = home_score
    match.away_score = away_score
    match.is_finished = True

    preds = await db.execute(
        select(Prediction).where(
            Prediction.match_id == match_id,
            Prediction.pool_id == pool_id,
        )
    )
    for pred in preds.scalars().all():
        pred.points_awarded = calculate_points(
            pred.predicted_home, pred.predicted_away,
            home_score, away_score,
        )

    await db.commit()
    return RedirectResponse(f"/admin/pool/{pool_id}", status_code=303)
