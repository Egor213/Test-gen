# FILE: src/manager/config.py
import logging
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, YamlConfigSettingsSource

from src.app.logger import LogLevel, LogOutput
from src.entity.llm import LLMProvider


class AIConfig(BaseModel):
    llm_provider: LLMProvider = "openai"
    model: str
    temperature: float = 0.1
    max_tokens: int = 40000
    base_url: str = "http://localhost:1234/v1/"
    timeout: int = 900
    max_generate_retries: int = 3
    max_fix_attempts: int = 4
    max_invoke_retries: int = 3
    target_line_coverage: int = 60

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not (0 < v <= 1):
            raise ValueError("temperature must be in the range (0, 1]")
        return v

    @field_validator(
        "max_tokens",
        "timeout",
        "max_generate_retries",
        "max_fix_attempts",
        "max_invoke_retries",
    )
    @classmethod
    def validate_positive_int(cls, v: int, info) -> int:
        if v < 0:
            raise ValueError(f"{info.field_name} must be greater than or equal 0")
        return v


class LoggerConfig(BaseModel):
    file_level: LogLevel = Field(LogLevel.INFO)
    console_level: LogLevel = Field(LogLevel.INFO)
    log_out: LogOutput = Field(LogOutput.CONSOLE)
    log_file: str = Field("logs/app.log")

    LEVEL_MAP: ClassVar[dict[str, int]] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    @property
    def numeric_console_level(self) -> int:
        return self.LEVEL_MAP[self.console_level]

    @property
    def numeric_file_level(self) -> int:
        return self.LEVEL_MAP[self.file_level]


class App(BaseModel):
    max_async_workers: int = 1


class Config(BaseSettings):
    app: App
    ai: AIConfig
    logger: LoggerConfig
    ai_api_key: str | None = None

    def __init__(
        self,
        config_file_path: Path | None = None,
        _env_file_path: Path | None = None,
        **data,
    ):
        self._config_file_path = config_file_path or Path("config/config.yaml")
        self._env_file_path = _env_file_path or Path("config/.env")
        super().__init__(**data)

    def settings_customise_sources(self, settings_cls, **kwargs):
        return (
            DotEnvSettingsSource(
                settings_cls,
                env_file=self._env_file_path,
                env_file_encoding="utf-8",
            ),
            YamlConfigSettingsSource(settings_cls, self._config_file_path),
        )
