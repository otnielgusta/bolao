import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Pool, PoolMember, Prediction, Match
from app.routers.auth import require_user
from app.services.rules import PREDICTION_DEADLINE_SECONDS
from app.templating import create_templates

router = APIRouter(prefix="/pools", tags=["pools"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    memberships = await db.execute(
        select(PoolMember)
        .where(PoolMember.user_id == user.id)
        .options(selectinload(PoolMember.pool).selectinload(Pool.owner))
    )
    memberships = memberships.scalars().all()

    pool_scores = {}
    for m in memberships:
        result = await db.execute(
            select(func.coalesce(func.sum(Prediction.points_awarded), 0))
            .where(Prediction.pool_id == m.pool_id, Prediction.user_id == user.id)
        )
        pool_scores[m.pool_id] = result.scalar()

    return templates.TemplateResponse(request, "pools/dashboard.html", {
        "user": user,
        "memberships": memberships,
        "pool_scores": pool_scores,
    })


@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(request, "pools/create.html", {"user": user})


@router.post("/create")
async def create_pool(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = Pool(name=name, description=description, owner_id=user.id)
    db.add(pool)
    await db.flush()
    db.add(PoolMember(pool_id=pool.id, user_id=user.id))
    await db.commit()
    return RedirectResponse(f"/pools/{pool.id}", status_code=303)


@router.get("/{pool_id}", response_class=HTMLResponse)
async def pool_detail(
    request: Request,
    pool_id: int,
    tab: str = "matches",
    predictions_tab: str = "general",
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if tab == "my_predictions":
        tab = "predictions"
        predictions_tab = "mine"
    if tab == "predictions" and predictions_tab not in {"general", "mine"}:
        predictions_tab = "general"

    pool = await db.get(Pool, pool_id, options=[selectinload(Pool.owner)])
    if not pool:
        return RedirectResponse("/pools", status_code=303)

    membership = await db.execute(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == user.id
        )
    )
    if not membership.scalar_one_or_none():
        return RedirectResponse("/pools", status_code=303)

    matches = await db.execute(
        select(Match).order_by(Match.match_datetime)
    )
    matches = matches.scalars().all()

    user_predictions = {}
    preds = await db.execute(
        select(Prediction).where(
            Prediction.pool_id == pool_id, Prediction.user_id == user.id
        )
    )
    for p in preds.scalars().all():
        user_predictions[p.match_id] = p

    all_predictions_by_match = {}
    if tab in {"matches", "predictions"}:
        all_preds = await db.execute(
            select(Prediction)
            .where(Prediction.pool_id == pool_id)
            .options(selectinload(Prediction.user))
            .order_by(Prediction.match_id, Prediction.submitted_at)
        )
        for p in all_preds.scalars().all():
            all_predictions_by_match.setdefault(p.match_id, []).append(p)

    ranking = []
    if tab == "ranking":
        ranking = await _build_ranking(db, pool_id)

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    match_deadlines = {
        m.id: m.match_datetime.timestamp() - PREDICTION_DEADLINE_SECONDS
        for m in matches
    }

    return templates.TemplateResponse(request, "pools/detail.html", {
        "user": user,
        "pool": pool,
        "pool_id": pool_id,
        "matches": matches,
        "user_predictions": user_predictions,
        "all_predictions_by_match": all_predictions_by_match,
        "ranking": ranking,
        "tab": tab,
        "predictions_tab": predictions_tab,
        "is_owner": pool.owner_id == user.id,
        "now_timestamp": now_ts,
        "match_deadlines": match_deadlines,
        "prediction_deadline_seconds": PREDICTION_DEADLINE_SECONDS,
    })


@router.get("/{pool_id}/ranking_partial", response_class=HTMLResponse)
async def ranking_partial(
    request: Request,
    pool_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    ranking = await _build_ranking(db, pool_id)
    return templates.TemplateResponse(request, "pools/_ranking_table.html", {
        "ranking": ranking,
    })


async def _build_ranking(db: AsyncSession, pool_id: int):
    members = await db.execute(
        select(PoolMember)
        .where(PoolMember.pool_id == pool_id)
        .options(selectinload(PoolMember.user))
    )
    members = members.scalars().all()

    ranking = []
    for m in members:
        preds = await db.execute(
            select(Prediction).where(
                Prediction.pool_id == pool_id,
                Prediction.user_id == m.user_id,
                Prediction.points_awarded.isnot(None),
            )
        )
        preds = preds.scalars().all()

        total = sum(p.points_awarded for p in preds)
        counts = {10: 0, 7: 0, 5: 0, 3: 0, 1: 0, 0: 0}
        last_submitted = 0.0
        for p in preds:
            counts[p.points_awarded] = counts.get(p.points_awarded, 0) + 1
            last_submitted = max(last_submitted, p.submitted_at.timestamp())

        ranking.append({
            "display_name": m.user.display_name,
            "total": total,
            "counts": counts,
            "count_10": counts[10],
            "count_7": counts[7],
            "list_submitted_at": last_submitted if preds else float("inf"),
        })

    ranking.sort(key=lambda r: (-r["total"], -r["count_10"], -r["count_7"], r["list_submitted_at"]))

    for i, r in enumerate(ranking, 1):
        r["position"] = i

    return ranking
