from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://bubbaroo:bubbaroo@localhost:5432/bubbaroo_events"
    database_url_sync: str = "postgresql://bubbaroo:bubbaroo@localhost:5432/bubbaroo_events"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "change-me-to-a-random-secret-key"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # External APIs
    ticketmaster_api_key: str = ""

    # AI (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_recommend_model: str = "gemma4:26b"
    ollama_trip_model: str = "gemma4:26b"

    # Discovery & scraping
    discovery_search_model: str = "gemma4:26b"
    discovery_extract_model: str = "gemma4:26b"
    discovery_dedup_model: str = "gemma4:e2b"  # smaller model fine for yes/no dedup check
    discovery_source_score_threshold: float = 0.7
    discovery_dedup_confidence_threshold: float = 0.8
    crawl4ai_timeout: int = 30

    # Slack bot
    slack_signing_secret: str = ""
    slack_bot_token: str = ""

    # Notifications - Email (Resend)
    resend_api_key: str = ""
    notification_from_email: str = "events@bubbaroo.app"

    # Notifications - SMS (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Notifications - Push (Firebase)
    firebase_credentials_path: str = ""

    # Monitoring
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
