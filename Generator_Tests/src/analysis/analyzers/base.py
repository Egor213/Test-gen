# ===== FILE: src/analysis/analyzers/base.py =====
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from src.app.logger import NullLogger


@dataclass
class AnalyzerVerdict:
    metadata: dict = field(default_factory=dict)


class BaseAnalyzer(ABC):

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or NullLogger()

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def analyze(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        project_root: Path,
        **kwargs,
    ) -> AnalyzerVerdict: ...
