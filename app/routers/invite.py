from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Pool, PoolMember
from app.routers.auth import get_current_user

router = APIRouter(tags=["invite"])


@router.get("/join/{invite_code}")
async def join_pool(
    request: Request,
    invite_code: str,
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)

    result = await db.execute(select(Pool).where(Pool.invite_code == invite_code))
    pool = result.scalar_one_or_none()
    if not pool:
        return RedirectResponse("/pools", status_code=303)

    if not user:
        response = RedirectResponse("/auth/login", status_code=303)
        response.set_cookie("redirect_after_login", f"/join/{invite_code}", max_age=600)
        return response

    existing = await db.execute(
        select(PoolMember).where(
            PoolMember.pool_id == pool.id, PoolMember.user_id == user.id
        )
    )
    if not existing.scalar_one_or_none():
        db.add(PoolMember(pool_id=pool.id, user_id=user.id))
        await db.commit()

    return RedirectResponse(f"/pools/{pool.id}", status_code=303)
