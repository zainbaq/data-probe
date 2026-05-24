from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DataProbe"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://dataprobe:changeme@db:5432/dataprobe"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Clerk
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Encryption
    encryption_key: str = ""  # 32-byte hex string

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Upload limits
    max_upload_size_mb: int = 250

    # Profiling limits
    statement_timeout_ms: int = 30_000
    max_profile_rows: int = 50_000
    max_top_values: int = 20

    # Upload directory
    upload_dir: str = "/app/uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
