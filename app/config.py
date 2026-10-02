from pydantic import Field
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

    kufar_queries_raw: str = Field(default="", validation_alias="KUFAR_QUERIES")
    kufar_interval_ms: int = 1000
    kufar_size: int = 42

    event_batch_size: int = 20
    event_reconnect_seconds: float = 2.0
    event_consumer_group: str = "velora-processors"
    event_stream: str = "velora:listings:events"
    event_dead_stream: str = "velora:listings:dead"
    event_maxlen: int = 100_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def source_urls(self) -> list[str]:
        raw = ",".join(x for x in (self.collector_url, self.collector_urls) if x)
        return [x.strip() for x in raw.split(",") if x.strip()]

    def kufar_query_list(self) -> list[str]:
        return [x.strip() for x in self.kufar_queries_raw.split(",") if x.strip()]


settings = Settings()
