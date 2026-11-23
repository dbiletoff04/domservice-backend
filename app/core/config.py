from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Домсервис API"
    app_debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/domservice"
    auto_init_db: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()