from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Pool, PoolMember, Match, Prediction
from app.routers.auth import require_user
from app.services.scoring import calculate_points

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


async def require_pool_owner(pool_id: int, user: User, db: AsyncSession) -> Pool:
    pool = await db.get(Pool, pool_id)
    if not pool or pool.owner_id != user.id:
        raise HTTPException(403, "Acesso negado.")
    return pool


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
    return templates.TemplateResponse(request, "admin/panel.html", {
        "user": user,
        "pool": pool,
        "matches": matches,
        "members": members,
    })


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
