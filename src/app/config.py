"""从环境变量加载配置。密钥只走 .env，不写进代码。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    llm_provider: str = "openai"
    llm_model: str = "gpt-5.4-mini"
    llm_temperature: float = 0.7
    # 空字符串 = 不启用备用供应商，主模型失败后直接角色口吻降级
    llm_fallback_provider: str = ""
    llm_fallback_model: str = ""

    openai_api_key: str = ""
    openai_base_url: str | None = None
    deepseek_api_key: str = ""

    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=6)

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    cors_origins: str = "*"

    # 送给模型的轮数；库里仍保存全部消息
    short_term_turn_limit: int = Field(default=16, ge=2, le=64)

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "companion"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例，避免每个请求重新读盘。"""
    return Settings()
