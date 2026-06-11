from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Match, Prediction
from app.routers.auth import require_user
from app.templating import create_templates

router = APIRouter(prefix="/matches", tags=["matches"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def list_matches(
    request: Request,
    pool_id: int | None = None,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    matches = await db.execute(select(Match).order_by(Match.match_datetime))
    matches = matches.scalars().all()

    user_predictions = {}
    if pool_id:
        preds = await db.execute(
            select(Prediction).where(
                Prediction.pool_id == pool_id, Prediction.user_id == user.id
            )
        )
        for p in preds.scalars().all():
            user_predictions[p.match_id] = p

    return templates.TemplateResponse(request, "matches/list.html", {
        "user": user,
        "matches": matches,
        "user_predictions": user_predictions,
        "pool_id": pool_id,
    })
