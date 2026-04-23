"""Анализ покрытия кода тестами через pytest-cov."""

import json
import subprocess
from pathlib import Path

from src.analysis.analyzers.base import AnalyzerVerdict, BaseAnalyzer
from src.utils.workspace_helper import WorkspaceHelper


class CoverageAnalyzer(BaseAnalyzer):
    """Запускает pytest-cov и анализирует покрытие исходного кода."""

    TIMEOUT = 120

    @property
    def name(self) -> str:
        return "coverage"

    def __init__(self, workspace_helper: WorkspaceHelper, **kwargs):
        super().__init__(**kwargs)
        self.workspace_helper = workspace_helper

    def analyze(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        project_root: Path,
        **kwargs,
    ) -> AnalyzerVerdict:
        test_paths = list(test_files.keys())
        if not test_paths:
            return AnalyzerVerdict()

        coverage_data = self._run_coverage(test_paths, source_files, project_root)

        if coverage_data is None:
            return AnalyzerVerdict()

        total_stmts = 0
        total_miss = 0
        file_coverages: dict[str, dict] = {}

        for file_path, file_data in coverage_data.get("files", {}).items():
            summary = file_data.get("summary", {})
            stmts = summary.get("num_statements", 0)
            miss = summary.get("missing_lines", 0)
            covered = stmts - miss
            pct = (covered / stmts * 100) if stmts > 0 else 100.0

            total_stmts += stmts
            total_miss += miss

            file_coverages[file_path] = {
                "statements": stmts,
                "missing": miss,
                "covered": covered,
                "percent": round(pct, 1),
                "missing_lines": file_data.get("missing_lines", []),
            }

        total_pct = (total_stmts - total_miss) / total_stmts * 100 if total_stmts > 0 else 100.0

        return AnalyzerVerdict(
            metadata={
                "total_coverage_percent": round(total_pct, 1),
                "total_statements": total_stmts,
                "total_missing": total_miss,
                "file_coverages": file_coverages,
            },
        )

    def _collect_cov_dirs(
        self,
        source_files: dict[Path, str],
        test_file_set: set[Path],
        project_root: Path,
    ) -> set[str]:
        """Собирает верхнеуровневые директории source файлов (без тестовых)."""
        cov_dirs: set[str] = set()

        for sp in source_files:
            if sp in test_file_set:
                continue

            parts_lower = [p.lower() for p in sp.parts]
            if any(p in ("tests", "test") or p.startswith("test_") for p in parts_lower):
                continue

            try:
                rel = sp.relative_to(project_root)
            except ValueError:
                continue

            top = rel.parts[0] if len(rel.parts) > 1 else "."
            cov_dirs.add(top)

        return cov_dirs

    def _run_coverage(
        self,
        test_paths: list[Path],
        source_files: dict[Path, str],
        project_root: Path,
    ) -> dict | None:
        test_file_set = set(test_paths)

        cov_dirs = self._collect_cov_dirs(source_files, test_file_set, project_root)
        if not cov_dirs:
            self.logger.warning("[COVERAGE] No source dirs found to measure coverage")
            return None

        cov_json_path = project_root / ".coverage_report.json"

        coveragerc_path = project_root / ".coveragerc_tmp"
        omit_lines = "\n    ".join(
            [
                "*/tests/*",
                "*/test_*.py",
                "*/test.py",
                "*/__pycache__/*",
                "*/conftest.py",
            ]
        )
        coveragerc_path.write_text(
            f"[run]\nomit =\n    {omit_lines}\n\n" f"[report]\nomit =\n    {omit_lines}\n",
            encoding="utf-8",
        )

        cmd = [
            self.workspace_helper._venv_pytest,
            "--tb=no",
            "--no-header",
            "-q",
            f"--cov-report=json:{cov_json_path}",
            f"--cov-config={coveragerc_path}",
        ]
        for d in sorted(cov_dirs):
            cmd.append(f"--cov={d}")
        for tp in test_paths:
            cmd.append(str(tp))

        env = self.workspace_helper.build_env()

        try:
            self.logger.debug(f"[COVERAGE] Running: {cmd}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
                cwd=str(project_root),
                env=env,
            )

            if result.stderr:
                self.logger.debug(f"[COVERAGE] stderr: {result.stderr[-500:]}")

            if not cov_json_path.exists():
                self.logger.warning(
                    f"[COVERAGE] JSON report not created. "
                    f"stdout: {result.stdout[-300:]}, "
                    f"stderr: {result.stderr[-300:]}"
                )
                return None

            data = json.loads(cov_json_path.read_text(encoding="utf-8"))
            return data

        except subprocess.TimeoutExpired:
            self.logger.error("[COVERAGE] Timeout running coverage")
            return None
        except Exception as e:
            self.logger.error(f"[COVERAGE] Error: {e}")
            return None
        finally:
            cov_json_path.unlink(missing_ok=True)
            coveragerc_path.unlink(missing_ok=True)
