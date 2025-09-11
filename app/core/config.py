from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    #db_host: str = "localhost"
    #db_port: int = 5432
    #db_name: str = "GestionHotel"
    #db_user: str = "postgres"
    #db_password: str = "maria042919"
    #app_secret: str = "change-me"
<<<<<<< HEAD
    #default_property_id: str = "00000000-0000-0000-0000-000000000000"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "BaseDatosHotel"
    db_user: str = "postgres"
    db_password: str = "pms_pass"
    default_property_id: str = Field("00000000-0000-0000-0000-000000000000", alias="DEFAULT_PROPERTY_ID")
    
=======
    default_property_id: str = "00000000-0000-0000-0000-000000000000"
>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff
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