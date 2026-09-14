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
    # Roteirizadores OSRM públicos, baixo volume de uso. Identificamos o
    # tráfego com um User-Agent (ver routing.py) para respeitar a política de
    # uso justo dos dois serviços e facilitar contato em caso de abuso.
    osrm_driving_url: str = "https://router.project-osrm.org/route/v1/driving"
    # Servidor FOSSGIS (routing.openstreetmap.de). O segmento "driving" no
    # caminho é exigido pela API mesmo para o perfil "routed-foot" (a pé).
    osrm_walking_url: str = "https://routing.openstreetmap.de/routed-foot/route/v1/driving"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
