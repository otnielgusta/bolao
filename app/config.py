from pydantic import model_validator
from pydantic_settings import BaseSettings

INSECURE_SECRETS = {"", "change-me", "secret", "changeme"}


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bolao"
    secret_key: str = "change-me"
    session_cookie_name: str = "bolao_session"
    # None = decide from debug (secure in prod, off in local HTTP dev).
    session_cookie_secure: bool | None = None
    session_max_age_seconds: int = 60 * 60 * 24 * 30  # 30 days
    debug: bool = False
    football_data_token: str = ""
    admin_token: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return not self.debug

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        # In production (debug off) a forgeable session secret = full account
        # takeover. Refuse to boot with a default/weak SECRET_KEY.
        if not self.debug:
            if self.secret_key in INSECURE_SECRETS or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY inseguro. Defina um valor aleatório com 32+ "
                    "caracteres (ex.: `python -c \"import secrets; "
                    "print(secrets.token_urlsafe(48))\"`)."
                )
        return self


settings = Settings()
