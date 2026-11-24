from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Домсервис API"
    app_debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/domservice"
    auto_init_db: bool = True

    jwt_secret_key: str = "domservice-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 часа
    sms_code_ttl_seconds: int = 300  # 5 минут

    notification_poll_interval_seconds: int = 5
    notification_max_attempts: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

