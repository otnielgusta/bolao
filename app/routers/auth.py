from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt as _bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.services.ratelimit import allow, client_ip
from app.templating import create_templates

router = APIRouter(prefix="/auth", tags=["auth"])
templates = create_templates()
# Timed serializer: tokens carry an issue timestamp and expire on load. The
# embedded token_version lets a logout invalidate every session for the user.
serializer = URLSafeTimedSerializer(settings.secret_key)


def _safe_redirect(target: str | None) -> str:
    """Only allow same-site relative paths to avoid open-redirect phishing."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/pools"


def set_session_cookie(response, user: User):
    token = serializer.dumps({"user_id": user.id, "v": user.token_version})
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
    )


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return None
    try:
        data = serializer.loads(cookie, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired, Exception):
        return None
    result = await db.execute(select(User).where(User.id == data.get("user_id")))
    user = result.scalar_one_or_none()
    if user is None or data.get("v") != user.token_version:
        return None
    return user


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
    if not allow(f"register:{client_ip(request)}", limit=5, window_seconds=3600):
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"error": "Muitas tentativas. Tente novamente mais tarde."},
            status_code=429,
        )
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        # Generic message: don't confirm which emails already have an account.
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"error": "Não foi possível concluir o cadastro com esses dados."},
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

    redirect_to = _safe_redirect(request.cookies.get("redirect_after_login"))
    response = RedirectResponse(redirect_to, status_code=303)
    set_session_cookie(response, user)
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
    # Throttle by IP and by target email to blunt credential brute force.
    if not allow(f"login:{client_ip(request)}", limit=10, window_seconds=300) or not allow(
        f"login:{email.lower()}", limit=10, window_seconds=300
    ):
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Muitas tentativas. Aguarde alguns minutos."},
            status_code=429,
        )
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not _bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Email ou senha incorretos."},
            status_code=400,
        )

    redirect_to = _safe_redirect(request.cookies.get("redirect_after_login"))
    response = RedirectResponse(redirect_to, status_code=303)
    set_session_cookie(response, user)
    response.delete_cookie("redirect_after_login")
    return response


@router.post("/logout")
async def logout(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    # Bump token_version to revoke every issued session, then drop the cookie.
    user.token_version += 1
    await db.commit()
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
