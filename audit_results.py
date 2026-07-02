"""
Audit finished match results against football-data.org and fix selected rows.

Use this when the external API may have published a wrong score and the local
database needs a manual review.

Usage:
    uv run python audit_results.py --dry-run
    uv run python audit_results.py
"""
import argparse
import asyncio
from dataclasses import dataclass

import httpx

from app.config import settings
from app.database import async_session
from app.models import Match
from app.services.matches import recalculate_all_pools
from app.services.ranking import create_match_snapshots_for_all_pools
from app.services.sync import _find_local_match, fetch_api_matches
from app.templating import local_strftime

Score = tuple[int, int]

WINNER_LABELS = {
    "HOME_TEAM": "mandante",
    "AWAY_TEAM": "visitante",
    "DRAW": "empate",
}


@dataclass
class Finding:
    local: Match
    api_match: dict
    api_score: Score | None
    api_winner: str | None
    reasons: list[str]
    api_score_conflicts_winner: bool


@dataclass
class AuditSummary:
    api_finished: int
    matched: int
    unmatched: int
    findings: list[Finding]


def _api_full_time_score(api_match: dict) -> Score | None:
    score = api_match.get("score") or {}
    full_time = score.get("fullTime") or {}
    home = full_time.get("home")
    away = full_time.get("away")
    if home is None or away is None:
        return None
    return int(home), int(away)


def _api_winner(api_match: dict) -> str | None:
    winner = ((api_match.get("score") or {}).get("winner") or "").strip()
    return winner or None


def _winner_from_score(score: Score) -> str:
    home, away = score
    if home > away:
        return "HOME_TEAM"
    if away > home:
        return "AWAY_TEAM"
    return "DRAW"


def _format_score(score: Score | None) -> str:
    if score is None:
        return "-"
    return f"{score[0]}x{score[1]}"


def _local_score(match: Match) -> Score | None:
    if not match.is_finished or match.home_score is None or match.away_score is None:
        return None
    return match.home_score, match.away_score


def _format_match(match: Match) -> str:
    when = local_strftime(match.match_datetime, "%d/%m %H:%M")
    return (
        f"#{match.id} [{match.stage}] {when} BRT - "
        f"{match.home_team} x {match.away_team}"
    )


def _parse_score(value: str) -> Score | None:
    normalized = (
        value.strip()
        .lower()
        .replace("x", " ")
        .replace("-", " ")
        .replace(":", " ")
    )
    parts = normalized.split()
    if len(parts) != 2:
        return None
    try:
        home, away = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if home < 0 or away < 0:
        return None
    return home, away


async def audit_results() -> AuditSummary:
    api_matches = await fetch_api_matches()
    findings: list[Finding] = []
    api_finished = 0
    matched = 0
    unmatched = 0

    async with async_session() as db:
        for api_match in api_matches:
            if api_match.get("status") != "FINISHED":
                continue
            api_finished += 1
            local = await _find_local_match(db, api_match)
            if not local:
                unmatched += 1
                continue
            matched += 1

            api_score = _api_full_time_score(api_match)
            api_winner = _api_winner(api_match)
            local_score = _local_score(local)
            reasons: list[str] = []
            api_score_conflicts_winner = False

            if api_score is not None and local_score is None:
                reasons.append("API finalizou o jogo, mas o banco esta sem placar")
            elif api_score is not None and local_score != api_score:
                reasons.append("placar do banco difere do score.fullTime atual da API")

            if api_winner:
                if api_score is not None and _winner_from_score(api_score) != api_winner:
                    api_score_conflicts_winner = True
                    reasons.append("API inconsistente: winner nao bate com score.fullTime")
                if local_score is not None and _winner_from_score(local_score) != api_winner:
                    reasons.append("placar do banco contradiz o winner atual da API")

            if reasons:
                findings.append(
                    Finding(
                        local=local,
                        api_match=api_match,
                        api_score=api_score,
                        api_winner=api_winner,
                        reasons=reasons,
                        api_score_conflicts_winner=api_score_conflicts_winner,
                    )
                )

    return AuditSummary(
        api_finished=api_finished,
        matched=matched,
        unmatched=unmatched,
        findings=findings,
    )


def _print_finding(index: int, total: int, finding: Finding) -> None:
    local_score = _local_score(finding.local)
    api_winner = WINNER_LABELS.get(finding.api_winner or "", finding.api_winner or "-")
    print()
    print(f"[{index}/{total}] {_format_match(finding.local)}")
    print(f"Banco: {_format_score(local_score)}")
    print(f"API:   {_format_score(finding.api_score)} | winner: {api_winner}")
    print("Motivos:")
    for reason in finding.reasons:
        print(f"  - {reason}")


def _ask_action(finding: Finding) -> tuple[str, Score | None]:
    can_apply_api = finding.api_score is not None and not finding.api_score_conflicts_winner
    while True:
        if can_apply_api:
            prompt = "[a] aplicar API, [m] manual, [s] pular, [q] sair: "
        else:
            prompt = "[m] manual, [s] pular, [q] sair: "
        choice = input(prompt).strip().lower()
        if choice == "a" and can_apply_api:
            return "apply", finding.api_score
        if choice == "m":
            value = input("Placar correto (ex: 1 1 ou 1x1): ")
            score = _parse_score(value)
            if score is not None:
                return "manual", score
            print("Placar invalido.")
            continue
        if choice in {"s", ""}:
            return "skip", None
        if choice == "q":
            return "quit", None
        print("Opcao invalida.")


async def _apply_result(match: Match, score: Score) -> int:
    async with async_session() as db:
        fresh = await db.get(Match, match.id)
        if not fresh:
            raise SystemExit(f"Jogo #{match.id} nao encontrado.")
        fresh.home_score, fresh.away_score = score
        fresh.is_finished = True
        scored = await recalculate_all_pools(db, fresh)
        await create_match_snapshots_for_all_pools(db, fresh)
        await db.commit()
        return scored


async def run(args: argparse.Namespace) -> None:
    if not settings.football_data_token:
        raise SystemExit("FOOTBALL_DATA_TOKEN nao configurado.")

    summary = await audit_results()
    print(
        f"Jogos finalizados na API: {summary.api_finished} | "
        f"vinculados no banco: {summary.matched} | "
        f"sem match local: {summary.unmatched}"
    )

    if not summary.findings:
        print("Nenhuma divergencia encontrada.")
        return

    print(f"Divergencias/suspeitas encontradas: {len(summary.findings)}")
    if args.dry_run:
        for index, finding in enumerate(summary.findings, 1):
            _print_finding(index, len(summary.findings), finding)
        print()
        print("DRY RUN - nada foi alterado.")
        return

    applied = 0
    skipped = 0
    for index, finding in enumerate(summary.findings, 1):
        _print_finding(index, len(summary.findings), finding)
        action, score = _ask_action(finding)
        if action == "quit":
            break
        if action == "skip" or score is None:
            skipped += 1
            continue

        scored = await _apply_result(finding.local, score)
        applied += 1
        print(
            f"Corrigido para {_format_score(score)}. "
            f"Palpites recalculados em todos os boloes: {scored}."
        )

    print()
    print(f"Concluido. Corrigidos: {applied}. Pulados: {skipped}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lista divergencias; nao pergunta nem grava correcoes.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(run(args))
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"Erro na API football-data.org: HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise SystemExit(f"Erro ao consultar football-data.org: {exc}") from exc
    except OSError as exc:
        raise SystemExit(
            "Falha de conexao. Verifique internet, banco e variaveis de ambiente."
        ) from exc


if __name__ == "__main__":
    main()
