"""Configuration handling using Pydantic settings."""

from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel as BaseSettings, Field  # type: ignore

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Networking / scraping behaviour (legacy fields retained for compatibility)
    BASE_URL: str = Field(default="https://example.com")
    RATE_LIMIT_RPS: float = Field(default=1.0)
    CONCURRENCY: int = Field(default=5)
    TIMEOUT_S: float = Field(default=10.0)
    RETRY_MAX: int = Field(default=3)
    USER_AGENT: str = Field(default="rscraper/0.1.0")
    PROXY_URL: Optional[str] = Field(default=None)

    # Output options
    OUTPUT_FORMAT: Literal["csv", "parquet", "sqlite"] = Field(default="csv")
    OUTPUT_PATH: Path = Field(default=Path("output.csv"))
    OUTPUT_CSV: Path = Field(default=Path("./out/listings.csv"))

    # Misc storage paths
    INPUT_HAR_DIR: Path = Field(default=Path("./hars"))
    RESUME_DB: Path = Field(default=Path("resume.db"))
    AMENITY_VOCAB_PATH: Path = Field(default=Path("./data/amenity_vocab.json"))

    # Location fallbacks and logging
    CITY_FALLBACK: Optional[str] = Field(default=None)
    STATE_FALLBACK: Optional[str] = Field(default=None)
    LOG_LEVEL: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
