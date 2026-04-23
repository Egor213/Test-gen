# src/analysis/mutation_tester.py
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.analysis.mutator import Mutant, MutationType, Mutator
from src.app.logger import NullLogger
from src.orchestrator.test_runner import TestRunner
from src.utils.file_lock import FileLockManager
from src.utils.workspace_helper import WorkspaceHelper


@dataclass
class MutationResult:
    total_mutants: int = 0
    killed: int = 0
    survived: int = 0
    mutants: list[Mutant] = field(default_factory=list)
    function_name: str = ""
    source_file: str = ""
    duration_seconds: float = 0.0

    @property
    def score(self) -> float:
        if self.total_mutants == 0:
            return 100.0
        return self.killed / self.total_mutants * 100

    @property
    def survived_mutants(self) -> list[Mutant]:
        return [m for m in self.mutants if m.survived]

    @property
    def killed_mutants(self) -> list[Mutant]:
        return [m for m in self.mutants if m.killed]

    @property
    def timeout_mutants(self) -> list[Mutant]:
        return [m for m in self.mutants if not m.killed and not m.survived]

    def to_dict(self) -> dict:
        """Сериализация для JSON и HTML-рендерера."""
        return {
            "function_name": self.function_name,
            "source_file": self.source_file,
            "total_mutants": self.total_mutants,
            "killed": self.killed,
            "survived": self.survived,
            "timeout": len(self.timeout_mutants),
            "score": round(self.score, 1),
            "duration_seconds": round(self.duration_seconds, 2),
            "mutants": [
                {
                    "id": m.id,
                    "mutation_type": m.mutation_type.value,
                    "line_number": m.line_number,
                    "description": m.description,
                    "status": m.status,
                    "status_icon": m.status_icon,
                    "diff_lines": m.get_diff_lines(context_lines=3),
                }
                for m in self.mutants
            ],
        }


class MutationTester:
    ACCEPTABLE_SCORE = 60.0
    BACKUP_SUFFIX = ".mutation_backup"

    def __init__(
        self,
        project_root: Path,
        workspace_helper: WorkspaceHelper,
        test_runner: TestRunner,
        logger: logging.Logger | None = None,
    ):
        self.project_root = project_root.resolve()
        self.workspace_helper = workspace_helper
        self.test_runner = test_runner
        self.logger = logger or NullLogger()
        self.mutator = Mutator(logger=self.logger)
        self._file_lock_manager = FileLockManager()

    def run_mutation_testing(
        self,
        source_code: str,
        source_file: Path,
        test_code: str,
        test_filename: str,
        function_name: str,
        _lock_acquired: bool = False,
    ) -> MutationResult:
        if _lock_acquired:
            return self._run_mutation_testing_impl(
                source_code=source_code,
                source_file=source_file,
                test_code=test_code,
                test_filename=test_filename,
                function_name=function_name,
            )

        source_file_resolved = Path(source_file).resolve()
        with self._file_lock_manager.lock(source_file_resolved):
            return self._run_mutation_testing_impl(
                source_code=source_code,
                source_file=source_file,
                test_code=test_code,
                test_filename=test_filename,
                function_name=function_name,
            )

    def _run_mutation_testing_impl(
        self,
        source_code: str,
        source_file: Path,
        test_code: str,
        test_filename: str,
        function_name: str,
    ) -> MutationResult:
        import time

        self.logger.info(f"[MUTATION] Запуск для {function_name}")
        start_time = time.time()

        mutants = self.mutator.generate_mutants(source_code, function_name)
        if not mutants:
            self.logger.info("[MUTATION] Мутанты не сгенерированы")
            return MutationResult(function_name=function_name, source_file=str(source_file))

        for m in mutants:
            m.function_name = function_name

        result = MutationResult(
            total_mutants=len(mutants),
            mutants=mutants,
            function_name=function_name,
            source_file=str(source_file),
        )

        source_file_resolved = Path(source_file).resolve()
        original_content = self._read_original(source_file_resolved)
        if original_content is None:
            return result

        backup_path = source_file_resolved.with_suffix(
            source_file_resolved.suffix + self.BACKUP_SUFFIX
        )
        if not self._create_backup(source_file_resolved, backup_path):
            return result

        try:
            for i, mutant in enumerate(mutants):
                self.logger.debug(f"[MUTATION] Мутант {i + 1}/{len(mutants)}: {mutant.description}")
                try:
                    self._test_single_mutant(
                        mutant=mutant,
                        source_file=source_file_resolved,
                        test_code=test_code,
                        test_filename=test_filename,
                        result=result,
                    )
                except Exception as e:
                    self.logger.error(f"[MUTATION] Ошибка мутанта {mutant.id}: {e}")
                finally:
                    self._restore_file(source_file_resolved, original_content)
        finally:
            self._restore_file(source_file_resolved, original_content)
            self._verify_and_cleanup_backup(source_file_resolved, backup_path, original_content)

        result.duration_seconds = time.time() - start_time

        self.logger.info(
            f"[MUTATION] Завершено: score={result.score:.1f}%, "
            f"killed={result.killed}/{result.total_mutants}, "
            f"survived={result.survived}"
        )
        return result

    def _create_backup(self, source_file: Path, backup_path: Path) -> bool:
        try:
            shutil.copy2(source_file, backup_path)
            self.logger.debug(f"[MUTATION] Бэкап создан: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(
                f"[MUTATION] Не удалось создать бэкап: {e}. " f"Мутационное тестирование отменено."
            )
            return False

    def _verify_and_cleanup_backup(
        self,
        source_file: Path,
        backup_path: Path,
        original_content: str,
    ) -> None:
        try:
            current_content = source_file.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error(
                f"[MUTATION] Не удалось прочитать {source_file} "
                f"для верификации: {e}. "
                f"Бэкап сохранён: {backup_path}"
            )
            return

        if current_content == original_content:
            try:
                backup_path.unlink()
                self.logger.debug(f"[MUTATION] Бэкап удалён: {backup_path}")
            except Exception as e:
                self.logger.warning(f"[MUTATION] Не удалось удалить бэкап: {e}")
        else:
            self.logger.error(
                f"[MUTATION] Файл {source_file} повреждён после мутаций! "
                f"Восстанавливаю из бэкапа..."
            )
            try:
                shutil.copy2(backup_path, source_file)
                restored = source_file.read_text(encoding="utf-8")
                if restored == original_content:
                    self.logger.info("[MUTATION] Файл восстановлен из бэкапа")
                    backup_path.unlink()
                else:
                    self.logger.error(
                        f"[MUTATION] КРИТИЧНО: восстановление не удалось. "
                        f"Бэкап сохранён: {backup_path}"
                    )
            except Exception as e:
                self.logger.error(
                    f"[MUTATION] КРИТИЧНО: не удалось восстановить "
                    f"из бэкапа: {e}. "
                    f"Ручное восстановление: "
                    f"cp {backup_path} {source_file}"
                )

    def _read_original(self, source_file: Path) -> str | None:
        try:
            return source_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.logger.error(f"[MUTATION] Файл не найден: {source_file}")
            return None
        except Exception as e:
            self.logger.error(f"[MUTATION] Не удалось прочитать {source_file}: {e}")
            return None

    def _test_single_mutant(
        self,
        mutant: Mutant,
        source_file: Path,
        test_code: str,
        test_filename: str,
        result: MutationResult,
    ) -> None:
        try:
            source_file.write_text(mutant.mutated_code, encoding="utf-8")
        except Exception as e:
            self.logger.error(f"[MUTATION] Не удалось записать мутант в {source_file}: {e}")
            return

        passed, feedback = self.test_runner.run_tests(
            test_code=test_code,
            test_filename=test_filename,
            fast=True,
        )

        if not passed:
            if "timeout" in feedback.lower():
                self.logger.debug(f"[MUTATION] ⏱ Мутант {mutant.id} TIMEOUT")
            else:
                mutant.killed = True
                result.killed += 1
                self.logger.debug(f"[MUTATION] ✓ Мутант {mutant.id} УБИТ")
        else:
            mutant.survived = True
            result.survived += 1
            self.logger.debug(f"[MUTATION] ✗ Мутант {mutant.id} ВЫЖИЛ")

    def _restore_file(self, path: Path, content: str) -> None:
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            self.logger.error(f"[MUTATION] Не удалось восстановить файл {path}: {e}")

    def format_survived_for_prompt(self, result: MutationResult) -> str:
        if not result.survived_mutants:
            return "All mutants killed — tests are strong enough."

        lines = [
            f"Mutation Score: {result.score:.1f}% "
            f"({result.killed}/{result.total_mutants} mutants killed)\n",
            "Survived mutants (tests DID NOT detect these changes):\n",
        ]

        for m in result.survived_mutants:
            lines.append(f"  - [{m.mutation_type.value}] {m.description}")
            hint = self._get_killing_hint(m)
            if hint:
                lines.append(f"    Hint: {hint}")

        return "\n".join(lines)

    def _get_killing_hint(self, mutant: Mutant) -> str:
        hints = {
            MutationType.COMPARISON_SWAP: (
                "Test the boundary value. If original is x > 0, test x=0."
            ),
            MutationType.BOOLEAN_SWAP: (
                "Assert the exact boolean value: " "assert result is True, not just assert result."
            ),
            MutationType.ARITHMETIC_SWAP: (
                "Use numbers where + and - give different results " "(e.g. 3+2=5 but 3-2=1)."
            ),
            MutationType.RETURN_NONE: (
                "Assert return value is NOT None and equals " "a specific expected value."
            ),
            MutationType.NEGATE_CONDITION: (
                "Write two tests: one for True branch, one for False. " "Assert different results."
            ),
            MutationType.CONSTANT_SWAP: (
                "Use input where the specific constant affects the result."
            ),
        }
        return hints.get(mutant.mutation_type, "")
