import logging
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from src.app.logger import NullLogger


class WorkspaceHelper:
    def __init__(
        self,
        project_path: Path,
        logger: logging.Logger | None = None,
    ):
        self.project_path = project_path
        self.logger = logger or NullLogger()

        self.sandbox_dir = Path(tempfile.mkdtemp(prefix="testgen_sandbox_"))
        # self.sandbox_dir = Path("../Test_dir")
        self.logger.debug(f"Песочница создана: {self.sandbox_dir}")

        self.venv_dir = self.sandbox_dir / ".venv"

        self._create_venv()
        self._install_project_dependencies()
        self.ensure_pytest_installed()

    def _create_venv(self) -> None:
        self.logger.info(f"Создание venv: {self.venv_dir}")
        venv.create(str(self.venv_dir), with_pip=True, clear=True)

    @property
    def _venv_python(self) -> str:
        if sys.platform == "win32":
            return str(self.venv_dir / "Scripts" / "python.exe")
        return str(self.venv_dir / "bin" / "python")

    @property
    def _venv_pytest(self) -> str:
        if sys.platform == "win32":
            return str(self.venv_dir / "Scripts" / "pytest.exe")
        return str(self.venv_dir / "bin" / "pytest")

    def cleanup(self) -> None:
        if self.sandbox_dir and self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)

    def __del__(self):
        self.cleanup()

    def ensure_pytest_installed(self) -> None:
        self._run_install_cmd(
            [
                self._venv_python,
                "-m",
                "pip",
                "install",
                "pytest",
                "pytest-asyncio",
                "pytest-cov",
                "coverage",
                "--quiet",
            ],
            label="pip install pytest",
        )

    def _install_project_dependencies(self) -> None:
        root = self.project_path

        self._run_install_cmd(
            [self._venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            label="pip upgrade",
        )

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            if self._file_contains(pyproject, "[tool.poetry]"):
                if shutil.which("poetry"):
                    env = os.environ.copy()
                    env["VIRTUAL_ENV"] = str(self.venv_dir)
                    self._run_install_cmd(
                        ["poetry", "install", "--no-interaction", "--no-root"],
                        label="poetry install",
                        extra_env=env,
                    )
                    return
                self.logger.warning("poetry не найден в PATH, пробую pip")

            self._run_install_cmd(
                [self._venv_python, "-m", "pip", "install", "-e", ".", "--quiet"],
                label="pip install -e . (pyproject.toml)",
            )
            return

        pipfile = root / "Pipfile"
        if pipfile.exists():
            if shutil.which("pipenv"):
                self._run_install_cmd(
                    ["pipenv", "install", "--dev", "--skip-lock"],
                    label="pipenv install",
                )
                return
            self.logger.warning("pipenv не найден в PATH, ищу другие варианты")

        req_files = sorted(root.glob("requirements*.txt"))
        if req_files:
            for req_file in req_files:
                self._run_install_cmd(
                    [
                        self._venv_python,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(req_file),
                        "--quiet",
                    ],
                    label=f"pip install -r {req_file.name}",
                )
            return

        setup_py = root / "setup.py"
        setup_cfg = root / "setup.cfg"
        if setup_py.exists() or setup_cfg.exists():
            found = "setup.py" if setup_py.exists() else "setup.cfg"
            self._run_install_cmd(
                [self._venv_python, "-m", "pip", "install", "-e", ".", "--quiet"],
                label=f"pip install -e . ({found})",
            )
            return

        self.logger.info("Файлы зависимостей не найдены, пропускаю установку")

    def _run_install_cmd(
        self,
        cmd: list[str],
        label: str = "install",
        extra_env: dict | None = None,
    ) -> None:
        try:
            self.logger.info(f"[{label}] Выполняю: {' '.join(cmd)}")

            env = extra_env if extra_env is not None else os.environ.copy()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.project_path),
                env=env,
            )
            if result.returncode == 0:
                self.logger.info(f"[{label}] Зависимости установлены")
            else:
                self.logger.warning(
                    f"[{label}] Код {result.returncode}\n"
                    f"stdout: {result.stdout[-500:]}\n"
                    f"stderr: {result.stderr[-500:]}"
                )
        except subprocess.TimeoutExpired:
            self.logger.error(f"[{label}] Таймаут установки (300с)")
        except FileNotFoundError:
            self.logger.error(f"[{label}] Команда не найдена: {cmd[0]}")
        except Exception as e:
            self.logger.error(f"[{label}] Ошибка: {e}")

    @staticmethod
    def _file_contains(filepath: Path, needle: str) -> bool:
        try:
            return needle in filepath.read_text(encoding="utf-8")
        except Exception:
            return False

    def build_env(self) -> dict[str, str]:
        env = os.environ.copy()

        if sys.platform == "win32":
            venv_bin = str(self.venv_dir / "Scripts")
        else:
            venv_bin = str(self.venv_dir / "bin")

        env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(self.venv_dir)

        env.pop("PYTHONHOME", None)

        pythonpath_parts = [str(self.project_path), str(self.sandbox_dir)]
        existing = env.get("PYTHONPATH", "")
        if existing:
            pythonpath_parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        return env
