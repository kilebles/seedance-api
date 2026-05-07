from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    seedance_api_key: str
    seedance_base_url: str

    model_config = {"env_file": ".env"}


settings = Settings()
