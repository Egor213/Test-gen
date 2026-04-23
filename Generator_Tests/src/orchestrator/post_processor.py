import logging
import re
from dataclasses import dataclass

from src.app.logger import NullLogger
from src.llm.clients import LLMClient
from src.managers.prompt_engine import PromptEngine
from src.managers.text_parser import TextParser
from src.utils.import_cleaner import ImportCleaner


@dataclass
class PostProcessResult:
    reviewed_code: str
    was_modified: bool


class PostProcessor:
    MAX_REMOVAL_RATIO = 0.4
    MAX_TEST_REMOVAL_RATIO = 0.35

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_engine: PromptEngine,
        text_parser: TextParser,
        logger: logging.Logger | None = None,
    ):
        self.llm_client = llm_client
        self.prompt_engine = prompt_engine
        self.text_parser = text_parser
        self.logger = logger or NullLogger()
        self.import_cleaner = ImportCleaner(logger=self.logger)

    async def review(self, test_code: str, source_code: str) -> PostProcessResult:
        self.logger.info("Запуск пост-обработки тестов через LLM...")

        try:
            reviewed_code = await self._send_review(test_code, source_code)
        except Exception as e:
            self.logger.error(f"Ошибка пост-обработки: {e}")
            self.logger.info("Используется оригинальный код без изменений")
            return self._unchanged_result(test_code)

        if reviewed_code is None:
            self.logger.warning("Не удалось извлечь код из ответа LLM, используется оригинал")
            return self._unchanged_result(test_code)

        if not self._is_safe_modification(test_code, reviewed_code):
            self.logger.warning(
                "LLM удалила слишком много кода при пост-обработке, используется оригинал"
            )
            return self._unchanged_result(test_code)

        original_tests = self._extract_test_names(test_code)
        reviewed_tests = self._extract_test_names(reviewed_code)
        removed_tests = sorted(original_tests - reviewed_tests)

        if not self._preserves_test_coverage(original_tests, reviewed_tests):
            self.logger.warning(
                "LLM удалила слишком много тестов при пост-обработке, используется оригинал"
            )
            return self._unchanged_result(test_code)

        reviewed_code = self.import_cleaner.clean_unused_imports(reviewed_code)

        was_modified = test_code.strip() != reviewed_code.strip()

        if was_modified:
            original_lines = len(test_code.strip().splitlines())
            reviewed_lines = len(reviewed_code.strip().splitlines())
            self.logger.info(f"Пост-обработка завершена: {original_lines} → {reviewed_lines} строк")
            if removed_tests:
                self.logger.info(f"Удалены дублирующиеся тесты: {removed_tests}")
        else:
            self.logger.info("Пост-обработка: LLM не внесла изменений, код чистый")

        return PostProcessResult(
            reviewed_code=reviewed_code,
            was_modified=was_modified,
        )

    def _unchanged_result(self, test_code: str) -> PostProcessResult:
        cleaned = self.import_cleaner.clean_unused_imports(test_code)
        was_modified = cleaned.strip() != test_code.strip()
        return PostProcessResult(
            reviewed_code=cleaned,
            was_modified=was_modified,
        )

    async def _send_review(self, test_code: str, source_code: str) -> str | None:
        prompt = self.prompt_engine.render(
            template_name="post_review.j2",
            test_code=test_code,
            source_code=source_code,
        )
        response = await self.llm_client.send_prompt(prompt)

        try:
            extracted = self.text_parser.extract_code(response.content)
            if not extracted or len(extracted.strip()) < 10:
                return None
            return extracted
        except Exception as e:
            self.logger.warning(f"Не удалось извлечь код из ответа: {e}")
            return None

    def _is_safe_modification(self, original: str, reviewed: str) -> bool:
        original_lines = len([l for l in original.strip().splitlines() if l.strip()])
        reviewed_lines = len([l for l in reviewed.strip().splitlines() if l.strip()])

        if original_lines == 0:
            return True

        removal_ratio = 1 - (reviewed_lines / original_lines)

        if removal_ratio > self.MAX_REMOVAL_RATIO:
            self.logger.debug(
                f"Коэффициент удаления строк: {removal_ratio:.1%} "
                f"(порог: {self.MAX_REMOVAL_RATIO:.0%})"
            )
            return False

        return True

    def _preserves_test_coverage(self, original_tests: set[str], reviewed_tests: set[str]) -> bool:
        if not original_tests:
            return True

        removed = original_tests - reviewed_tests
        removal_ratio = len(removed) / len(original_tests)

        if removal_ratio > self.MAX_TEST_REMOVAL_RATIO:
            self.logger.debug(
                f"Удалено тестов: {len(removed)}/{len(original_tests)} "
                f"({removal_ratio:.0%}, порог: {self.MAX_TEST_REMOVAL_RATIO:.0%}). "
                f"Удалённые: {sorted(removed)}"
            )
            return False

        return True

    @staticmethod
    def _extract_test_names(code: str) -> set[str]:
        names = set()
        for match in re.finditer(r"(?:async\s+)?def\s+(test_\w+)\s*\(", code):
            names.add(match.group(1))
        return names
