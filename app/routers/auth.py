from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt as _bcrypt
from itsdangerous import URLSafeSerializer

from app.database import get_db
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
serializer = URLSafeSerializer(settings.secret_key)


def set_session_cookie(response, user_id: int):
    token = serializer.dumps({"user_id": user_id})
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return None
    try:
        data = serializer.loads(cookie)
    except Exception:
        return None
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    return result.scalar_one_or_none()


class NotAuthenticatedError(Exception):
    pass


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await get_current_user(request, db)
    if not user:
        raise NotAuthenticatedError()
    return user


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html")


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"error": "Email já cadastrado."},
            status_code=400,
        )
    user = User(
        email=email,
        display_name=display_name,
        hashed_password=_bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    redirect_to = request.cookies.get("redirect_after_login", "/pools")
    response = RedirectResponse(redirect_to, status_code=303)
    set_session_cookie(response, user.id)
    response.delete_cookie("redirect_after_login")
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not _bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Email ou senha incorretos."},
            status_code=400,
        )

    redirect_to = request.cookies.get("redirect_after_login", "/pools")
    response = RedirectResponse(redirect_to, status_code=303)
    set_session_cookie(response, user.id)
    response.delete_cookie("redirect_after_login")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
