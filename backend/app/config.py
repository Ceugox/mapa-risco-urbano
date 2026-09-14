from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_path: str = "data/app.db"
    database_url: str = ""
    cge_interval: int = 300
    cemaden_interval: int = 600
    inmet_interval: int = 600
    meteo_interval: int = 900
    whatsapp_verify_token: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    admin_password: str = ""
    analytics_salt: str = ""
    analytics_retention_days: int = 90

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
