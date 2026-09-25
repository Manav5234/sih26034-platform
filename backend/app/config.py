from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/sih26034"
    jwt_secret: str
    # ponytail: placeholder HF origin — replace with the real Space URL once it exists.
    allowed_origins: str = (
        "http://localhost:3000,https://REPLACE-WITH-HF-SPACE-URL.hf.space"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
