from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str = ""
    telegram_webapp_url: str = ""
    database_url: str = "sqlite+aiosqlite:///./velora.db"
    redis_url: str = "redis://localhost:6379/0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    collector_url: str = ""
    collector_urls: str = ""
    collector_interval_seconds: float = 2.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def source_urls(self) -> list[str]:
        raw = ",".join(x for x in (self.collector_url, self.collector_urls) if x)
        return [x.strip() for x in raw.split(",") if x.strip()]

settings = Settings()
