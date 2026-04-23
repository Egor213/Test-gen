"""Анализ дублирования тестов — поиск семантически похожих тестов."""

import ast
import difflib
from pathlib import Path

from src.analysis.analyzers.base import AnalyzerVerdict, BaseAnalyzer


class DuplicationAnalyzer(BaseAnalyzer):
    SIMILARITY_THRESHOLD = 0.85

    @property
    def name(self) -> str:
        return "duplication"

    def analyze(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        project_root: Path,
        **kwargs,
    ) -> AnalyzerVerdict:
        all_tests: list[dict] = []
        for test_path, test_code in test_files.items():
            try:
                tree = ast.parse(test_code)
            except SyntaxError:
                continue

            for class_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                class_name = class_node.name

                for node in class_node.body:
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not node.name.startswith("test_"):
                        continue

                    body_code = self._normalize_test_body(node)
                    full_name = f"{class_name}.{node.name}"

                    all_tests.append(
                        {
                            "name": full_name,
                            "file": str(test_path),
                            "line": node.lineno,
                            "body": body_code,
                        }
                    )

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.name.startswith("test_"):
                    continue

                is_class_method = False
                for class_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                    if node in class_node.body:
                        is_class_method = True
                        break

                if is_class_method:
                    continue

                body_code = self._normalize_test_body(node)
                all_tests.append(
                    {
                        "name": node.name,
                        "file": str(test_path),
                        "line": node.lineno,
                        "body": body_code,
                    }
                )
        near_duplicates = 0
        duplicate_pairs: list[tuple[str, str, float]] = []
        for i in range(len(all_tests)):
            for j in range(i + 1, len(all_tests)):
                t1, t2 = all_tests[i], all_tests[j]
                similarity = self._compute_similarity(t1["body"], t2["body"])
                if similarity >= self.SIMILARITY_THRESHOLD:
                    near_duplicates += 1
                    duplicate_pairs.append((t1["name"], t2["name"], similarity))

        total_tests = len(all_tests)
        return AnalyzerVerdict(
            metadata={
                "total_tests": total_tests,
                "near_duplicates": near_duplicates,
                "duplicate_pairs": [
                    {"test1": p[0], "test2": p[1], "similarity": p[2]} for p in duplicate_pairs
                ],
            }
        )

    def _normalize_test_body(self, node: ast.AST) -> str:
        try:
            code = ast.unparse(node)
        except Exception:
            return ""

        lines = code.split("\n")
        body_lines = lines[1:] if len(lines) > 1 else lines
        body = "\n".join(body_lines)

        body = " ".join(body.split())
        return body

    def _compute_similarity(self, body1: str, body2: str) -> float:
        if not body1 or not body2:
            return 0.0
        return difflib.SequenceMatcher(None, body1, body2).ratio()
