from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/sih26034"
    jwt_secret: str

    class Config:
        env_file = ".env"


settings = Settings()
