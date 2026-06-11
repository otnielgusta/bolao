from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bolao"
    secret_key: str = "change-me"
    session_cookie_name: str = "bolao_session"
    debug: bool = False
    football_data_token: str = ""
    admin_token: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
