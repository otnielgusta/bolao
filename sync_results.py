"""
Sync World Cup results from football-data.org and recalculate pool points.
Run: uv run python sync_results.py
Schedule it (e.g. Task Scheduler / cron every 30 min) during the tournament.
"""
import asyncio

from app.database import async_session
from app.services.sync import sync_results


async def main():
    async with async_session() as db:
        summary = await sync_results(db)
    print(
        f"Linked: {summary['linked']} | "
        f"Schedule updates: {summary['updated_schedule']} | "
        f"Newly finished: {summary['finished']} | "
        f"Predictions scored: {summary['predictions_scored']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
