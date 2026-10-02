import asyncio
import uvicorn
from app.api import app
from app.bot import run_bot
from app.collector import run_collector
from app.config import settings

async def main():
    server=uvicorn.Server(uvicorn.Config(app,host=settings.api_host,port=settings.api_port,log_level="info"))
    tasks=[server.serve()]
    if settings.telegram_bot_token: tasks.append(run_bot())
    if settings.collector_url: tasks.append(run_collector())
    await asyncio.gather(*tasks)

if __name__=="__main__":
    asyncio.run(main())
