from pathlib import Path

from src.entity.project import FunctionInfo
from src.managers.project_indexer import ProjectIndexer

SKIP_NAME_PREFIXES = ("test", "Test")
SKIP_NAME_SUFFIXES = ("test", "Test")
SKIP_EXACT_NAMES = frozenset({"main"})
TEST_DIR_NAMES = frozenset({"test", "tests"})

MAX_LINE_LENGTH = 200


class PathFilter:
    def __init__(
        self,
        project_indexer: ProjectIndexer,
        target_dir: str | None = None,
        target_function: str | None = None,
        target_class: str | None = None,
        target_file: str | None = None,
    ):
        self._indexer = project_indexer
        self._target_dir = str(Path(target_dir)) if target_dir is not None else None
        self._target_function = str(Path(target_function)) if target_function is not None else None
        self._target_class = str(Path(target_class)) if target_class is not None else None
        self._target_file = str(Path(target_file)) if target_file is not None else None

    def should_test(self, function_path: str) -> bool:
        path_file, function_name = function_path.rsplit("::", 1)
        parts = function_name.split(".")

        if self._is_dunder(parts[-1]):
            return False
        if parts[-1] in SKIP_EXACT_NAMES:
            return False
        if self._matches_test_pattern(parts):
            return False
        if self._is_in_test_directory(path_file):
            return False

        if self.has_custom_filter:
            return self.matches(function_path)

        return True

    def matches(self, function_path: str) -> bool:
        path_file, function_name = function_path.rsplit("::", 1)

        if self._target_function is not None:
            if not self._matches_function(function_path, function_name):
                return False

        if self._target_class is not None:
            if not self._matches_class(function_name):
                return False

        if self._target_file is not None:
            if not self._matches_file(path_file):
                return False

        if self._target_dir is not None:
            if not self._matches_directory(path_file):
                return False

        return True

    @staticmethod
    def _is_dunder(name: str) -> bool:
        return name.startswith("__") and name.endswith("__")

    @staticmethod
    def _matches_test_pattern(parts: list[str]) -> bool:
        return any(
            part.startswith(SKIP_NAME_PREFIXES) or part.endswith(SKIP_NAME_SUFFIXES)
            for part in parts
        )

    def _is_in_test_directory(self, path_file: str) -> bool:
        relative = self._indexer.relative_path(path_file)
        return bool(TEST_DIR_NAMES & set(Path(relative).parts))

    @property
    def has_custom_filter(self) -> bool:
        return (
            self._target_dir is not None
            or self._target_function is not None
            or self._target_class is not None
            or self._target_file is not None
        )

    def _matches_file(self, path_file: str) -> bool:
        """
        Форматы
        - "file.py"
        - "path/to/file.py"
        """
        relative = self._indexer.relative_path(path_file)
        target_file = self._target_file.replace("\\", "/").strip("/")
        relative_str = str(Path(relative)).replace("\\", "/")
        return relative_str == target_file or relative_str.endswith(f"/{target_file}")

    def _matches_function(self, full_path: str, function_name: str) -> bool:
        """
        Форматы
        - "func_name"
        - "ClassName.method_name"
        - "path/to/file.py::ClassName.method_name"
        """
        target = self._target_function

        if "::" in target:
            return full_path.endswith(target) or full_path == target

        return function_name == target or function_name.endswith(f".{target}")

    def _matches_class(self, function_name: str) -> bool:
        """
        Форматы
        - "ClassName"
        - "path/to/file.py::ClassName"
        """

        if "." not in function_name:
            return False

        target = self._target_class

        if "::" in target:
            target = target.split("::", 1)[-1]

        class_name = function_name.split(".", 1)[0]

        return class_name == target

    def _matches_directory(self, path_file: str) -> bool:
        relative = self._indexer.relative_path(path_file)
        target_dir = self._target_dir.replace("\\", "/").strip("/")
        relative_str = str(Path(relative)).replace("\\", "/")
        return relative_str.startswith(target_dir)
