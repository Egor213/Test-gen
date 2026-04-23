from dataclasses import dataclass, field
from pathlib import Path

from src.entity.project import FunctionInfo


@dataclass
class FunctionTarget:
    full_path: str
    file_path: Path
    function_name: str
    info: FunctionInfo
    test_path: Path = field(default_factory=Path)

    @classmethod
    def from_index_entry(cls, function_path: str, function_info: FunctionInfo) -> "FunctionTarget":
        path_file, function_name = function_path.rsplit("::", 1)
        return cls(
            full_path=function_path,
            file_path=Path(path_file),
            function_name=function_name,
            info=function_info,
        )

    @property
    def test_filename(self) -> str:
        return f"test_{self.file_path.stem}.py"


@dataclass
class FunctionTestResult:
    target: FunctionTarget
    test_code: str | None = None
    line_coverage: int | None = None
    # TODO: удалить эту штуку
    success: bool = False
