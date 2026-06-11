"""
Seed script: populates the database with the real FIFA World Cup 2026 schedule
(official draw of December 5, 2025).

Run: uv run python seed.py            # seeds only if empty
     uv run python seed.py --force    # wipes matches + predictions and reseeds
"""
import asyncio
import datetime as dt
import sys

from sqlalchemy import select, delete

from app.database import engine, async_session
from app.models.user import Base
from app.models.match import Match
from app.models.prediction import Prediction

UTC = dt.timezone.utc

from app.services.teams import TEAMS


def d(month: int, day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=UTC)


# Official group stage schedule (kickoffs converted from ET to UTC).
# (group, datetime_utc, home, away)
GROUP_MATCHES = [
    # Matchday June 11
    ("Grupo A", d(6, 11, 18), "MEX", "RSA"),
    ("Grupo A", d(6, 12, 2), "KOR", "CZE"),
    # June 12
    ("Grupo B", d(6, 12, 19), "CAN", "BIH"),
    ("Grupo D", d(6, 13, 1), "USA", "PAR"),
    # June 13
    ("Grupo B", d(6, 13, 19), "QAT", "SUI"),
    ("Grupo C", d(6, 13, 22), "BRA", "MAR"),
    ("Grupo C", d(6, 14, 1), "HAI", "SCO"),
    ("Grupo D", d(6, 14, 4), "AUS", "TUR"),
    # June 14
    ("Grupo E", d(6, 14, 17), "GER", "CUW"),
    ("Grupo F", d(6, 14, 20), "NED", "JPN"),
    ("Grupo E", d(6, 14, 23), "CIV", "ECU"),
    ("Grupo F", d(6, 15, 2), "SWE", "TUN"),
    # June 15
    ("Grupo H", d(6, 15, 17), "ESP", "CPV"),
    ("Grupo G", d(6, 15, 22), "BEL", "EGY"),
    ("Grupo H", d(6, 15, 22), "KSA", "URY"),
    ("Grupo G", d(6, 16, 4), "IRN", "NZL"),
    # June 16
    ("Grupo I", d(6, 16, 19), "FRA", "SEN"),
    ("Grupo I", d(6, 16, 22), "IRQ", "NOR"),
    ("Grupo J", d(6, 17, 1), "ARG", "ALG"),
    ("Grupo J", d(6, 17, 4), "AUT", "JOR"),
    # June 17
    ("Grupo K", d(6, 17, 17), "POR", "COD"),
    ("Grupo L", d(6, 17, 20), "ENG", "CRO"),
    ("Grupo L", d(6, 17, 23), "GHA", "PAN"),
    ("Grupo K", d(6, 18, 2), "UZB", "COL"),
    # June 18
    ("Grupo A", d(6, 18, 16), "CZE", "RSA"),
    ("Grupo B", d(6, 18, 19), "SUI", "BIH"),
    ("Grupo B", d(6, 18, 22), "CAN", "QAT"),
    ("Grupo A", d(6, 19, 3), "MEX", "KOR"),
    # June 19
    ("Grupo D", d(6, 19, 19), "USA", "AUS"),
    ("Grupo C", d(6, 19, 22), "SCO", "MAR"),
    ("Grupo C", d(6, 20, 1), "BRA", "HAI"),
    ("Grupo D", d(6, 20, 4), "TUR", "PAR"),
    # June 20
    ("Grupo F", d(6, 20, 17), "NED", "SWE"),
    ("Grupo E", d(6, 20, 20), "GER", "CIV"),
    ("Grupo E", d(6, 21, 0), "ECU", "CUW"),
    ("Grupo F", d(6, 21, 4), "TUN", "JPN"),
    # June 21
    ("Grupo H", d(6, 21, 16), "ESP", "KSA"),
    ("Grupo G", d(6, 21, 19), "BEL", "IRN"),
    ("Grupo H", d(6, 21, 22), "URY", "CPV"),
    ("Grupo G", d(6, 22, 1), "NZL", "EGY"),
    # June 22
    ("Grupo J", d(6, 22, 17), "ARG", "AUT"),
    ("Grupo I", d(6, 22, 21), "FRA", "IRQ"),
    ("Grupo I", d(6, 23, 0), "NOR", "SEN"),
    ("Grupo J", d(6, 23, 3), "JOR", "ALG"),
    # June 23
    ("Grupo K", d(6, 23, 17), "POR", "UZB"),
    ("Grupo L", d(6, 23, 20), "ENG", "GHA"),
    ("Grupo L", d(6, 23, 23), "PAN", "CRO"),
    ("Grupo K", d(6, 24, 2), "COL", "COD"),
    # June 24 — final round groups A/B/C (simultaneous)
    ("Grupo B", d(6, 24, 19), "SUI", "CAN"),
    ("Grupo B", d(6, 24, 19), "BIH", "QAT"),
    ("Grupo C", d(6, 24, 22), "SCO", "BRA"),
    ("Grupo C", d(6, 24, 22), "MAR", "HAI"),
    ("Grupo A", d(6, 25, 1), "CZE", "MEX"),
    ("Grupo A", d(6, 25, 1), "RSA", "KOR"),
    # June 25 — groups D/E/F
    ("Grupo E", d(6, 25, 20), "ECU", "GER"),
    ("Grupo E", d(6, 25, 20), "CUW", "CIV"),
    ("Grupo F", d(6, 25, 23), "JPN", "SWE"),
    ("Grupo F", d(6, 25, 23), "TUN", "NED"),
    ("Grupo D", d(6, 26, 2), "TUR", "USA"),
    ("Grupo D", d(6, 26, 2), "PAR", "AUS"),
    # June 26 — groups G/H/I
    ("Grupo I", d(6, 26, 19), "NOR", "FRA"),
    ("Grupo I", d(6, 26, 19), "SEN", "IRQ"),
    ("Grupo H", d(6, 27, 0), "CPV", "KSA"),
    ("Grupo H", d(6, 27, 0), "URY", "ESP"),
    ("Grupo G", d(6, 27, 3), "EGY", "IRN"),
    ("Grupo G", d(6, 27, 3), "NZL", "BEL"),
    # June 27 — groups J/K/L
    ("Grupo L", d(6, 27, 21), "PAN", "ENG"),
    ("Grupo L", d(6, 27, 21), "CRO", "GHA"),
    ("Grupo K", d(6, 27, 23, 30), "COL", "POR"),
    ("Grupo K", d(6, 27, 23, 30), "COD", "UZB"),
    ("Grupo J", d(6, 28, 2), "ALG", "AUT"),
    ("Grupo J", d(6, 28, 2), "JOR", "ARG"),
]

# Knockout bracket placeholders — teams defined as groups conclude.
# Pool owner edits team names via admin panel once confirmed.
KNOCKOUT_MATCHES = [
    # Round of 32 — June 28 to July 3 (16 matches)
    ("32-avos", d(6, 28, 19), "1º Grupo A", "3º C/E/F/H"),
    ("32-avos", d(6, 28, 23), "2º Grupo B", "2º Grupo C"),
    ("32-avos", d(6, 29, 17), "1º Grupo E", "3º A/B/C/D"),
    ("32-avos", d(6, 29, 21), "1º Grupo F", "2º Grupo I"),
    ("32-avos", d(6, 30, 1), "1º Grupo C", "2º Grupo F"),
    ("32-avos", d(6, 30, 17), "1º Grupo I", "3º C/D/F/G"),
    ("32-avos", d(6, 30, 21), "1º Grupo B", "3º E/F/I/J"),
    ("32-avos", d(7, 1, 1), "2º Grupo D", "2º Grupo G"),
    ("32-avos", d(7, 1, 17), "1º Grupo D", "3º B/E/I/J"),
    ("32-avos", d(7, 1, 21), "1º Grupo G", "3º A/H/K/L"),
    ("32-avos", d(7, 2, 1), "2º Grupo A", "2º Grupo H"),
    ("32-avos", d(7, 2, 17), "1º Grupo H", "2º Grupo J"),
    ("32-avos", d(7, 2, 21), "1º Grupo J", "2º Grupo K"),
    ("32-avos", d(7, 3, 1), "1º Grupo K", "3º D/G/H/I"),
    ("32-avos", d(7, 3, 17), "1º Grupo L", "3º E/H/I/J"),
    ("32-avos", d(7, 3, 21), "2º Grupo E", "2º Grupo L"),
    # Round of 16 — July 4-7 (8 matches)
    ("Oitavas", d(7, 4, 17), "V. 32-avos 1", "V. 32-avos 2"),
    ("Oitavas", d(7, 4, 21), "V. 32-avos 3", "V. 32-avos 4"),
    ("Oitavas", d(7, 5, 17), "V. 32-avos 5", "V. 32-avos 6"),
    ("Oitavas", d(7, 5, 21), "V. 32-avos 7", "V. 32-avos 8"),
    ("Oitavas", d(7, 6, 17), "V. 32-avos 9", "V. 32-avos 10"),
    ("Oitavas", d(7, 6, 21), "V. 32-avos 11", "V. 32-avos 12"),
    ("Oitavas", d(7, 7, 17), "V. 32-avos 13", "V. 32-avos 14"),
    ("Oitavas", d(7, 7, 21), "V. 32-avos 15", "V. 32-avos 16"),
    # Quarterfinals — July 9-11 (4 matches)
    ("Quartas", d(7, 9, 20), "V. Oitavas 1", "V. Oitavas 2"),
    ("Quartas", d(7, 10, 20), "V. Oitavas 3", "V. Oitavas 4"),
    ("Quartas", d(7, 11, 17), "V. Oitavas 5", "V. Oitavas 6"),
    ("Quartas", d(7, 11, 21), "V. Oitavas 7", "V. Oitavas 8"),
    # Semifinals — July 14-15
    ("Semifinal", d(7, 14, 20), "V. Quartas 1", "V. Quartas 2"),
    ("Semifinal", d(7, 15, 20), "V. Quartas 3", "V. Quartas 4"),
    # Third place — July 18
    ("3º Lugar", d(7, 18, 20), "P. Semifinal 1", "P. Semifinal 2"),
    # Final — July 19
    ("Final", d(7, 19, 19), "V. Semifinal 1", "V. Semifinal 2"),
]


async def seed(force: bool = False):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = dt.datetime.now(UTC)

    async with async_session() as session:
        existing = await session.execute(select(Match).limit(1))
        if existing.scalar_one_or_none():
            if not force:
                print("Database already seeded. Use --force to wipe and reseed.")
                return
            await session.execute(delete(Prediction))
            await session.execute(delete(Match))
            print("Wiped existing matches and predictions.")

        count = 0
        for stage, match_dt, home, away in GROUP_MATCHES:
            session.add(Match(
                home_team=TEAMS[home],
                away_team=TEAMS[away],
                match_datetime=match_dt,
                stage=stage,
                allow_retroactive=match_dt < now,
            ))
            count += 1

        for stage, match_dt, home, away in KNOCKOUT_MATCHES:
            session.add(Match(
                home_team=home,
                away_team=away,
                match_datetime=match_dt,
                stage=stage,
                allow_retroactive=match_dt < now,
            ))
            count += 1

        await session.commit()
        print(f"Seeded {count} matches (72 group stage + 32 knockout).")


if __name__ == "__main__":
    asyncio.run(seed(force="--force" in sys.argv))
