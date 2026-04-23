"""Анализ надёжности тестов — обнаружение flaky tests."""

import subprocess
from pathlib import Path

from src.analysis.analyzers.base import AnalyzerVerdict, BaseAnalyzer
from src.utils.workspace_helper import WorkspaceHelper


class ReliabilityAnalyzer(BaseAnalyzer):
    """Запускает тесты несколько раз для обнаружения flaky tests."""

    NUM_RUNS = 3
    TIMEOUT_PER_RUN = 90

    @property
    def name(self) -> str:
        return "reliability"

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

        run_results: list[dict[str, str]] = []

        for run_num in range(1, self.NUM_RUNS + 1):
            self.logger.debug(f"[RELIABILITY] Run {run_num}/{self.NUM_RUNS}")
            result = self._run_tests(test_paths, project_root)
            run_results.append(result)

        flaky_tests = self._detect_flaky(run_results)
        all_pass_count = sum(1 for r in run_results if r["status"] == "passed")
        all_fail_count = sum(1 for r in run_results if r["status"] == "failed")

        flaky_count = len(flaky_tests)

        return AnalyzerVerdict(
            metadata={
                "num_runs": self.NUM_RUNS,
                "all_pass_runs": all_pass_count,
                "all_fail_runs": all_fail_count,
                "flaky_tests": list(flaky_tests.keys()),
                "flaky_count": flaky_count,
            },
        )

    def _run_tests(self, test_paths: list[Path], project_root: Path) -> dict:
        cmd = [
            self.workspace_helper._venv_pytest,
            "-v",
            "--tb=no",
            "--no-header",
        ]
        for tp in test_paths:
            cmd.append(str(tp))

        env = self.workspace_helper.build_env()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_PER_RUN,
                cwd=str(project_root),
                env=env,
            )

            test_results = self._parse_verbose_output(result.stdout)
            overall = "passed" if result.returncode == 0 else "failed"

            return {
                "status": overall,
                "test_results": test_results,
                "test_names": set(test_results.keys()),
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "test_results": {},
                "test_names": set(),
            }
        except Exception as e:
            self.logger.error(f"[RELIABILITY] Run error: {e}")
            return {
                "status": "error",
                "test_results": {},
                "test_names": set(),
            }

    def _parse_verbose_output(self, output: str) -> dict[str, str]:
        results: dict[str, str] = {}
        for line in output.splitlines():
            line = line.strip()
            if " PASSED" in line:
                test_name = line.split(" PASSED")[0].strip()
                results[test_name] = "passed"
            elif " FAILED" in line:
                test_name = line.split(" FAILED")[0].strip()
                results[test_name] = "failed"
            elif " ERROR" in line:
                test_name = line.split(" ERROR")[0].strip()
                results[test_name] = "failed"
        return results

    def _detect_flaky(self, run_results: list[dict]) -> dict[str, list[str]]:
        all_test_names: set[str] = set()
        for r in run_results:
            all_test_names.update(r.get("test_names", set()))

        flaky: dict[str, list[str]] = {}
        for test_name in all_test_names:
            statuses = []
            for r in run_results:
                status = r.get("test_results", {}).get(test_name, "missing")
                statuses.append(status)

            unique = set(s for s in statuses if s != "missing")
            if len(unique) > 1:
                flaky[test_name] = statuses

        return flaky
