import logging
import os
import subprocess
from pathlib import Path

from src.app.logger import NullLogger
from src.utils.workspace_helper import WorkspaceHelper


class TestRunner:
    def __init__(
        self,
        project_path: Path,
        workspace_helper: WorkspaceHelper,
        logger: logging.Logger | None = None,
        timeout: int = 60,
    ):
        self.project_path = project_path
        self.logger = logger or NullLogger()
        self.timeout = timeout
        self.workspace_helper = workspace_helper

    def run_tests(
        self,
        test_code: str,
        test_filename: str = "test_generated.py",
        fast: bool = False,
    ) -> tuple[bool, str]:
        self.workspace_helper.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_helper.ensure_pytest_installed()
        test_file = self.workspace_helper.sandbox_dir / test_filename

        try:
            test_file.write_text(test_code, encoding="utf-8")

            if fast:
                pytest_args = ["-x", "--tb=no", "--no-header", "-q"]
            else:
                pytest_args = ["-v", "--tb=short", "--no-header"]

            result = subprocess.run(
                [
                    self.workspace_helper._venv_python,
                    "-m",
                    "pytest",
                    str(test_file),
                    *pytest_args,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.project_path),
                env=self.workspace_helper.build_env(),
            )

            raw_output = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                self.logger.info("[TESTRUNNER] Тесты в песочнице ПРОШЛИ")
                return True, ""

            return False, raw_output

        except subprocess.TimeoutExpired:
            msg = f"[TESTRUNNER] Таймаут выполнения тестов ({self.timeout}с)"
            self.logger.error(msg)
            return False, msg

        except Exception as e:
            msg = f"[TESTRUNNER] Ошибка выполнения в песочнице: {e}"
            self.logger.error(msg)
            return False, msg

        finally:
            if test_file.exists():
                test_file.unlink()
