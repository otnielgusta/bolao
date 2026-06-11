import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.database import async_session
from app.routers import auth, pools, matches, predictions, admin, invite
from app.routers.auth import NotAuthenticatedError
from app.services.autosync import auto_sync_loop
from app.services.sync import sync_results

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_task = asyncio.create_task(auto_sync_loop())
    yield
    sync_task.cancel()


app = FastAPI(title="Bolão Copa 2026", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(pools.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.include_router(invite.router)


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError):
    return RedirectResponse("/auth/login", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse("/pools", status_code=303)


@app.api_route("/internal/sync", methods=["GET", "POST"])
async def internal_sync(token: str):
    """Site-admin only: forces an immediate sync. Protected by ADMIN_TOKEN."""
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(403, "Token inválido.")
    async with async_session() as db:
        summary = await sync_results(db)
    return JSONResponse(summary)


if __name__ == "__main__":
    import uvicorn

    # Reload is disabled here on purpose: the reloader spawns a subprocess,
    # which breaks IDE debugger breakpoints.
    uvicorn.run(app, host="0.0.0.0", port=8000)
