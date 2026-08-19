from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "LexAI"

    app_env: str = "development"

    max_file_size_mb: int = 20

    max_text_length: int = 50000

    model_provider: str = "mock"

    model_name: str = "legal-assistant"

    legal_jurisdiction: str = "BR"

    confidence_threshold: float = 0.70

    cors_origins: str = (
        "http://localhost:5500,"
        "http://127.0.0.1:5500"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()