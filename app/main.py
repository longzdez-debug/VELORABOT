import asyncio
import uvicorn
from app.api import app
from app.bot import run_bot

async def main():
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info"))
    await asyncio.gather(server.serve(), run_bot())

if __name__ == "__main__":
    asyncio.run(main())
