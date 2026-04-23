import ast
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from src.app.logger import NullLogger
from src.utils.import_cleaner import ImportCleaner


@dataclass
class GeneratedTest:
    function_name: str
    source_file: Path
    test_code: str
    test_path: Path


class ExtractedMethod(NamedTuple):
    name: str
    source: str


class TestMerger:
    KNOWN_STDLIB = frozenset(
        {
            "abc",
            "ast",
            "asyncio",
            "collections",
            "contextlib",
            "copy",
            "dataclasses",
            "datetime",
            "enum",
            "functools",
            "hashlib",
            "importlib",
            "inspect",
            "io",
            "itertools",
            "json",
            "logging",
            "math",
            "os",
            "pathlib",
            "re",
            "shutil",
            "subprocess",
            "sys",
            "tempfile",
            "textwrap",
            "time",
            "typing",
            "unittest",
        }
    )

    def __init__(
        self,
        project_path: Path,
        tests_dir: str | Path = "tests",
        logger: logging.Logger | None = None,
    ):
        self.project_path = project_path
        self.logger = logger or NullLogger()
        self.import_cleaner = ImportCleaner(logger=self.logger)

        tests_path = Path(tests_dir)
        if tests_path.is_absolute():
            self.tests_dir = tests_path
        else:
            self.tests_dir = project_path / tests_path

    def inject_single_method(
        self,
        existing_code: str,
        new_code: str,
        method: ExtractedMethod,
    ) -> str:
        class_name, _ = self._extract_class_methods(existing_code)
        if not class_name:
            self.logger.warning("[MERGE] Не найден класс для инъекции метода")
            return existing_code

        existing_imports = self._extract_import_lines(existing_code)
        new_imports = self._extract_import_lines(new_code)
        code_with_imports = self._add_missing_imports(existing_code, existing_imports, new_imports)

        indent = self._detect_method_indent(code_with_imports, class_name)

        return self._inject_methods_at_class_end(
            code=code_with_imports,
            class_name=class_name,
            methods=[method],
            indent=indent,
        )

    def extract_new_methods(
        self,
        existing_code: str,
        new_code: str,
    ) -> list[ExtractedMethod]:
        _, existing_methods = self._extract_class_methods(existing_code)
        _, new_methods = self._extract_class_methods(new_code)

        existing_names = {m.name for m in existing_methods}

        return [m for m in new_methods if m.name not in existing_names]

    def _extract_class_methods(self, code: str) -> tuple[str | None, list[ExtractedMethod]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.logger.error(f"[MERGE] SyntaxError: {e}")
            return None, []

        lines = code.splitlines()

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.startswith("Test"):
                continue

            methods = []
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                source = self._extract_node_source(item, lines)

                methods.append(
                    ExtractedMethod(
                        name=item.name,
                        source=source,
                    )
                )

            return node.name, methods

        return None, []

    def _extract_node_source(self, node: ast.AST, lines: list[str]) -> str:
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        else:
            start = node.lineno - 1

        end = node.end_lineno
        return "\n".join(lines[start:end])

    def _inject_methods_at_class_end(
        self,
        code: str,
        class_name: str,
        methods: list[ExtractedMethod],
        indent: str,
    ) -> str:
        class_end = self._find_class_end_line(code, class_name)
        if class_end is None:
            self.logger.warning(f"[MERGE] Конец класса {class_name} не найден")
            return code

        lines = code.splitlines()

        new_blocks = []
        for method in methods:
            indented = self._reindent_method(method.source, indent)
            new_blocks.append(indented)

        insert_text = "\n\n".join(new_blocks)

        result_lines = lines[:class_end] + [""] + insert_text.splitlines() + lines[class_end:]

        return "\n".join(result_lines)

    def _find_class_end_line(self, code: str, class_name: str) -> int | None:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node.end_lineno

        return None

    def _detect_method_indent(self, code: str, class_name: str) -> str:
        in_class = False
        for line in code.splitlines():
            stripped = line.strip()

            if f"class {class_name}" in stripped:
                in_class = True
                continue

            if in_class and (
                stripped.startswith("def ")
                or stripped.startswith("async def ")
                or stripped.startswith("@")
            ):
                return line[: len(line) - len(line.lstrip())]

        return "    "

    def _reindent_method(self, method_source: str, target_indent: str) -> str:
        lines = method_source.splitlines()
        if not lines:
            return method_source

        current_indent = ""
        for line in lines:
            if line.strip():
                current_indent = line[: len(line) - len(line.lstrip())]
                break

        result = []
        for line in lines:
            if not line.strip():
                result.append("")
                continue

            if line.startswith(current_indent):
                relative = line[len(current_indent) :]
                result.append(target_indent + relative)
            else:
                result.append(target_indent + line.lstrip())

        return "\n".join(result)

    def _extract_import_lines(self, code: str) -> set[str]:
        result = set()
        for line in code.splitlines():
            stripped = line.strip()
            if re.match(r"^(import\s+|from\s+\S+\s+import\s+)", stripped):
                result.add(stripped)
        return result

    def _add_missing_imports(
        self,
        code: str,
        existing_imports: set[str],
        new_imports: set[str],
    ) -> str:
        missing = new_imports - existing_imports
        if not missing:
            return code

        lines = code.splitlines()

        last_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r"^(import\s+|from\s+\S+\s+import\s+)", stripped):
                last_import_idx = i

        insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0

        result = lines[:insert_at] + sorted(missing) + lines[insert_at:]

        return "\n".join(result)

    def resolve_test_path(self, source_file: Path) -> Path:
        try:
            relative = source_file.relative_to(self.project_path)
        except ValueError:
            relative = Path(source_file.name)

        parts = list(relative.parts)
        test_filename = f"test_{parts[-1]}"
        sub_dirs = parts[:-1]

        if sub_dirs:
            return self.tests_dir / Path(*sub_dirs, test_filename)
        return self.tests_dir / test_filename

    def merge_tests(self, generated_tests: list[GeneratedTest]) -> dict[Path, str]:
        groups: dict[Path, list[GeneratedTest]] = defaultdict(list)

        for test in generated_tests:
            test_path = self.resolve_test_path(test.source_file)
            groups[test_path].append(test)

        merged: dict[Path, str] = {}
        for test_path, tests in groups.items():
            self.logger.info(f"Объединение {len(tests)} тестов в {test_path}")
            merged_code = self._merge_test_codes([t.test_code for t in tests])
            merged[test_path] = merged_code

        return merged

    def _merge_test_codes(self, codes: list[str]) -> str:
        all_import_nodes: list[ast.Import | ast.ImportFrom] = []
        all_bodies: list[str] = []

        for code in codes:
            import_nodes, body = self._split_imports_and_body(code)
            all_import_nodes.extend(import_nodes)
            if body.strip():
                all_bodies.append(body.strip())

        deduped_imports = self._deduplicate_imports(all_import_nodes)
        merged_body = "\n\n\n".join(all_bodies)

        cleaned_imports = self.import_cleaner.remove_unused_from_nodes(deduped_imports, merged_body)

        import_lines = [ast.unparse(node) for node in cleaned_imports]
        sorted_imports = self._sort_imports(import_lines)

        parts: list[str] = []
        if sorted_imports:
            parts.append("\n".join(sorted_imports))
        if merged_body:
            parts.append(merged_body)

        return "\n\n\n".join(parts) + "\n"

    def _split_imports_and_body(self, code: str) -> tuple[list[ast.Import | ast.ImportFrom], str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return self._split_imports_and_body_fallback(code)

        import_nodes: list[ast.Import | ast.ImportFrom] = []
        first_non_import_lineno: int | None = None

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)
            else:
                first_non_import_lineno = node.lineno
                break

        if first_non_import_lineno is not None:
            lines = code.splitlines()
            body = "\n".join(lines[first_non_import_lineno - 1 :])
        else:
            body = ""

        return import_nodes, body

    def _split_imports_and_body_fallback(
        self, code: str
    ) -> tuple[list[ast.Import | ast.ImportFrom], str]:
        lines = code.splitlines()
        import_lines: list[str] = []
        body_start = 0
        import_pattern = re.compile(r"^\s*(import\s+|from\s+\S+\s+import\s+)")

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if import_pattern.match(line):
                import_lines.append(stripped)
                body_start = i + 1
            else:
                break

        nodes: list[ast.Import | ast.ImportFrom] = []
        for line in import_lines:
            try:
                mini_tree = ast.parse(line)
                nodes.extend(
                    n for n in mini_tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                )
            except SyntaxError:
                pass

        body = "\n".join(lines[body_start:])
        return nodes, body

    def _deduplicate_imports(
        self, nodes: list[ast.Import | ast.ImportFrom]
    ) -> list[ast.Import | ast.ImportFrom]:
        from_imports: dict[tuple[str | None, int], dict[str, str | None]] = defaultdict(dict)
        plain_imports: dict[str, str | None] = {}

        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                key = (node.module, node.level)
                for alias in node.names:
                    if alias.name not in from_imports[key]:
                        from_imports[key][alias.name] = alias.asname
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in plain_imports:
                        plain_imports[alias.name] = alias.asname

        result: list[ast.Import | ast.ImportFrom] = []

        for (module, level), names_dict in sorted(
            from_imports.items(), key=lambda x: (x[0][0] or "", x[0][1])
        ):
            aliases = [
                ast.alias(name=name, asname=asname) for name, asname in sorted(names_dict.items())
            ]
            node = ast.ImportFrom(module=module, names=aliases, level=level)
            ast.fix_missing_locations(node)
            result.append(node)

        for name, asname in sorted(plain_imports.items()):
            node = ast.Import(names=[ast.alias(name=name, asname=asname)])
            ast.fix_missing_locations(node)
            result.append(node)

        return result

    def _sort_imports(self, imports: list[str]) -> list[str]:
        stdlib: list[str] = []
        third_party: list[str] = []
        local: list[str] = []

        for imp in imports:
            module = self._extract_top_module(imp)
            if module in self.KNOWN_STDLIB:
                stdlib.append(imp)
            elif module.startswith(("src", ".")):
                local.append(imp)
            else:
                third_party.append(imp)

        result: list[str] = []
        for group in [sorted(stdlib), sorted(third_party), sorted(local)]:
            if group:
                if result:
                    result.append("")
                result.extend(group)

        return result

    @staticmethod
    def _extract_top_module(import_line: str) -> str:
        match = re.match(r"(?:from\s+(\S+)|import\s+(\S+))", import_line.strip())
        if match:
            module = match.group(1) or match.group(2)
            return module.split(".")[0]
        return ""
