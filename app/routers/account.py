from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PoolMember, User
from app.routers.auth import require_user
from app.templating import create_templates

router = APIRouter(prefix="/account", tags=["account"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def account_page(
    request: Request,
    saved: bool = False,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool_count = await db.execute(
        select(func.count(PoolMember.id)).where(PoolMember.user_id == user.id)
    )
    return templates.TemplateResponse(request, "account/settings.html", {
        "user": user,
        "pool_count": pool_count.scalar() or 0,
        "saved": saved,
    })


@router.post("/settings")
async def update_settings(
    request: Request,
    mirror_predictions: str | None = Form(None),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    user.mirror_predictions = mirror_predictions == "1"
    await db.commit()
    return RedirectResponse("/account?saved=1", status_code=303)
