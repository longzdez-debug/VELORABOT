import asyncio

import uvicorn

from app.api import app
from app.bot import run_bot
from app.collector import run_collector
from app.kufar import run_kufar
from app.config import settings
from app.pipeline import run_event_worker


async def main():
    server = uvicorn.Server(
        uvicorn.Config(app, host=settings.api_host, port=settings.api_port, log_level="info")
    )
    tasks = [server.serve(), run_event_worker()]
    if settings.telegram_bot_token:
        tasks.append(run_bot())
    if settings.source_urls():
        tasks.append(run_collector())
    if settings.kufar_query_list():
        tasks.append(run_kufar())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
