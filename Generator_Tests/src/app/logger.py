# File path: Generator_Tests/src/app/logger.py
import asyncio
import logging
from enum import Enum
from logging.handlers import RotatingFileHandler


class CoroutineIdFilter(logging.Filter):
    def filter(self, record):
        task = asyncio.current_task()
        if task:
            record.coro_id = id(task)
            record.coro_name = task.get_name()
        else:
            record.coro_id = None
            record.coro_name = None
        return True


class LogOutput(str, Enum):
    FILE = "file"
    CONSOLE = "console"
    BOTH = "both"
    NONE = "none"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None


def get_logger(
    name: str,
    output: LogOutput = LogOutput.BOTH,
    log_file: str = "logs/app.log",
    file_level: int = logging.INFO,
    console_level: int = logging.INFO,
) -> logging.Logger | None:

    logger = logging.getLogger(name)
    logger.addFilter(CoroutineIdFilter())

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    if output == LogOutput.NONE:
        logger.disabled = True
        return None

    logger.setLevel(min(file_level, console_level))

    if output in (LogOutput.FILE, LogOutput.BOTH):
        file_handler = RotatingFileHandler(
            log_file,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [coro_id=%(coro_id)s coro_name=%(coro_name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if output in (LogOutput.CONSOLE, LogOutput.BOTH):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


class NullLogger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def critical(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass
