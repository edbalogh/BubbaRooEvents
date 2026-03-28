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
    seatgeek_client_id: str = ""
    seatgeek_client_secret: str = ""

    # Notifications - Email (Resend)
    resend_api_key: str = ""
    notification_from_email: str = "events@bubbaroo.app"

    # Notifications - SMS (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Notifications - Push (Firebase)
    firebase_credentials_path: str = ""

    # App
    app_env: str = "development"
    use_mock_data: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
