from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/sih26034"
    jwt_secret: str
    allowed_origins: str = "http://localhost:3000"
    # "auto" = RapidOCR primary + Tesseract fallback (default);
    # "tesseract_only" = skip RapidOCR entirely — memory stopgap for
    # constrained hosts like Render's free 512MB tier (RapidOCR's ONNX
    # model load + inference run in-process and push RSS past the ceiling).
    # See docs/ocr-engine-decision.md.
    ocr_engine_mode: str = "auto"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
