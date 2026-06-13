"""
Manage global match data (shared by every pool) from the server shell.

Global match mutations are intentionally NOT available to web users: a match row
backs all bolões at once, so editing it changes everyone's championship. Use this
script (or the automatic sync_results.py job) instead.

Usage (run on the server):
    uv run python manage_matches.py list
    uv run python manage_matches.py result <match_id> <home_score> <away_score>
    uv run python manage_matches.py teams  <match_id> "<home_team>" "<away_team>"
    uv run python manage_matches.py retroactive <match_id> on|off

`result` finishes the match and scores predictions across ALL pools, the same way
the automatic sync does.
"""
import argparse
import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models import Match
from app.services.matches import set_result, set_teams, set_retroactive
from app.templating import local_strftime


async def _get_match(db, match_id: int) -> Match:
    match = await db.get(Match, match_id)
    if not match:
        raise SystemExit(f"Match {match_id} não encontrado.")
    return match


async def cmd_list(args) -> None:
    async with async_session() as db:
        result = await db.execute(select(Match).order_by(Match.match_datetime))
        for m in result.scalars().all():
            when = local_strftime(m.match_datetime, "%d/%m %H:%M")
            if m.is_finished:
                status = f"FIM {m.home_score}x{m.away_score}"
            else:
                status = "retro" if m.allow_retroactive else "aberto"
            print(f"#{m.id:>3} [{m.stage:>10}] {when} BRT  {m.home_team} x {m.away_team}  ({status})")


async def cmd_result(args) -> None:
    async with async_session() as db:
        match = await _get_match(db, args.match_id)
        scored = await set_result(db, match, args.home_score, args.away_score)
    print(
        f"Resultado: {match.home_team} {args.home_score} x {args.away_score} {match.away_team}. "
        f"Palpites pontuados (todos os bolões): {scored}."
    )


async def cmd_teams(args) -> None:
    async with async_session() as db:
        match = await _get_match(db, args.match_id)
        if match.is_finished:
            raise SystemExit("Jogo já encerrado; não é possível trocar os times.")
        await set_teams(db, match, args.home_team, args.away_team)
    print(f"Times atualizados: {args.home_team} x {args.away_team}.")


async def cmd_retroactive(args) -> None:
    value = args.state == "on"
    async with async_session() as db:
        match = await _get_match(db, args.match_id)
        await set_retroactive(db, match, value)
    print(f"Retroativo {'ativado' if value else 'desativado'} para o jogo #{args.match_id}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Lista todos os jogos com id e status.").set_defaults(func=cmd_list)

    p_result = sub.add_parser("result", help="Encerra o jogo e pontua todos os bolões.")
    p_result.add_argument("match_id", type=int)
    p_result.add_argument("home_score", type=int)
    p_result.add_argument("away_score", type=int)
    p_result.set_defaults(func=cmd_result)

    p_teams = sub.add_parser("teams", help="Atualiza os nomes dos times.")
    p_teams.add_argument("match_id", type=int)
    p_teams.add_argument("home_team")
    p_teams.add_argument("away_team")
    p_teams.set_defaults(func=cmd_teams)

    p_retro = sub.add_parser("retroactive", help="Liga/desliga palpite retroativo.")
    p_retro.add_argument("match_id", type=int)
    p_retro.add_argument("state", choices=["on", "off"])
    p_retro.set_defaults(func=cmd_retroactive)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
