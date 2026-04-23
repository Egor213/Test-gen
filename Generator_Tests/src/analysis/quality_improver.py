# src/analysis/quality_improver.py
import logging
from dataclasses import dataclass
from pathlib import Path

from src.analysis.mutation_tester import MutationResult, MutationTester
from src.analysis.test_analysis import TestAnalysisManager
from src.app.logger import NullLogger
from src.llm.clients import LLMClient
from src.managers.prompt_engine import PromptEngine
from src.managers.text_parser import TextParser
from src.orchestrator.test_merger import TestMerger
from src.orchestrator.test_refiner import TestRefiner
from src.orchestrator.test_runner import TestRunner
from src.utils.file_lock import FileLockManager


@dataclass
class CoverageAnalysis:
    coverage_percent: float = 0.0
    total_lines: int = 0
    covered_lines: int = 0
    annotated_body: str = ""

    @property
    def has_uncovered(self) -> bool:
        return "!" in self.annotated_body


@dataclass
class ImprovementReport:
    function_name: str
    initial_coverage: float = 0.0
    final_coverage: float = 0.0
    initial_mutation_score: float = 0.0
    final_mutation_score: float = 0.0

    @property
    def improved(self) -> bool:
        return (
            self.final_coverage > self.initial_coverage
            or self.final_mutation_score > self.initial_mutation_score
        )


class QualityImprover:
    MAX_COVERAGE_IMPROVE_ITERATIONS = 3
    MAX_MUTATION_ITERATIONS = 2
    TARGET_COVERAGE = 70.0
    TARGET_MUTATION_SCORE = 60.0
    GAPS_PER_PROMPT = 3

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_engine: PromptEngine,
        text_parser: TextParser,
        test_runner: TestRunner,
        mutation_tester: MutationTester,
        analysis_manager: TestAnalysisManager,
        test_refiner: TestRefiner,
        test_merger: TestMerger,
        logger: logging.Logger | None = None,
    ):
        self.llm_client = llm_client
        self.prompt_engine = prompt_engine
        self.text_parser = text_parser
        self.test_runner = test_runner
        self.mutation_tester = mutation_tester
        self.analysis_manager = analysis_manager
        self.test_refiner = test_refiner
        self.test_merger = test_merger
        self.logger = logger or NullLogger()
        self._file_lock_manager = FileLockManager()

    async def improve(
        self,
        test_code: str,
        source_code: str,
        source_file: Path,
        function_name: str,
        test_filename: str,
        context: str | None = None,
    ) -> tuple[str, ImprovementReport]:
        report = ImprovementReport(function_name=function_name)
        current_test_code = test_code
        effective_context = context or source_code
        source_file_resolved = Path(source_file).resolve()

        async with self._file_lock_manager.async_lock(source_file_resolved):
            self.logger.info(f"[IMPROVE] Лок захвачен для {source_file_resolved}")

            self.logger.info(f"[IMPROVE] Фаза 1: закрытие coverage для {function_name}")
            current_test_code, report = await self._phase_coverage(
                current_test_code=current_test_code,
                source_file=source_file,
                function_name=function_name,
                test_filename=test_filename,
                context=effective_context,
                report=report,
            )

            self.logger.info(f"[IMPROVE] Фаза 2: мутационное тестирование для {function_name}")
            current_test_code, report = await self._phase_mutation_killing(
                current_test_code=current_test_code,
                source_code=source_code,
                source_file=source_file,
                function_name=function_name,
                test_filename=test_filename,
                context=effective_context,
                report=report,
            )

            self.logger.info(f"[IMPROVE] Лок освобождён для {source_file_resolved}")

        self.logger.info(
            f"[IMPROVE] Завершено для {function_name}: "
            f"coverage {report.initial_coverage:.1f}% → "
            f"{report.final_coverage:.1f}%, "
            f"mutation {report.initial_mutation_score:.1f}% → "
            f"{report.final_mutation_score:.1f}%"
        )

        return current_test_code, report

    async def _phase_coverage(
        self,
        current_test_code: str,
        source_file: Path,
        function_name: str,
        test_filename: str,
        context: str,
        report: ImprovementReport,
    ) -> tuple[str, ImprovementReport]:
        for iteration in range(1, self.MAX_COVERAGE_IMPROVE_ITERATIONS + 1):
            self.logger.info(
                f"[IMPROVE] Coverage improve итерация "
                f"{iteration}/{self.MAX_COVERAGE_IMPROVE_ITERATIONS}"
            )
            analysis = self._run_coverage_analysis(
                current_test_code,
                function_name,
                test_filename,
                source_file,
            )

            if iteration == 1:
                report.initial_coverage = analysis.coverage_percent
            report.final_coverage = analysis.coverage_percent

            if analysis.coverage_percent >= self.TARGET_COVERAGE:
                self.logger.info(
                    f"[IMPROVE] Coverage {analysis.coverage_percent:.1f}% "
                    f">= {self.TARGET_COVERAGE}%"
                )
                break

            if not analysis.has_uncovered:
                self.logger.info("[IMPROVE] Нет непокрытых строк")
                break

            new_tests = await self._generate_coverage_tests(
                annotated_body=analysis.annotated_body,
                context=context,
                existing_tests=current_test_code,
                function_name=function_name,
            )

            if not new_tests:
                self.logger.warning("[IMPROVE] LLM не сгенерировал тесты")
                break

            self.logger.info(f"[IMPROVE] сгенерированы тесты для повышения покрытия")

            refine_result = await self.test_refiner.refine(
                test_code=new_tests,
                test_filename=test_filename,
                source_code=context,
            )

            if not refine_result.success:
                self.logger.warning(
                    f"[IMPROVE] Новые тесты не прошли валидацию " f"(итерация {iteration})"
                )
                continue

            self.logger.info(f"[IMPROVE] refine успешно починил тесты")

            merged = self._merge_validated_methods(
                current_code=current_test_code,
                new_code=refine_result.code,
                test_filename=test_filename,
            )

            if merged == current_test_code:
                self.logger.warning("[IMPROVE] Ни один метод не прошёл merge")
                continue

            new_analysis = self._run_coverage_analysis(
                merged,
                function_name,
                test_filename,
                source_file,
            )

            if new_analysis.coverage_percent > analysis.coverage_percent:
                self.logger.info(
                    f"[IMPROVE] Coverage: {analysis.coverage_percent:.1f}% "
                    f"→ {new_analysis.coverage_percent:.1f}%"
                )
                current_test_code = merged
                report.final_coverage = new_analysis.coverage_percent

                if new_analysis.coverage_percent >= self.TARGET_COVERAGE:
                    self.logger.info(
                        f"[IMPROVE] Coverage "
                        f"{new_analysis.coverage_percent:.1f}% "
                        f">= {self.TARGET_COVERAGE}%"
                    )
                    break
            else:
                self.logger.warning(
                    f"[IMPROVE] Coverage не вырос "
                    f"({new_analysis.coverage_percent:.1f}%), "
                    f"откат изменений"
                )

        return current_test_code, report

    async def _generate_coverage_tests(
        self,
        annotated_body: str,
        context: str,
        existing_tests: str,
        function_name: str,
    ) -> str | None:
        try:
            prompt = self.prompt_engine.render(
                template_name="improve_coverage.j2",
                context=context,
                existing_tests=existing_tests,
                annotated_body=annotated_body,
                function_name=function_name,
            )
            response = await self.llm_client.send_prompt(prompt)
            code = self.text_parser.extract_code(response.content)
            if not code or len(code.strip()) < 20:
                return None
            return code
        except Exception as e:
            self.logger.error(f"[IMPROVE] Ошибка генерации coverage-тестов: {e}")
            return None

    async def _phase_mutation_killing(
        self,
        current_test_code: str,
        source_code: str,
        source_file: Path,
        function_name: str,
        test_filename: str,
        context: str,
        report: ImprovementReport,
    ) -> tuple[str, ImprovementReport]:
        for iteration in range(1, self.MAX_MUTATION_ITERATIONS + 1):
            self.logger.info(
                f"[IMPROVE] Mutation итерация " f"{iteration}/{self.MAX_MUTATION_ITERATIONS}"
            )

            mutation_result = self.mutation_tester.run_mutation_testing(
                source_code=source_code,
                source_file=source_file,
                test_code=current_test_code,
                test_filename=test_filename,
                function_name=self._extract_short_name(function_name),
                _lock_acquired=True,
            )

            if iteration == 1:
                report.initial_mutation_score = mutation_result.score
            report.final_mutation_score = mutation_result.score

            if mutation_result.score >= self.TARGET_MUTATION_SCORE:
                self.logger.info(
                    f"[IMPROVE] Mutation score {mutation_result.score:.1f}% "
                    f">= {self.TARGET_MUTATION_SCORE}%, достаточно"
                )
                break

            survived = mutation_result.survived_mutants
            if not survived:
                self.logger.info("[IMPROVE] Нет выживших мутантов")
                break

            self.logger.info(
                f"[IMPROVE] {len(survived)} мутантов выжили, " f"генерируем убивающие тесты"
            )

            killer_tests = await self._generate_mutation_killers(
                survived_mutants=survived,
                context=context,
                function_name=function_name,
                existing_tests=current_test_code,
                mutation_result=mutation_result,
            )

            if not killer_tests:
                self.logger.warning("[IMPROVE] LLM не сгенерировал killer-тесты")
                break

            refine_result = await self.test_refiner.refine(
                test_code=killer_tests,
                test_filename=test_filename,
                source_code=context,
            )

            if not refine_result.success:
                self.logger.warning(
                    f"[IMPROVE] Killer-тесты не прошли валидацию " f"(итерация {iteration})"
                )
                continue

            merged = self._merge_validated_methods(
                current_code=current_test_code,
                new_code=refine_result.code,
                test_filename=test_filename,
            )

            if merged == current_test_code:
                self.logger.warning("[IMPROVE] Ни один killer не прошёл merge")
                continue

            new_mutation = self.mutation_tester.run_mutation_testing(
                source_code=source_code,
                source_file=source_file,
                test_code=merged,
                test_filename=test_filename,
                function_name=self._extract_short_name(function_name),
                _lock_acquired=True,
            )

            if new_mutation.score > mutation_result.score:
                self.logger.info(
                    f"[IMPROVE] Mutation score: "
                    f"{mutation_result.score:.1f}% "
                    f"→ {new_mutation.score:.1f}%"
                )
                current_test_code = merged
                report.final_mutation_score = new_mutation.score

                if new_mutation.score >= self.TARGET_MUTATION_SCORE:
                    self.logger.info(
                        f"[IMPROVE] Mutation score "
                        f"{new_mutation.score:.1f}% "
                        f">= {self.TARGET_MUTATION_SCORE}%, достаточно"
                    )
                    break
            else:
                self.logger.warning(
                    f"[IMPROVE] Mutation score не вырос " f"({new_mutation.score:.1f}%), откат"
                )

        return current_test_code, report

    async def _generate_mutation_killers(
        self,
        survived_mutants: list,
        context: str,
        function_name: str,
        existing_tests: str,
        mutation_result: MutationResult,
    ) -> str | None:
        mutants_description = self.mutation_tester.format_survived_for_prompt(mutation_result)
        try:
            prompt = self.prompt_engine.render(
                template_name="improve_kill_mutants.j2",
                function_name=function_name,
                context=context,
                existing_tests=existing_tests,
                mutants_description=mutants_description,
                survived_count=len(survived_mutants),
            )
            response = await self.llm_client.send_prompt(prompt)
            code = self.text_parser.extract_code(response.content)
            if not code or len(code.strip()) < 20:
                return None
            return code
        except Exception as e:
            self.logger.error(f"Ошибка генерации mutation-killer тестов: {e}")
            return None

    def _merge_validated_methods(
        self,
        current_code: str,
        new_code: str,
        test_filename: str,
    ) -> str:
        candidates = self.test_merger.extract_new_methods(current_code, new_code)

        if not candidates:
            self.logger.info("[MERGE] Нет новых методов для добавления")
            return current_code

        self.logger.info(f"[MERGE] Кандидатов на добавление: {len(candidates)}")

        added = 0
        for method in candidates:
            candidate_code = self.test_merger.inject_single_method(
                existing_code=current_code,
                new_code=new_code,
                method=method,
            )

            passed, _ = self.test_runner.run_tests(candidate_code, test_filename=test_filename)

            if passed:
                current_code = candidate_code
                added += 1
                self.logger.debug(f"[MERGE] ✓ {method.name}")
            else:
                self.logger.debug(f"[MERGE] ✗ {method.name} — не прошёл валидацию")

        self.logger.info(f"[MERGE] Добавлено {added}/{len(candidates)}")
        return current_code

    def _run_coverage_analysis(
        self,
        test_code: str,
        function_name: str,
        test_filename: str,
        source_file: Path,
    ) -> CoverageAnalysis:
        try:
            self.analysis_manager.run_coverage(
                test_code=test_code,
                test_function_name=function_name,
                file_path=str(source_file),
                test_filename=test_filename,
            )

            coverage_data: dict = self.analysis_manager.coverage_data.get(function_name)
            if coverage_data is None:
                return CoverageAnalysis()

            return CoverageAnalysis(
                coverage_percent=coverage_data.get("coverage_percent", 0.0),
                total_lines=coverage_data.get("total_lines", 0),
                covered_lines=coverage_data.get("covered_lines", 0),
                annotated_body=coverage_data.get("annotated_body", ""),
            )

        except Exception as e:
            self.logger.error(f"[IMPROVE] Ошибка coverage: {e}")
            return CoverageAnalysis()

    def _extract_short_name(self, function_name: str) -> str:
        if "::" in function_name:
            return function_name.split("::")[-1]
        return function_name
