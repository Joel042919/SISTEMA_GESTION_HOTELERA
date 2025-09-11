from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    #db_host: str = "localhost"
    #db_port: int = 5432
    #db_name: str = "GestionHotel"
    #db_user: str = "postgres"
    #db_password: str = "maria042919"
    #app_secret: str = "change-me"
    #default_property_id: str = "00000000-0000-0000-0000-000000000000"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "BaseDatosHotel"
    db_user: str = "postgres"
    db_password: str = "pms_pass"
    default_property_id: str = Field("00000000-0000-0000-0000-000000000000", alias="DEFAULT_PROPERTY_ID")
    
    # Ejemplos de variables (ajusta a lo tuyo)
    DB_DSN: str = Field("postgresql://postgres:pms_pass@localhost:5432/BaseDatosHotel", alias="DATABASE_URL")
    SECRET_KEY: str = Field(default="change-me", alias="SECRET_KEY")
    DEBUG: bool = False
    
     # Configuración de carga de .env (opcional)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # para ignorar variables no definidas en el modelo
        populate_by_name=True, #permite que alias y nombre funcionen
    )
    


settings = Settings()