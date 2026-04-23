import asyncio
import logging
import re
from collections import deque
from pathlib import Path

from src.analysis.mutation_tester import MutationTester
from src.analysis.quality_improver import ImprovementReport, QualityImprover
from src.analysis.report_generator import ReportGenerator
from src.analysis.test_analysis import TestAnalysisManager
from src.app.logger import NullLogger
from src.entity.pipeline import FunctionTarget, FunctionTestResult
from src.llm.clients import LLMClient
from src.managers.config import Config
from src.managers.console import ConsoleManager
from src.managers.context_manager import ContextManager
from src.managers.project_indexer import ProjectIndexer
from src.managers.prompt_engine import PromptEngine
from src.managers.text_parser import TextParser
from src.orchestrator.cleaner_test import TestCleaner
from src.orchestrator.post_processor import PostProcessor
from src.orchestrator.test_merger import GeneratedTest, TestMerger
from src.orchestrator.test_refiner import TestRefiner
from src.orchestrator.test_runner import TestRunner
from src.utils.path_filter import PathFilter
from src.utils.workspace_helper import WorkspaceHelper


class PipelineOrchestrator:
    def __init__(
        self,
        config: Config | None = None,
        console: ConsoleManager | None = None,
        logger: logging.Logger | None = None,
    ):
        self.logger = logger or NullLogger()
        self.console = console or ConsoleManager()
        self.config = config or Config()
        self.max_gen_test_retry = getattr(self.console.args, "max_generate_retries", 3)
        self.max_fix_attempts = getattr(self.console.args, "max_fix_attempts", 4)
        self.target_line_coverage = getattr(self.console.args, "target_line_coverage", 60)

        self._apply_console_args()

        self.project_indexer = ProjectIndexer(self.console.args.project)
        self.context_manager = ContextManager(self.project_indexer)
        self.llm_client = LLMClient(config)
        self.text_parser = TextParser(self.console.args.project)
        self.prompt_engine = PromptEngine(templates_dir="prompts")
        self.path_filter = PathFilter(
            self.project_indexer,
            target_dir=getattr(self.console.args, "target_dir", None),
            target_function=getattr(self.console.args, "target_function", None),
            target_class=getattr(self.console.args, "target_class", None),
            target_file=getattr(self.console.args, "target_file", None),
        )

        self.workspace_helper = WorkspaceHelper(
            project_path=self.project_indexer.project_path,
            logger=self.logger,
        )

        self.test_runner = TestRunner(
            project_path=self.project_indexer.project_path,
            workspace_helper=self.workspace_helper,
            logger=self.logger,
        )

        self.post_processor = PostProcessor(
            llm_client=self.llm_client,
            prompt_engine=self.prompt_engine,
            text_parser=self.text_parser,
            logger=self.logger,
        )

        self.cleaner_test = TestCleaner(logger=self.logger)

        self.test_merger = TestMerger(
            project_path=self.project_indexer.project_path,
            tests_dir=getattr(self.console.args, "tests_dir", "tests"),
            logger=self.logger,
        )

        self.analysis_manager = TestAnalysisManager(
            project_root=self.project_indexer.project_path,
            tests_path=getattr(self.console.args, "tests_dir", "tests"),
            workspace_helper=self.workspace_helper,
            logger=self.logger,
        )

        mutation_tester = MutationTester(
            project_root=self.project_indexer.project_path,
            workspace_helper=self.workspace_helper,
            test_runner=self.test_runner,
            logger=self.logger,
        )

        self.test_refiner = TestRefiner(
            test_runner=self.test_runner,
            llm_client=self.llm_client,
            prompt_engine=self.prompt_engine,
            text_parser=self.text_parser,
            cleaner=self.cleaner_test,
            post_processor=self.post_processor,
            max_fix_attempts=self.max_fix_attempts,
            logger=self.logger,
        )

        self.quality_improver = QualityImprover(
            llm_client=self.llm_client,
            prompt_engine=self.prompt_engine,
            text_parser=self.text_parser,
            test_runner=self.test_runner,
            mutation_tester=mutation_tester,
            analysis_manager=self.analysis_manager,
            test_refiner=self.test_refiner,
            test_merger=self.test_merger,
            logger=self.logger,
        )

        self.report_generator = ReportGenerator(
            project_root=self.project_indexer.project_path,
            workspace_helper=self.workspace_helper,
            mutation_tester=mutation_tester,
            logger=self.logger,
            enable_reliability=True,
            enable_mutation=True,
        )

        self._results: list[FunctionTestResult] = []
        self.written_test_paths: list[Path] = []

        self.logger.info("[ORCHESTRATOR] PipelineOrchestrator инициализирован")

    def _apply_console_args(self):
        args = self.console.args

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        overrides = {
            "model": args.model,
            "temperature": args.temperature,
            "max_generate_retries": args.max_generate_retries,
            "max_fix_attempts": args.max_fix_attempts,
            "max_async_workers": args.max_async_workers,
            "target_line_coverage": args.target_line_coverage,
        }
        for attr, value in overrides.items():
            if value is not None:
                setattr(self.config.ai, attr, value)
                self.logger.debug(f"[ORCHESTRATOR] Конфиг переопределён: {attr}={value}")

    async def close_llm(self):
        if self.llm_client:
            await self.llm_client.close()
            self.logger.info("[ORCHESTRATOR] LLM-клиент закрыт")

    async def _send_prompt(self, **template_params) -> str:
        prompt = self.prompt_engine.render(**template_params)
        self.logger.debug(f"[ORCHESTRATOR] Отправка промпта: {prompt}")
        response = await self.llm_client.send_prompt(prompt)
        return response.content

    async def _send_prompt_raw(self, prompt: str) -> str:
        response = await self.llm_client.send_prompt(prompt)
        return response.content

    def _pick_code_template(self) -> str:
        return "generate_code.j2"

    def _pick_fix_template(self) -> str:
        return "fix_tests.j2"

    def _pick_recommendations_template(self) -> str:
        return "fix_recommendations.j2"

    def _build_code_prompt(
        self,
        target: FunctionTarget,
        context: str | None,
    ) -> str:
        effective_context = context or target.info.code
        template_name = self._pick_code_template()

        base_params = dict(
            template_name=template_name,
            method_name=target.function_name,
            path_to_function=self.project_indexer.relative_path(target.file_path),
            path_to_tests=self.project_indexer.relative_path(target.test_path),
            context=effective_context,
        )

        return self.prompt_engine.render(
            **base_params,
            class_name=target.file_path.stem.capitalize(),
        )

    async def _generate_test_code(self, prompt: str) -> str | None:
        max_retry_extract = 3
        for attempt in range(1, max_retry_extract + 1):
            self.logger.debug(
                f"[ORCHESTRATOR] Извлечение кода, попытка {attempt}/{max_retry_extract}"
            )
            try:
                content = await self._send_prompt_raw(prompt)
                return self.text_parser.extract_code(content)
            except Exception as e:
                self.logger.warning(
                    f"[ORCHESTRATOR] Ошибка извлечения кода (попытка {attempt}): {e}"
                )
                await asyncio.sleep(2)

        self.logger.error("[ORCHESTRATOR] Не удалось извлечь код тестов из ответа LLM")
        return None

    def _collect_context(self, target: FunctionTarget, dependency_depth: int = -1) -> str | None:
        try:
            context = self.context_manager.collect_context(
                target.full_path, dependency_depth=dependency_depth
            )
            self.logger.info(f"[ORCHESTRATOR] Контекст собран для {target.function_name}")
            return context
        except Exception as e:
            self.logger.error(
                f"[ORCHESTRATOR] Не удалось собрать контекст для {target.function_name}: {e}"
            )
            return None

    def _write_tests(self, code: str, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        self.written_test_paths.append(path)

    async def _build_and_generate_test_code(
        self,
        target: FunctionTarget,
        context: str | None = None,
    ) -> str | None:
        prompt = self._build_code_prompt(target, context)
        test_code = await self._generate_test_code(prompt)
        return test_code

    async def _process_function(self, target: FunctionTarget) -> FunctionTestResult:
        result = FunctionTestResult(target=target)

        for step in range(1, self.max_gen_test_retry + 1):
            context = self._collect_context(target, dependency_depth=step)
            self.logger.info(
                f"[ORCHESTRATOR] Генерация тестов для {target.function_name}, "
                f"попытка {step}/{self.max_gen_test_retry}"
            )

            try:
                test_code = await self._build_and_generate_test_code(target, context)
                if not test_code:
                    continue

                source_code = context or target.info.code
                refine_result = await self.test_refiner.refine(
                    test_code=test_code,
                    test_filename=target.test_filename,
                    source_code=source_code,
                )

                if not refine_result.success:
                    continue

                final_code, report = await self._analyze_and_improve(
                    refine_result.code, target, context
                )
                if report.final_coverage < self.target_line_coverage:
                    if result.line_coverage is None or report.final_coverage > result.line_coverage:
                        result.line_coverage = report.final_coverage
                        result.test_code = final_code
                    continue

                result.line_coverage = report.final_coverage
                result.test_code = final_code

                self.logger.info(f"[ORCHESTRATOR] ✓ Тесты готовы для {target.function_name}")
                break

            except Exception as e:
                self.logger.error(
                    f"[ORCHESTRATOR] Непредвиденная ошибка при обработке {target.function_name}: {e}"
                )

        return result

    async def _analyze_and_improve(
        self,
        test_code: str,
        target: FunctionTarget,
        context: str | None,
    ) -> tuple[str, ImprovementReport]:
        source_code = self._read_source_file(target.file_path)
        if source_code is None:
            self.logger.warning(
                f"[ORCHESTRATOR] Не удалось прочитать {target.file_path}, пропуск анализа"
            )
            return test_code, ImprovementReport(
                improved=False, initial_coverage=0, final_coverage=0
            )

        try:
            improved_code, report = await self.quality_improver.improve(
                test_code=test_code,
                source_code=source_code,
                source_file=target.file_path,
                function_name=target.function_name,
                test_filename=target.test_filename,
                context=context,
            )

            if report.improved:
                self.logger.info(
                    f"[ORCHESTRATOR] {target.function_name} улучшен: "
                    f"coverage {report.initial_coverage:.1f}% "
                    f"→ {report.final_coverage:.1f}%, "
                    f"mutation {report.initial_mutation_score:.1f}% "
                    f"→ {report.final_mutation_score:.1f}% "
                )
            else:
                self.logger.info(
                    f"[ORCHESTRATOR] {target.function_name}: улучшение не требуется или невозможно"
                )

            return improved_code, report

        except Exception as e:
            self.logger.error(
                f"[ORCHESTRATOR] Ошибка при улучшении тестов для {target.function_name}: {e}"
            )
            return test_code

    def _read_source_file(self, file_path: Path) -> str | None:
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error(f"[ORCHESTRATOR] Ошибка чтения файла {file_path}: {e}")
            return None

    def _resolve_test_path(self, source_file: Path) -> Path:
        return self.test_merger.resolve_test_path(source_file)

    def _discover_targets(self) -> deque[FunctionTarget]:
        targets: deque[FunctionTarget] = deque()

        for function_path, function_info in self.project_indexer.functions.items():
            if (
                not self.path_filter.should_test(
                    self.project_indexer.relative_path(function_path),
                )
                or "abstractmethod" in function_info.decorators
            ):
                continue

            target = FunctionTarget.from_index_entry(function_path, function_info)
            target.test_path = self._resolve_test_path(target.file_path)
            targets.append(target)

        return targets

    async def _worker(self, queue: deque[FunctionTarget]):
        while queue:
            element = queue.popleft()
            self.logger.info(
                f"[ORCHESTRATOR] Обработка: {element.function_name} ({element.file_path})"
            )
            result = await self._process_function(element)
            self._results.append(result)
            self.logger.info(f"[ORCHESTRATOR] Осталось обработать: {len(queue)} элементов очереди")

    async def _process_targets(self, targets: deque[FunctionTarget]):
        workers = [
            asyncio.create_task(self._worker(targets))
            for _ in range(min(len(targets), self.config.app.max_async_workers))
        ]
        await asyncio.gather(*workers, return_exceptions=True)

    def _merge_and_write_results(self):
        successful = [r for r in self._results if r.test_code]

        if not successful:
            self.logger.warning("[ORCHESTRATOR] Нет успешно сгенерированных тестов для записи")
            return

        generated_tests = [
            GeneratedTest(
                function_name=r.target.function_name,
                source_file=r.target.file_path,
                test_code=r.test_code,
                test_path=r.target.test_path,
            )
            for r in successful
        ]

        merged = self.test_merger.merge_tests(generated_tests)

        total_functions = len(successful)
        total_files = 0

        for test_path, merged_code in merged.items():
            test_filename = test_path.name
            passed, feedback = self.test_runner.run_tests(
                merged_code,
                test_filename=test_filename,
            )

            if passed:
                self._write_tests(merged_code, test_path)
                self.logger.info(f"[ORCHESTRATOR] ✓ Тесты записаны: {test_path}")
                total_files += 1
            else:
                self.logger.warning(
                    f"[ORCHESTRATOR] Объединённые тесты не прошли валидацию: {test_path}\n"
                    f"Feedback: {feedback[:500]}"
                )

                file_tests = [
                    t
                    for t in generated_tests
                    if self.test_merger.resolve_test_path(t.source_file) == test_path
                ]
                written = self._fallback_write_tests(file_tests, test_path)
                total_files += written

        self._create_init_files()
        self.written_test_paths.clear()
        self.logger.info(f"[ORCHESTRATOR] Итого: {total_functions} функций → {total_files} файлов")

    def _create_init_files(self):
        tests_root = self.project_indexer.project_path / getattr(
            self.console.args, "tests_dir", "tests"
        )
        for test_path in self.written_test_paths:
            current = test_path.parent
            while current != tests_root and current != current.parent:
                init_file = current / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
                    self.logger.debug(f"[ORCHESTRATOR] Создан {init_file}")
                current = current.parent
        root_init = tests_root / "__init__.py"
        if not root_init.exists():
            root_init.touch()
            self.logger.debug(f"[ORCHESTRATOR] Создан {root_init}")

    async def _try_refine_merged(self, merged_code: str, test_filename: str) -> str | None:
        """Пытаемся починить объединённые тесты через refiner."""
        try:
            refine_result = await self.test_refiner.refine(
                test_code=merged_code,
                test_filename=test_filename,
                source_code="",
            )
            if refine_result.success:
                return refine_result.code
        except Exception as e:
            self.logger.warning(f"[ORCHESTRATOR] Не удалось починить объединённые тесты: {e}")
        return None

    def _fallback_write_tests(
        self,
        tests: list[GeneratedTest],
        original_test_path: Path,
    ) -> int:
        """Фоллбэк: разделяем тесты, находим рабочие и проблемные."""
        self.logger.info(
            f"[ORCHESTRATOR] Фоллбэк: разделение {len(tests)} тестов для {original_test_path}"
        )

        if len(tests) <= 1:
            for test in tests:
                self._write_tests(test.test_code, original_test_path)
                self.logger.warning(
                    f"[ORCHESTRATOR] ⚠ Записан непроходящий тест: {original_test_path}"
                )
            return 1 if tests else 0

        passing_tests: list[GeneratedTest] = []
        failing_tests: list[GeneratedTest] = []

        for test in tests:
            test_filename = original_test_path.name
            passed, _ = self.test_runner.run_tests(
                test.test_code,
                test_filename=test_filename,
            )
            if passed:
                passing_tests.append(test)
            else:
                failing_tests.append(test)
                self.logger.warning(
                    f"[ORCHESTRATOR] ✗ Тест для {test.function_name} не прошёл индивидуально"
                )

        written = 0

        if passing_tests:
            written += self._merge_and_write_passing(passing_tests, original_test_path)

        if failing_tests:
            written += self._write_failing_separately(failing_tests, original_test_path)

        return written

    def _merge_and_write_passing(
        self,
        passing_tests: list[GeneratedTest],
        test_path: Path,
    ) -> int:
        """Объединяем проходящие тесты и записываем."""
        if len(passing_tests) == 1:
            self._write_tests(passing_tests[0].test_code, test_path)
            self.logger.info(f"[ORCHESTRATOR] ✓ Записан единственный проходящий тест: {test_path}")
            return 1

        merged = self.test_merger._merge_test_codes([t.test_code for t in passing_tests])
        test_filename = test_path.name

        passed, feedback = self.test_runner.run_tests(merged, test_filename=test_filename)

        if passed:
            self._write_tests(merged, test_path)
            self.logger.info(
                f"[ORCHESTRATOR] ✓ Объединены {len(passing_tests)} проходящих тестов: {test_path}"
            )
            return 1

        self.logger.warning(
            f"[ORCHESTRATOR] Проходящие тесты конфликтуют при объединении, "
            f"поиск совместимых групп..."
        )
        return self._find_compatible_groups(passing_tests, test_path)

    def _find_compatible_groups(
        self,
        tests: list[GeneratedTest],
        base_test_path: Path,
    ) -> int:
        """Инкрементально добавляем тесты, проверяя совместимость."""
        groups: list[list[GeneratedTest]] = []
        current_group: list[GeneratedTest] = []
        current_merged: str = ""

        for test in tests:
            if not current_group:
                current_group = [test]
                current_merged = test.test_code
                continue

            candidate_codes = [t.test_code for t in current_group] + [test.test_code]
            candidate_merged = self.test_merger._merge_test_codes(candidate_codes)

            passed, _ = self.test_runner.run_tests(
                candidate_merged,
                test_filename=base_test_path.name,
            )

            if passed:
                current_group.append(test)
                current_merged = candidate_merged
            else:
                groups.append(current_group)
                current_group = [test]
                current_merged = test.test_code

        if current_group:
            groups.append(current_group)

        written = 0
        for i, group in enumerate(groups):
            if i == 0:
                path = base_test_path
            else:
                stem = base_test_path.stem
                suffix = base_test_path.suffix
                path = base_test_path.parent / f"{stem}_part{i + 1}{suffix}"

            if len(group) == 1:
                code = group[0].test_code
            else:
                code = self.test_merger._merge_test_codes([t.test_code for t in group])

            self._write_tests(code, path)
            func_names = [t.function_name for t in group]
            self.logger.info(
                f"[ORCHESTRATOR] ✓ Группа {i + 1}: {len(group)} тестов → {path} "
                f"({', '.join(func_names)})"
            )
            written += 1

        return written

    def _write_failing_separately(
        self,
        failing_tests: list[GeneratedTest],
        base_test_path: Path,
    ) -> int:
        """Записываем проблемные тесты в отдельные файлы с суффиксом."""
        written = 0

        for test in failing_tests:
            stem = base_test_path.stem
            suffix = base_test_path.suffix
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", test.function_name)
            path = base_test_path.parent / f"{stem}_{safe_name}_failing{suffix}"

            self._write_tests(test.test_code, path)
            self.logger.warning(
                f"[ORCHESTRATOR] ⚠ Непроходящий тест записан отдельно: {path} "
                f"(функция: {test.function_name})"
            )
            written += 1

        return written

    async def _run_analysis(self, tests_dir: str = "tests") -> None:
        self.logger.info("[ORCHESTRATOR] Запуск анализа сгенерированных тестов")

        tests_path = self.project_indexer.project_path / tests_dir
        if not tests_path.exists():
            self.logger.warning(f"[ORCHESTRATOR] Директория тестов не найдена: {tests_path}")
            return

        test_files, source_files = self.report_generator.collect_files(
            test_dir=tests_path,
            source_dirs=[self.project_indexer.project_path],
        )
        if not test_files:
            self.logger.warning("[ORCHESTRATOR] Нет тестовых файлов для анализа")
            return

        report = self.report_generator.generate(
            test_files=test_files,
            source_files=source_files,
        )

        html_path, cov_html_dir, cov_annotate_dir = self.report_generator.save_report(
            report,
            test_files=test_files,
            source_files=source_files,
            output_dir=self.project_indexer.project_path,
        )

        self.logger.info(f"[ORCHESTRATOR] HTML-отчёт: {html_path}")
        self.logger.info(f"[ORCHESTRATOR] HTML-отчёт покрытия: {cov_html_dir}")
        self.logger.info(f"[ORCHESTRATOR] Аннотированные файлы покрытия: {cov_annotate_dir}")

    async def orchestrate_pipeline(self):
        self.logger.info(
            f"[ORCHESTRATOR] Пайплайн запущен с {self.config.app.max_async_workers} воркерами"
        )
        self.project_indexer.analyze()

        targets: deque[FunctionTarget] = self._discover_targets()
        if not targets:
            self.logger.warning("[ORCHESTRATOR] Не найдено функций для генерации тестов")
            if self.path_filter.has_custom_filter:
                self.logger.info(
                    "[ORCHESTRATOR] Проверьте параметры --target-dir / --target-function / --target-class"
                )
            await self.close_llm()
            return

        self.logger.info(f"[ORCHESTRATOR] Найдено {len(targets)} функций для генерации тестов")

        await self._process_targets(targets)

        self._merge_and_write_results()

        tests_dir = getattr(self.console.args, "tests_dir", "tests")
        await self._run_analysis(tests_dir=tests_dir)

        await self.close_llm()
        self.logger.info("[ORCHESTRATOR] Пайплайн завершён")
