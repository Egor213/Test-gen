# FILE: src/orchestrator/test_cleaner.py
import ast
import logging
import re

from src.app.logger import NullLogger
from src.entity.project import FailedTest
from src.orchestrator.feedback_parser import FeedbackParser


class CleanerCodeTransformer(ast.NodeTransformer):
    def __init__(self, failed_tests: list[FailedTest]):
        self.failed_tests = failed_tests

    def _process_function(self, node: ast.FunctionDef) -> ast.AST | None:
        for failed in self.failed_tests:
            if node.name == failed.method_name:
                if failed.class_name is None:
                    return None
                else:
                    parent = getattr(node, "parent", None)
                    if isinstance(parent, ast.ClassDef) and parent.name == failed.class_name:
                        return None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
        return self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST | None:
        return self._process_function(node)


class UnusedFixtureRemover(ast.NodeTransformer):
    def _is_fixture(self, node: ast.FunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if decorator.attr == "fixture":
                    return True
            elif isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute) and func.attr == "fixture":
                    return True
                if isinstance(func, ast.Name) and func.id == "fixture":
                    return True
            elif isinstance(decorator, ast.Name):
                if decorator.id == "fixture":
                    return True
        return False

    def _collect_fixture_names(self, nodes: list[ast.stmt]) -> set[str]:
        names = set()
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._is_fixture(node):
                    names.add(node.name)
        return names

    def _collect_used_fixture_names(self, nodes: list[ast.stmt]) -> set[str]:
        used = set()
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # if self._is_fixture(node):
                #     continue
                if not node.name.startswith("test_"):
                    continue
                for arg in node.args.args:
                    if arg.arg not in ("self", "cls"):
                        used.add(arg.arg)
        return used

    def _remove_unused_fixtures(self, nodes: list[ast.stmt]) -> list[ast.stmt]:
        fixture_names = self._collect_fixture_names(nodes)
        used_names = self._collect_used_fixture_names(nodes)
        unused_fixtures = fixture_names - used_names

        if not unused_fixtures:
            return nodes

        result = []
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._is_fixture(node) and node.name in unused_fixtures:
                    continue
            result.append(node)
        return result

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST | None:
        self.generic_visit(node)

        new_body = self._remove_unused_fixtures(node.body)

        meaningful = [
            n
            for n in new_body
            if not isinstance(n, ast.Pass)
            and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
        ]

        if not meaningful:
            return None

        node.body = new_body if new_body else [ast.Pass()]
        return node

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)

        node.body = self._remove_unused_fixtures(node.body)

        return node


class TestCleaner:

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or NullLogger()

    def clean(self, test_code: str, pytest_feedback: str) -> str:
        failures = FeedbackParser._extract_section(
            pytest_feedback, r"={3,}\s*short test summary info\s*={3,}"
        )
        failed_tests = self._parse_failed_tests(failures or pytest_feedback)

        if not failed_tests:
            self.logger.info("Нет проваленных тестов для удаления")
            return self._remove_unused_fixtures(test_code)

        self.logger.info(f"Найдено {len(failed_tests)} проваленных тестов")

        result = self._remove_failed_tests(test_code, failed_tests)

        fixture_result = self._remove_unused_fixtures(result)

        return fixture_result

    def _parse_failed_tests(self, pytest_output: str) -> list[FailedTest]:
        """
        Парсит вывод pytest и извлекает проваленные тесты:
        - FAILED path::ClassName::method_name[param_id]
        - FAILED path::method_name[param_id]
        - FAILED path::ClassName::method_name
        - FAILED path::method_name
        """
        failed: list[FailedTest] = []

        pattern = re.compile(r"FAILED\s+.*?::(?:(\w+)::)?(test_\w+)" r"(?:\[([^\]]*)\])?")

        for match in pattern.finditer(pytest_output):
            class_name = match.group(1)
            method_name = match.group(2)
            param_id = match.group(3)

            failed.append(
                FailedTest(
                    class_name=class_name,
                    method_name=method_name,
                    param_id=param_id,
                )
            )
            self.logger.debug(
                f"Проваленный тест: class={class_name}, method={method_name}, param={param_id}"
            )

        return failed

    def _remove_unused_fixtures(self, code: str) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.logger.error(f"Ошибка синтаксиса при удалении фикстур: {e}")
            return code

        remover = UnusedFixtureRemover()
        modified_tree = remover.visit(tree)

        if modified_tree is None:
            self.logger.warning("После удаления фикстур дерево пустое")
            return code

        ast.fix_missing_locations(modified_tree)
        cleaned_code = ast.unparse(modified_tree)

        was_modified = cleaned_code != code
        if was_modified:
            self.logger.info("Неиспользуемые фикстуры удалены из кода")
        else:
            self.logger.info("Неиспользуемых фикстур не найдено")

        return cleaned_code

    def _remove_failed_tests(self, code: str, failed_tests: list[FailedTest]) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.logger.error(f"Ошибка синтаксиса в коде тестов: {e}")
            return code

        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

        transformer = CleanerCodeTransformer(failed_tests)
        modified_tree = transformer.visit(tree)

        if modified_tree is None:
            self.logger.warning("Все тесты были удалены, возвращаю оригинальный код")
            return code

        ast.fix_missing_locations(modified_tree)
        cleaned_code = ast.unparse(modified_tree)

        was_modified = cleaned_code != code
        if was_modified:
            self.logger.info("Проваленные тесты удалены из кода")
        else:
            self.logger.info("Проваленные тесты не найдены в коде, изменений не внесено")

        return cleaned_code
