from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CODEMIND_", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./codemind.db"
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    auth_rate_limit_per_minute: int = 10
    cors_origins: list[str] = ["http://localhost:3000"]
    worker_enabled: bool = True  # in-process job worker (dev/small deploys); run dedicated workers + disable this at scale
    worker_poll_seconds: float = 3.0
    # --- LLM providers (all optional; keys supplied later). Order = fallback chain.
    llm_chain: list[str] = ["gemini", "groq", "openrouter", "ollama"]
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"
    gemini_embed_model: str = "text-embedding-004"  # verify against current Gemini docs when a key is added
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = 45.0
    llm_max_output_tokens: int = 900
    llm_daily_token_budget_per_user: int = 60000
    experiment_holdout_fraction: float = 0.10  # share of users who get the rating-matched BASELINE daily problem (measured, disclosed in Settings)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "nexora@localhost"
    redis_url: str = ""  # shared rate limits, cache and scheduler leader lease when set; in-process otherwise
    db_pool_size: int = 10  # per process. Total connections = replicas x workers x (pool_size + max_overflow): keep it under Postgres max_connections
    db_max_overflow: int = 10
    db_pool_recycle_s: int = 1800
    instance_id: str = ""  # shown in X-Served-By so the load balancer's spread is observable; defaults to the hostname
    metrics_token: str = ""  # bearer token for /metrics (otherwise admin role required)
    log_json: bool = True
    executor_url: str = ""  # remote code-execution service (separate host); local Docker if empty
    executor_key: str = ""
    experiment_salt: str = "daily-exp-v1"

    def validate_for_prod(self) -> None:
        if self.env == "prod" and self.jwt_secret.startswith("dev-only"):
            raise RuntimeError("CODEMIND_JWT_SECRET must be set in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
