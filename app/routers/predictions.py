import datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Match, Prediction, PoolMember, Pool
from app.routers.auth import require_user
from app.services.rules import PREDICTION_DEADLINE_MINUTES

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("")
async def create_or_update(
    request: Request,
    pool_id: int = Form(...),
    match_id: int = Form(...),
    predicted_home: int = Form(...),
    predicted_away: int = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await db.execute(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == user.id
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(400, "Você não é membro deste bolão.")

    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Jogo não encontrado.")

    if match.is_finished:
        raise HTTPException(
            400,
            "Jogo já encerrado. Peça ao dono do bolão para registrar seu palpite retroativo.",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    deadline = match.match_datetime - datetime.timedelta(minutes=PREDICTION_DEADLINE_MINUTES)

    if now > deadline:
        if not match.allow_retroactive:
            raise HTTPException(400, "Prazo para palpite encerrado.")

    if predicted_home < 0 or predicted_away < 0:
        raise HTTPException(400, "Placar não pode ser negativo.")

    result = await db.execute(
        select(Prediction).where(
            Prediction.user_id == user.id,
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
        prediction = Prediction(
            user_id=user.id,
            pool_id=pool_id,
            match_id=match_id,
            predicted_home=predicted_home,
            predicted_away=predicted_away,
            submitted_at=now,
        )
        db.add(prediction)

    await db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"ok": True, "message": "Palpite salvo!"})
    return RedirectResponse(f"/pools/{pool_id}?tab=matches", status_code=303)


@router.post("/bulk")
async def bulk_create_or_update(
    request: Request,
    pool_id: int = Form(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await db.execute(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == user.id
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(400, "Voce nao e membro deste bolao.")

    form = await request.form()
    match_ids = set()
    for key in form.keys():
        if key.startswith("home_"):
            try:
                match_ids.add(int(key.removeprefix("home_")))
            except ValueError:
                continue

    if not match_ids:
        return RedirectResponse(f"/pools/{pool_id}?tab=quick", status_code=303)

    matches_result = await db.execute(select(Match).where(Match.id.in_(match_ids)))
    matches = {match.id: match for match in matches_result.scalars().all()}

    predictions_result = await db.execute(
        select(Prediction).where(
            Prediction.user_id == user.id,
            Prediction.pool_id == pool_id,
            Prediction.match_id.in_(match_ids),
        )
    )
    predictions = {
        prediction.match_id: prediction
        for prediction in predictions_result.scalars().all()
    }

    now = datetime.datetime.now(datetime.timezone.utc)
    for match_id in sorted(match_ids):
        match = matches.get(match_id)
        if not match or match.is_finished:
            continue

        home_raw = str(form.get(f"home_{match_id}", "")).strip()
        away_raw = str(form.get(f"away_{match_id}", "")).strip()
        if home_raw == "" and away_raw == "":
            continue
        if home_raw == "" or away_raw == "":
            raise HTTPException(400, "Preencha os dois placares do jogo.")

        try:
            predicted_home = int(home_raw)
            predicted_away = int(away_raw)
        except ValueError as exc:
            raise HTTPException(400, "Placar invalido.") from exc

        if predicted_home < 0 or predicted_away < 0:
            raise HTTPException(400, "Placar nao pode ser negativo.")

        deadline = match.match_datetime - datetime.timedelta(
            minutes=PREDICTION_DEADLINE_MINUTES
        )
        if now > deadline and not match.allow_retroactive:
            continue

        prediction = predictions.get(match_id)
        if prediction:
            prediction.predicted_home = predicted_home
            prediction.predicted_away = predicted_away
            prediction.submitted_at = now
        else:
            db.add(
                Prediction(
                    user_id=user.id,
                    pool_id=pool_id,
                    match_id=match_id,
                    predicted_home=predicted_home,
                    predicted_away=predicted_away,
                    submitted_at=now,
                )
            )

    await db.commit()
    return RedirectResponse(f"/pools/{pool_id}?tab=quick", status_code=303)
