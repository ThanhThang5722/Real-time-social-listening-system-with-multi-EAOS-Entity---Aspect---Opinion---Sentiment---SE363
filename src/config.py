"""Configuration management for TV Producer Analytics"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings with validation"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ----------------------------------------
    # GCP Configuration
    # ----------------------------------------
    gcp_project_id: str
    gcp_region: str = "us-central1"
    gcp_location: str = "us-central1"
    google_application_credentials: str = "./gcp-service-account.json"

    # Cloud Pub/Sub
    pubsub_topic_id: str = "tv-comments"
    pubsub_subscription_id: str = "tv-comments-sub"
    pubsub_max_messages: int = 100

    # Vertex AI
    vertex_ai_model: str = "gemini-1.5-pro"
    vertex_ai_temperature: float = 0.1
    vertex_ai_max_output_tokens: int = 2048
    vertex_ai_top_p: float = 0.95
    vertex_ai_top_k: int = 40

    # ----------------------------------------
    # Redis Configuration
    # ----------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_decode_responses: bool = True

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ----------------------------------------
    # ClickHouse Configuration
    # ----------------------------------------
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_native_port: int = 9000
    clickhouse_database: str = "tv_analytics"
    clickhouse_username: str = "admin"
    clickhouse_password: str = "admin123"

    @property
    def clickhouse_url(self) -> str:
        """Get ClickHouse HTTP connection URL"""
        return f"http://{self.clickhouse_host}:{self.clickhouse_port}"

    # ----------------------------------------
    # Elasticsearch Configuration
    # ----------------------------------------
    elasticsearch_host: str = "localhost"
    elasticsearch_port: int = 9200
    elasticsearch_scheme: str = "http"
    elasticsearch_index_comments: str = "tv_comments"
    elasticsearch_index_trends: str = "tv_trends"

    @property
    def elasticsearch_url(self) -> str:
        """Get Elasticsearch connection URL"""
        return f"{self.elasticsearch_scheme}://{self.elasticsearch_host}:{self.elasticsearch_port}"

    # ----------------------------------------
    # LangFuse Configuration
    # ----------------------------------------
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    @property
    def langfuse_enabled(self) -> bool:
        """Check if LangFuse is configured"""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    # ----------------------------------------
    # API Configuration
    # ----------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_debug: bool = False
    api_reload: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # ----------------------------------------
    # EAOS Configuration
    # ----------------------------------------
    eaos_sentiment_weight: float = 0.6
    eaos_engagement_weight: float = 0.4
    eaos_decay_factor: float = 0.9
    eaos_time_window_minutes: int = 5

    # ----------------------------------------
    # Trend Detection
    # ----------------------------------------
    trend_min_mentions: int = 10
    trend_time_windows: str = "5,15,60"  # minutes
    trend_spike_threshold: float = 2.0

    @property
    def trend_time_windows_list(self) -> List[int]:
        """Get trend time windows as list of integers"""
        return [int(w.strip()) for w in self.trend_time_windows.split(",")]

    # ----------------------------------------
    # Agent Configuration
    # ----------------------------------------
    agent_max_iterations: int = 5
    agent_timeout_seconds: int = 30
    agent_verbose: bool = True

    # ----------------------------------------
    # Logging
    # ----------------------------------------
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "logs/app.log"

    # ----------------------------------------
    # Feature Flags
    # ----------------------------------------
    enable_bigquery: bool = False
    enable_anomaly_detection: bool = True
    enable_auto_recommendations: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
