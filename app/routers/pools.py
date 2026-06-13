import datetime
from collections.abc import Sequence

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Pool, PoolMember, Prediction, Match
from app.routers.auth import require_user
from app.services.scoring import calculate_points
from app.services.rules import PREDICTION_DEADLINE_SECONDS
from app.templating import APP_TIMEZONE, create_templates, local_datetime, local_strftime

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
    ranking_date: str | None = None,
    ranking_stage: str | None = None,
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

    now = datetime.datetime.now(datetime.timezone.utc)
    now_ts = now.timestamp()
    today_local_date = local_datetime(now).date().isoformat()
    match_deadlines = {
        m.id: m.match_datetime.timestamp() - PREDICTION_DEADLINE_SECONDS
        for m in matches
    }
    match_local_dates = {
        m.id: local_datetime(m.match_datetime).date().isoformat()
        for m in matches
    }
    prediction_release_labels = {
        m.id: local_strftime(
            datetime.datetime.fromtimestamp(
                match_deadlines[m.id],
                datetime.timezone.utc,
            ),
            "%d/%m %H:%M",
        )
        for m in matches
    }

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

    predictions_visible_by_match = {
        match.id: _can_view_match_predictions(pool, match, now)
        for match in matches
    }
    open_missing_count = 0
    today_missing_count = 0
    open_count = 0
    finished_count = 0
    for match in matches:
        can_predict = _can_predict(match, now)
        if can_predict:
            open_count += 1
        if match.is_finished:
            finished_count += 1
        if can_predict and match.id not in user_predictions:
            open_missing_count += 1
            if match_local_dates[match.id] == today_local_date:
                today_missing_count += 1

    ranking = []
    ranking_label = "Classificação geral"
    ranking_days = _finished_match_days(matches)
    ranking_stages = _finished_match_stages(matches)
    ranking_user_summary = None
    if tab == "ranking":
        ranking_match_ids = None
        if ranking_date:
            ranking_match_ids = [
                match.id
                for match in matches
                if match.is_finished and match_local_dates[match.id] == ranking_date
            ]
            ranking_label = f"Classificação de {_format_local_date_label(ranking_date)}"
            ranking_stage = None
        elif ranking_stage:
            ranking_match_ids = [
                match.id
                for match in matches
                if match.is_finished and match.stage == ranking_stage
            ]
            ranking_label = f"Classificação - {ranking_stage}"
        ranking = await _build_ranking(db, pool_id, ranking_match_ids)
        previous_positions = None
        if not ranking_date and not ranking_stage:
            previous_positions = await _previous_positions_before_latest_match(
                db, pool_id, matches
            )
        _decorate_ranking(ranking, user.id, previous_positions)
        ranking_user_summary = _ranking_user_summary(ranking, user.id)

    return templates.TemplateResponse(request, "pools/detail.html", {
        "user": user,
        "pool": pool,
        "pool_id": pool_id,
        "matches": matches,
        "user_predictions": user_predictions,
        "all_predictions_by_match": all_predictions_by_match,
        "ranking": ranking,
        "ranking_date": ranking_date,
        "ranking_stage": ranking_stage,
        "ranking_days": ranking_days,
        "ranking_stages": ranking_stages,
        "ranking_label": ranking_label,
        "ranking_user_summary": ranking_user_summary,
        "tab": tab,
        "predictions_tab": predictions_tab,
        "is_owner": pool.owner_id == user.id,
        "now_timestamp": now_ts,
        "match_deadlines": match_deadlines,
        "match_local_dates": match_local_dates,
        "predictions_visible_by_match": predictions_visible_by_match,
        "prediction_release_labels": prediction_release_labels,
        "today_local_date": today_local_date,
        "prediction_deadline_seconds": PREDICTION_DEADLINE_SECONDS,
        "open_missing_count": open_missing_count,
        "today_missing_count": today_missing_count,
        "open_count": open_count,
        "finished_count": finished_count,
    })


@router.get("/{pool_id}/ranking_partial", response_class=HTMLResponse)
async def ranking_partial(
    request: Request,
    pool_id: int,
    ranking_date: str | None = None,
    ranking_stage: str | None = None,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_member_pool_or_404(db, pool_id, user)
    ranking_match_ids = None
    previous_positions = None
    if ranking_date or ranking_stage:
        matches = await db.execute(select(Match).where(Match.is_finished.is_(True)))
        finished_matches = matches.scalars().all()
    if ranking_date:
        ranking_match_ids = [
            match.id
            for match in finished_matches
            if local_datetime(match.match_datetime).date().isoformat() == ranking_date
        ]
    elif ranking_stage:
        ranking_match_ids = [
            match.id
            for match in finished_matches
            if match.stage == ranking_stage
        ]
    else:
        matches = await db.execute(select(Match).order_by(Match.match_datetime))
        previous_positions = await _previous_positions_before_latest_match(
            db,
            pool_id,
            matches.scalars().all(),
        )
    ranking = await _build_ranking(db, pool_id, ranking_match_ids)
    _decorate_ranking(ranking, user.id, previous_positions)
    return templates.TemplateResponse(request, "pools/_ranking_table.html", {
        "ranking": ranking,
        "user": user,
    })


@router.get("/{pool_id}/ranking_copy", response_class=PlainTextResponse)
async def ranking_copy(
    pool_id: int,
    ranking_date: str | None = None,
    ranking_stage: str | None = None,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await _get_member_pool_or_404(db, pool_id, user)
    ranking_match_ids = None
    label = "geral"
    if ranking_date or ranking_stage:
        matches = await db.execute(select(Match).where(Match.is_finished.is_(True)))
        finished_matches = matches.scalars().all()
    if ranking_date:
        ranking_match_ids = [
            match.id
            for match in finished_matches
            if local_datetime(match.match_datetime).date().isoformat() == ranking_date
        ]
        label = _format_local_date_label(ranking_date)
    elif ranking_stage:
        ranking_match_ids = [
            match.id
            for match in finished_matches
            if match.stage == ranking_stage
        ]
        label = ranking_stage
    ranking = await _build_ranking(db, pool_id, ranking_match_ids)
    return _ranking_copy_text(pool, ranking, label)


@router.get(
    "/{pool_id}/matches/{match_id}/predictions_copy",
    response_class=PlainTextResponse,
)
async def match_predictions_copy(
    pool_id: int,
    match_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await _get_member_pool_or_404(db, pool_id, user)
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Jogo nao encontrado.")

    preds = await db.execute(
        select(Prediction)
        .where(Prediction.pool_id == pool_id, Prediction.match_id == match_id)
        .options(selectinload(Prediction.user))
        .order_by(Prediction.submitted_at, Prediction.id)
    )
    predictions = preds.scalars().all()

    now = datetime.datetime.now(datetime.timezone.utc)
    return _match_predictions_copy_text(
        pool,
        match,
        predictions,
        visible=_can_view_match_predictions(pool, match, now),
    )


@router.get("/{pool_id}/days/{day}/summary_copy", response_class=PlainTextResponse)
async def day_summary_copy(
    pool_id: int,
    day: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pool = await _get_member_pool_or_404(db, pool_id, user)
    try:
        local_day = datetime.date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(400, "Data inválida.") from exc

    matches_result = await db.execute(select(Match).order_by(Match.match_datetime))
    matches = matches_result.scalars().all()
    day_matches = [
        match
        for match in matches
        if local_datetime(match.match_datetime).date() == local_day
    ]
    finished_day_match_ids = [
        match.id for match in day_matches if match.is_finished
    ]

    day_ranking = await _build_ranking(db, pool_id, finished_day_match_ids)
    current_ranking = await _build_ranking(db, pool_id)
    before_ids, after_ids = _match_ids_before_and_after_day(matches, local_day)
    before_ranking = await _build_ranking(db, pool_id, before_ids)
    after_ranking = await _build_ranking(db, pool_id, after_ids)

    return _day_summary_copy_text(
        pool=pool,
        local_day=local_day,
        day_matches=day_matches,
        day_ranking=day_ranking,
        current_ranking=current_ranking,
        before_ranking=before_ranking,
        after_ranking=after_ranking,
    )


async def _get_member_pool_or_404(db: AsyncSession, pool_id: int, user: User) -> Pool:
    pool = await db.get(Pool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="Bolao nao encontrado.")

    membership = await db.execute(
        select(PoolMember.id).where(
            PoolMember.pool_id == pool_id,
            PoolMember.user_id == user.id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Bolao nao encontrado.")

    return pool


def _format_brt(value: datetime.datetime | None) -> str:
    formatted = local_strftime(value, "%d/%m/%Y %H:%M")
    return f"{formatted} BRT" if formatted else ""


def _format_local_date_label(value: str) -> str:
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%d/%m/%Y")


def _prediction_deadline(match: Match) -> datetime.datetime:
    return match.match_datetime - datetime.timedelta(
        seconds=PREDICTION_DEADLINE_SECONDS
    )


def _can_predict(match: Match, now: datetime.datetime) -> bool:
    return (
        not match.is_finished
        and (now <= _prediction_deadline(match) or match.allow_retroactive)
    )


def _can_view_match_predictions(
    pool: Pool,
    match: Match,
    now: datetime.datetime,
) -> bool:
    return (
        pool.show_predictions_before_deadline
        or now >= _prediction_deadline(match)
        or match.is_finished
    )


def _finished_match_days(matches: Sequence[Match]) -> list[dict[str, str]]:
    days: dict[str, str] = {}
    for match in matches:
        if not match.is_finished:
            continue
        local_day = local_datetime(match.match_datetime).date()
        value = local_day.isoformat()
        days[value] = local_day.strftime("%d/%m")
    return [{"value": value, "label": label} for value, label in days.items()]


def _finished_match_stages(matches: Sequence[Match]) -> list[str]:
    stages = []
    seen = set()
    for match in matches:
        if not match.is_finished or match.stage in seen:
            continue
        seen.add(match.stage)
        stages.append(match.stage)
    return stages


def _ranking_copy_text(pool: Pool, ranking: list[dict], label: str = "geral") -> str:
    lines = [
        f"Classificacao {label} - Bolao {pool.name}",
        "",
    ]
    if not ranking:
        lines.append("Nenhum palpite pontuado ainda.")
        return "\n".join(lines)

    for r in ranking:
        lines.append(
            f"{r['position']}. {r['display_name']} - {r['total']} pts "
            f"(10:{r['counts'][10]} 7:{r['counts'][7]} 5:{r['counts'][5]} "
            f"3:{r['counts'][3]} 1:{r['counts'][1]} 0:{r['counts'][0]})"
        )

    return "\n".join(lines)


def _match_predictions_copy_text(
    pool: Pool,
    match: Match,
    predictions: list[Prediction],
    visible: bool = True,
) -> str:
    if match.is_finished:
        lines = [
            f"Resultado saiu - Bolao {pool.name}",
            match.stage,
            f"{match.home_team} {match.home_score} x {match.away_score} {match.away_team}",
            "",
        ]
    else:
        lines = [
            f"Palpites - Bolao {pool.name}",
            match.stage,
            f"{match.home_team} x {match.away_team}",
            _format_brt(match.match_datetime),
            "",
        ]

    if not visible:
        lines.append(
            "Os palpites deste jogo estao ocultos ate o prazo fechar."
        )
        return "\n".join(lines)

    if not predictions:
        lines.append("Nenhum palpite feito para este jogo.")
        return "\n".join(lines)

    for pred in predictions:
        line = (
            f"{pred.user.display_name}: "
            f"{pred.predicted_home} x {pred.predicted_away}"
        )
        points = _points_for_finished_match(match, pred)
        if points is not None:
            line = f"{line} (+{points} pts)"
        lines.append(line)

    return "\n".join(lines)


def _day_summary_copy_text(
    pool: Pool,
    local_day: datetime.date,
    day_matches: Sequence[Match],
    day_ranking: list[dict],
    current_ranking: list[dict],
    before_ranking: list[dict],
    after_ranking: list[dict],
) -> str:
    label = local_day.strftime("%d/%m/%Y")
    lines = [f"Resumo do dia {label} - Bolao {pool.name}", ""]

    finished_matches = [match for match in day_matches if match.is_finished]
    if finished_matches:
        lines.append("Resultados:")
        for match in finished_matches:
            lines.append(
                f"- {match.home_team} {match.home_score} x {match.away_score} {match.away_team}"
            )
        lines.append("")
    else:
        lines.append("Nenhum jogo finalizado neste dia ainda.")
        return "\n".join(lines)

    positive_day_ranking = [row for row in day_ranking if row["total"] > 0]
    if positive_day_ranking:
        lines.append("Top do dia:")
        for row in positive_day_ranking[:3]:
            lines.append(
                f"{row['position']}. {row['display_name']} - {row['total']} pts"
            )
        best_score = positive_day_ranking[0]["total"]
        best_names = [
            row["display_name"]
            for row in positive_day_ranking
            if row["total"] == best_score
        ]
        lines.append(
            f"Maior pontuacao do dia: {', '.join(best_names)} ({best_score} pts)"
        )
    else:
        lines.append("Ninguem pontuou nos jogos finalizados deste dia.")

    climb = _biggest_climb(before_ranking, after_ranking)
    if climb:
        lines.append(
            f"Maior subida: {climb['display_name']} subiu {climb['delta']} posicao(oes)."
        )
    else:
        lines.append("Maior subida: sem mudanca de posicao relevante.")

    if current_ranking:
        lines.append("")
        lines.append("Top 3 geral:")
        for row in current_ranking[:3]:
            lines.append(
                f"{row['position']}. {row['display_name']} - {row['total']} pts"
            )

    return "\n".join(lines)


def _biggest_climb(
    before_ranking: Sequence[dict],
    after_ranking: Sequence[dict],
) -> dict | None:
    before_positions = {row["user_id"]: row["position"] for row in before_ranking}
    best: dict | None = None
    for row in after_ranking:
        previous_position = before_positions.get(row["user_id"])
        if previous_position is None:
            continue
        delta = previous_position - row["position"]
        if delta <= 0:
            continue
        if best is None or delta > best["delta"]:
            best = {"display_name": row["display_name"], "delta": delta}
    return best


def _match_ids_before_and_after_day(
    matches: Sequence[Match],
    local_day: datetime.date,
) -> tuple[list[int], list[int]]:
    start = datetime.datetime.combine(
        local_day,
        datetime.time.min,
        tzinfo=APP_TIMEZONE,
    ).astimezone(datetime.timezone.utc)
    end = start + datetime.timedelta(days=1)
    before_ids = [
        match.id
        for match in matches
        if match.is_finished and match.match_datetime < start
    ]
    after_ids = [
        match.id
        for match in matches
        if match.is_finished and match.match_datetime < end
    ]
    return before_ids, after_ids


def _points_for_finished_match(match: Match, pred: Prediction) -> int | None:
    if not match.is_finished:
        return None
    if pred.points_awarded is not None:
        return pred.points_awarded
    if match.home_score is None or match.away_score is None:
        return None
    return calculate_points(
        pred.predicted_home,
        pred.predicted_away,
        match.home_score,
        match.away_score,
    )


async def _previous_positions_before_latest_match(
    db: AsyncSession,
    pool_id: int,
    matches: Sequence[Match],
) -> dict[int, int] | None:
    finished_matches = [match for match in matches if match.is_finished]
    if not finished_matches:
        return None
    latest_match_datetime = max(match.match_datetime for match in finished_matches)
    previous_match_ids = [
        match.id
        for match in finished_matches
        if match.match_datetime < latest_match_datetime
    ]
    previous_ranking = await _build_ranking(db, pool_id, previous_match_ids)
    return {row["user_id"]: row["position"] for row in previous_ranking}


def _decorate_ranking(
    ranking: list[dict],
    current_user_id: int,
    previous_positions: dict[int, int] | None = None,
) -> None:
    for index, row in enumerate(ranking):
        row["is_current_user"] = row["user_id"] == current_user_id
        previous_position = None
        if previous_positions is not None:
            previous_position = previous_positions.get(row["user_id"])
        row["position_delta"] = (
            0 if previous_position is None else previous_position - row["position"]
        )
        if index == 0:
            row["points_to_pass"] = None
            row["next_display_name"] = None
            continue
        next_row = ranking[index - 1]
        row["points_to_pass"] = max(next_row["total"] - row["total"] + 1, 1)
        row["next_display_name"] = next_row["display_name"]


def _ranking_user_summary(ranking: Sequence[dict], user_id: int) -> dict | None:
    for row in ranking:
        if row["user_id"] == user_id:
            return row
    return None


async def _build_ranking(
    db: AsyncSession,
    pool_id: int,
    match_ids: Sequence[int] | None = None,
):
    members = await db.execute(
        select(PoolMember)
        .where(PoolMember.pool_id == pool_id)
        .options(selectinload(PoolMember.user))
    )
    members = members.scalars().all()

    ranking = []
    for m in members:
        if match_ids is not None and not match_ids:
            preds = []
        else:
            query = select(Prediction).where(
                Prediction.pool_id == pool_id,
                Prediction.user_id == m.user_id,
                Prediction.points_awarded.isnot(None),
            )
            if match_ids is not None:
                query = query.where(Prediction.match_id.in_(list(match_ids)))
            preds_result = await db.execute(query)
            preds = preds_result.scalars().all()

        total = sum(p.points_awarded for p in preds)
        counts = {10: 0, 7: 0, 5: 0, 3: 0, 1: 0, 0: 0}
        last_submitted = 0.0
        for p in preds:
            counts[p.points_awarded] = counts.get(p.points_awarded, 0) + 1
            last_submitted = max(last_submitted, p.submitted_at.timestamp())

        ranking.append({
            "user_id": m.user_id,
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
