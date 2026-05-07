from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # BytePlus Seedance API
    seedance_api_key: str
    seedance_base_url: str

    # PostgreSQL
    database_url: str

    # Fixed admin account (no registration yet)
    admin_username: str
    admin_password: str

    # Background worker
    worker_poll_interval: int = 10  # seconds
    seedance_max_concurrent: int = 10  # max tasks running in BytePlus at once

    model_config = {"env_file": ".env"}


settings = Settings()
