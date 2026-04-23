import asyncio
import logging
from dataclasses import dataclass

from src.app.logger import NullLogger
from src.llm.clients import LLMClient
from src.managers.prompt_engine import PromptEngine
from src.managers.text_parser import TextParser
from src.orchestrator.cleaner_test import TestCleaner
from src.orchestrator.feedback_parser import FeedbackParser
from src.orchestrator.post_processor import PostProcessor
from src.orchestrator.test_runner import TestRunner


@dataclass
class RefineResult:
    code: str | None
    feedback: str
    passed: bool

    @property
    def success(self) -> bool:
        return self.code is not None and self.passed


class TestRefiner:
    def __init__(
        self,
        test_runner: TestRunner,
        llm_client: LLMClient,
        prompt_engine: PromptEngine,
        text_parser: TextParser,
        cleaner: TestCleaner | None = None,
        post_processor: PostProcessor | None = None,
        max_fix_attempts: int = 3,
        logger: logging.Logger | None = None,
    ):
        self.test_runner = test_runner
        self.llm_client = llm_client
        self.prompt_engine = prompt_engine
        self.text_parser = text_parser
        self.cleaner = cleaner or TestCleaner(logger=logger)
        self.post_processor = post_processor
        self.max_fix_attempts = max_fix_attempts
        self.logger = logger or NullLogger()

    async def refine(
        self,
        test_code: str,
        test_filename: str,
        source_code: str,
    ) -> RefineResult:
        passed, feedback = self.test_runner.run_tests(test_code, test_filename=test_filename)

        if passed:
            self.logger.info("[REFINE] Тесты прошли с первого раза")
            final_code = await self.maybe_post_process(test_code, test_filename, source_code)
            return RefineResult(code=final_code, feedback=feedback, passed=True)

        current_code = test_code
        last_feedback = feedback

        self.logger.debug(f"[REFINE] TEST CODE \n{test_code}")
        self.logger.debug(f"[REFINE] FEEDBACK \n{feedback}")

        for attempt in range(1, self.max_fix_attempts + 1):
            clean_feedback = FeedbackParser.extract_failures(last_feedback)
            failed_count, total_count = FeedbackParser.count_failures(last_feedback)
            self.logger.warning(
                f"[REFINE] Провалено {failed_count}/{total_count}, "
                f"починка {attempt}/{self.max_fix_attempts}"
            )

            fixed = await self._fix_via_llm(
                broken_code=current_code,
                feedback=clean_feedback,
                source_code=source_code,
            )

            if fixed is None:
                self.logger.warning("[REFINE] LLM не вернул исправленный код")
                break

            passed, feedback = self.test_runner.run_tests(fixed, test_filename=test_filename)
            last_feedback = feedback

            if passed:
                self.logger.info(f"[REFINE] Тесты прошли после починки (попытка {attempt})")
                final_code = await self.maybe_post_process(
                    fixed,
                    test_filename,
                    source_code,
                )
                return RefineResult(code=final_code, feedback=feedback, passed=True)

            current_code = fixed
            await asyncio.sleep(2)

        self.logger.info("[REFINE] Попытка очистки сломанных тестов")
        cleaned = self.cleaner.clean(current_code, last_feedback)

        passed, feedback = self.test_runner.run_tests(cleaned, test_filename=test_filename)

        if passed:
            self.logger.info("[REFINE] Очищенные тесты прошли")
            final_code = await self.maybe_post_process(
                cleaned,
                test_filename,
                source_code,
            )
            return RefineResult(code=final_code, feedback=feedback, passed=True)

        self.logger.warning("[REFINE] Даже после очистки тесты не проходят")
        return RefineResult(code=None, feedback=last_feedback, passed=False)

    async def maybe_post_process(
        self,
        test_code: str,
        test_filename: str,
        source_code: str,
    ) -> str:
        if self.post_processor is None:
            return test_code

        try:
            result = await self.post_processor.review(test_code, source_code)

            if not result.was_modified:
                self.logger.debug("[REFINE] Пост-обработка: изменений не требуется")
                return test_code

            passed, feedback = self.test_runner.run_tests(
                result.reviewed_code, test_filename=test_filename
            )

            if passed:
                self.logger.info("[REFINE] Пост-обработанные тесты прошли")
                return result.reviewed_code

            self.logger.warning("[REFINE] Пост-обработка сломала тесты, используется оригинал")
            return test_code

        except Exception as e:
            self.logger.error(f"[REFINE] Ошибка пост-обработки: {e}")
            return test_code

    async def _fix_via_llm(
        self,
        broken_code: str,
        feedback: str,
        source_code: str,
    ) -> str | None:
        """Отправляет сломанные тесты в LLM для починки."""
        try:
            recommendations = await self._send_prompt(
                template_name="fix_recommendations.j2",
                code_to_fix=broken_code,
                feedback=feedback,
                source_code=source_code,
            )

            content = await self._send_prompt(
                template_name="fix_tests.j2",
                code_to_fix=broken_code,
                feedback=feedback,
                source_code=source_code,
                recommendations=recommendations,
            )

            fixed_code = self.text_parser.extract_code(content)
            if fixed_code and len(fixed_code.strip()) > 20:
                self.logger.debug("[REFINE] Исправленный код получен")
                return fixed_code

            return None

        except Exception as e:
            self.logger.error(f"[REFINE] Ошибка починки: {e}")
            return None

    async def _send_prompt(self, **template_params) -> str:
        prompt = self.prompt_engine.render(**template_params)
        response = await self.llm_client.send_prompt(prompt)
        return response.content
