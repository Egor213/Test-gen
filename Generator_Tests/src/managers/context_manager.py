import ast
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from src.app.logger import NullLogger
from src.entity.project import ClassInfo, FunctionInfo
from src.managers.project_indexer import ProjectIndexer


@dataclass
class CollectedFunction:
    """Собранная информация о функции для рендеринга."""

    key: str
    info: FunctionInfo
    show_full_body: bool = False


@dataclass
class CollectedClass:
    """Собранная информация о классе для рендеринга."""

    key: str
    info: ClassInfo
    methods: dict[str, CollectedFunction] = field(default_factory=dict)


@dataclass
class FileContext:
    """Контекст одного файла."""

    classes: dict[str, CollectedClass] = field(default_factory=dict)
    functions: dict[str, CollectedFunction] = field(default_factory=dict)


class ContextManager:
    DEFAULT_INDENT = 4
    MAX_INVOKE_EXAMPLE_LENGTH = 1000
    MAX_REVERSE_DEPENDENCIES = 3

    def __init__(
        self,
        project_indexer: ProjectIndexer,
        logger: logging.Logger | None = None,
        dependency_depth: int = 1,
    ):
        self.project_indexer = project_indexer
        self.logger = logger or NullLogger()
        self.dependency_depth = dependency_depth

        self.files: dict[str, FileContext] = defaultdict(FileContext)
        self.seen_objects: set[str] = set()
        self.invoke_examples: dict[str, CollectedFunction] = {}

    def collect_context(self, function_key: str, dependency_depth: int = -1) -> str:
        if dependency_depth >= 0:
            self.dependency_depth = dependency_depth
        self.files.clear()
        self.seen_objects.clear()
        self.invoke_examples.clear()
        self.logger.info(f"Сбор контекста для функции: {function_key}")

        function_info = self._get_function_or_raise(function_key)
        if function_info.cls:
            self._ensure_class(function_info.cls)
            file_path = self._file_path_from_key(function_info.cls)
            cls_collected = self.files[file_path].classes[function_info.cls]
            cls_collected.methods[function_key] = CollectedFunction(
                key=function_key, info=function_info, show_full_body=True
            )
        else:
            file_path = self._file_path_from_key(function_key)
            self.files[file_path].functions[function_key] = CollectedFunction(
                key=function_key, info=function_info, show_full_body=True
            )

        self.seen_objects.add(function_key)

        self._collect_body_annotation_dependencies(function_info.code)

        self._collect_signature_dependencies(function_info)

        self._collect_dependencies_recursive(function_info, current_depth=0)

        self._collect_enums(function_info)

        self._collect_raised_exceptions(function_info)

        self._collect_all_field_type_dependencies()

        self._collect_invoke_examples(function_info)

        return self._render()

    def _collect_all_field_type_dependencies(self) -> None:
        """Финальный проход по всем собранным классам."""
        all_class_keys = []
        for file_ctx in self.files.values():
            all_class_keys.extend(file_ctx.classes.keys())

        for class_key in all_class_keys:
            class_info = self.project_indexer.classes.get(class_key)
            if class_info:
                self._collect_field_type_dependencies(class_info)
                self._collect_method_type_dependencies(class_info)

        for file_ctx in self.files.values():
            for func_collected in file_ctx.functions.values():
                self._collect_body_annotation_dependencies(func_collected.info.code)
                for sig_dep in func_collected.info.signature_dependencies:
                    self._resolve_and_ensure_class_by_name(sig_dep)

    def _collect_signature_dependencies(self, function_info: FunctionInfo) -> None:
        for dep_path in function_info.signature_dependencies:
            self._ensure_class(dep_path)

    def _collect_dependencies_recursive(
        self, function_info: FunctionInfo, current_depth: int
    ) -> None:
        if current_depth >= self.dependency_depth:
            return

        for dep_key in function_info.dependencies:
            if dep_key in self.seen_objects:
                continue

            class_info = self.project_indexer.classes.get(dep_key)
            if class_info:
                self._ensure_class(dep_key)
                continue

            dep_info = self.project_indexer.functions.get(dep_key)
            if dep_info is None:
                self.seen_objects.add(dep_key)
                continue

            self._collect_body_annotation_dependencies(dep_info.code)

            if dep_info.cls:
                self._ensure_class(dep_info.cls)
                file_path = self._file_path_from_key(dep_info.cls)
                cls_collected = self.files[file_path].classes.get(dep_info.cls)
                if cls_collected:
                    cls_collected.methods[dep_key] = CollectedFunction(
                        key=dep_key, info=dep_info, show_full_body=True
                    )
            else:
                self.seen_objects.add(dep_key)
                file_path = self._file_path_from_key(dep_key)
                self.files[file_path].functions[dep_key] = CollectedFunction(
                    key=dep_key, info=dep_info, show_full_body=True
                )
            self._collect_dependencies_recursive(dep_info, current_depth + 1)

    def _ensure_class(self, class_key: str) -> None:
        if class_key in self.seen_objects:
            return
        self.seen_objects.add(class_key)

        class_info = self.project_indexer.classes.get(class_key)
        if not class_info:
            return

        file_path = self._file_path_from_key(class_key)

        if class_key not in self.files[file_path].classes:
            collected_class = CollectedClass(key=class_key, info=class_info)

            for method_key in class_info.methods:
                method_info = self.project_indexer.functions.get(method_key)
                if method_info is None:
                    continue

                is_init = method_key.endswith("__init__")

                if method_key not in collected_class.methods:
                    collected_class.methods[method_key] = CollectedFunction(
                        key=method_key, info=method_info, show_full_body=is_init
                    )

            self.files[file_path].classes[class_key] = collected_class

        for parent_key in class_info.parents:
            self._ensure_class(parent_key)

        self._collect_field_type_dependencies(class_info)

        self._collect_method_type_dependencies(class_info)

    def _collect_method_type_dependencies(self, class_info: ClassInfo) -> None:
        """Собираем классы из сигнатур методов и аннотированных self-присваиваний в телах методов."""
        for method_key in class_info.methods:
            method_info = self.project_indexer.functions.get(method_key)
            if method_info is None:
                continue

            for dep in method_info.signature_dependencies:
                self._resolve_and_ensure_class_by_name(dep)

            self._collect_body_annotation_dependencies(method_info.code)

    def _collect_body_annotation_dependencies(self, code: str) -> None:
        """Парсим тело метода и ищем аннотированные присваивания (self.x: Type = ...)."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                if node.annotation is None:
                    continue
                annotation_str = ast.unparse(node.annotation)
                type_names = self._extract_type_names(annotation_str)
                for type_name in type_names:
                    self._resolve_and_ensure_class_by_name(type_name)

            elif isinstance(node, ast.Assign):
                has_self_target = any(
                    isinstance(t, ast.Attribute)
                    and isinstance(t.value, ast.Name)
                    and t.value.id == "self"
                    for t in node.targets
                )
                if not has_self_target:
                    continue
                call_name = self._extract_call_class_name(node.value)
                if call_name:
                    self._resolve_and_ensure_class_by_name(call_name)

    def _extract_call_class_name(self, node: ast.expr) -> str | None:
        if not isinstance(node, ast.Call):
            return None

        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            return ast.unparse(func)
        return None

    def _collect_field_type_dependencies(self, class_info: ClassInfo) -> None:
        for fld in class_info.fields:
            field_type = getattr(fld, "type", None)
            if not field_type or field_type == "Any":
                continue

            type_names = self._extract_type_names(field_type)
            for type_name in type_names:
                self._resolve_and_ensure_class_by_name(type_name)

    def _extract_type_names(self, type_str: str) -> list[str]:
        BUILTIN_TYPES = {
            "int",
            "str",
            "float",
            "bool",
            "bytes",
            "None",
            "none",
            "list",
            "dict",
            "tuple",
            "set",
            "frozenset",
            "Any",
            "Optional",
            "Union",
            "List",
            "Dict",
            "Tuple",
            "Set",
            "Type",
            "Callable",
            "Awaitable",
            "Coroutine",
            "Generator",
            "Iterator",
            "Iterable",
            "Sequence",
            "Mapping",
            "ClassVar",
            "Final",
            "Literal",
            "TypeVar",
            "Generic",
            "Protocol",
            "datetime",
            "date",
            "time",
            "timedelta",
            "Decimal",
            "UUID",
            "Path",
        }

        try:
            tree = ast.parse(type_str, mode="eval")
            names: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id not in BUILTIN_TYPES:
                    names.append(node.id)
                elif isinstance(node, ast.Attribute):
                    full_name = ast.unparse(node)
                    names.append(full_name)
            return names
        except SyntaxError:
            stripped = type_str.strip()
            if stripped and stripped not in BUILTIN_TYPES:
                return [stripped]
            return []

    def _resolve_and_ensure_class_by_name(self, type_name: str) -> None:
        """Ищет класс по имени в индексе и добавляет в контекст."""
        if not type_name:
            return

        for seen_key in self.seen_objects:
            if seen_key.endswith(f"::{type_name}"):
                return

        if type_name in self.project_indexer.classes:
            self._ensure_class(type_name)
            return

        for class_key in self.project_indexer.classes:
            if class_key.endswith(f"::{type_name}"):
                self._ensure_class(class_key)
                return

    def _collect_enums(self, function_info: FunctionInfo) -> None:
        """Собираем Enum-классы, используемые в коде функции и её зависимостей."""
        used_names: set[str] = set()

        self._extract_names_from_code(function_info.code, used_names)

        for dep_key in function_info.dependencies:
            dep_info = self.project_indexer.functions.get(dep_key)
            if dep_info is not None:
                self._extract_names_from_code(dep_info.code, used_names)

        for class_key, class_info in self.project_indexer.classes.items():
            if not class_info.is_enum:
                continue
            if class_key in self.seen_objects:
                continue
            short_name = class_key.split("::")[-1]
            if short_name in used_names:
                self.seen_objects.add(class_key)
                self._add_enum_class(class_key, class_info)

    def _collect_raised_exceptions(self, function_info: FunctionInfo) -> None:
        """Собираем классы исключений из raise в коде функции и её зависимостей."""
        exception_names: set[str] = set()

        self._extract_raised_names(function_info.code, exception_names)

        for dep_key in function_info.dependencies:
            dep_info = self.project_indexer.functions.get(dep_key)
            if dep_info is not None:
                self._extract_raised_names(dep_info.code, exception_names)

        for exc_name in exception_names:
            for class_key, class_info in self.project_indexer.classes.items():
                if class_key.endswith(f"::{exc_name}"):
                    if class_key in self.seen_objects:
                        break
                    self._ensure_class(class_key)
                    break

    def _collect_invoke_examples(self, function_info: FunctionInfo) -> None:
        """Собираем примеры использования из reverse_dependencies."""
        count = 0
        for dep_key in function_info.reverse_dependencies:
            if count >= self.MAX_REVERSE_DEPENDENCIES:
                break
            dep_func = self.project_indexer.functions.get(dep_key)
            if dep_func:
                self.invoke_examples[dep_key] = CollectedFunction(
                    key=dep_key, info=dep_func, show_full_body=True
                )
                count += 1

    def _extract_names_from_code(self, code: str, names: set[str]) -> None:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    names.add(node.value.id)
                elif isinstance(node, ast.Name):
                    names.add(node.id)
        except SyntaxError:
            pass

    def _extract_raised_names(self, code: str, names: set[str]) -> None:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and node.exc is not None:
                    exc = node.exc
                    if isinstance(exc, ast.Call):
                        if isinstance(exc.func, ast.Name):
                            names.add(exc.func.id)
                        elif isinstance(exc.func, ast.Attribute):
                            names.add(exc.func.attr)
                    elif isinstance(exc, ast.Name):
                        names.add(exc.id)
        except SyntaxError:
            pass

    def _add_enum_class(self, class_key: str, class_info: ClassInfo) -> None:
        file_path = self._file_path_from_key(class_key)
        if class_key not in self.files[file_path].classes:
            collected = CollectedClass(key=class_key, info=class_info)
            self.files[file_path].classes[class_key] = collected

    def _render(self) -> str:

        parts: list[str] = []

        for file_path, file_ctx in self.files.items():
            rel_path = self._relative(file_path)
            file_parts: list[str] = []

            for cls_collected in file_ctx.classes.values():
                file_parts.append(self._render_class(cls_collected))

            for func_collected in file_ctx.functions.values():
                file_parts.append(self._render_function(func_collected))

            if file_parts:
                parts.append(f"Path: {rel_path}")
                parts.append("\n\n".join(file_parts))
                parts.append("")

        if self.invoke_examples:
            parts.append("=" * 40)
            parts.append("Usage examples (reverse dependencies):")
            parts.append("=" * 40)

            examples_by_file: dict[str, list[CollectedFunction]] = defaultdict(list)
            for func in self.invoke_examples.values():
                fp = self._file_path_from_key(func.key)
                examples_by_file[fp].append(func)

            for fp, funcs in examples_by_file.items():
                parts.append(f"\nPath: {self._relative(fp)}")
                for func in funcs:
                    rendered = self._render_function(func)
                    parts.append(rendered[: self.MAX_INVOKE_EXAMPLE_LENGTH])
                    parts.append("")

        return "\n".join(parts)

    def _render_class(self, cls: CollectedClass) -> str:
        lines: list[str] = []

        for deco in cls.info.decorators:
            lines.append(f"@{deco}")

        class_name = cls.key.split("::")[-1]
        class_decl = f"class {class_name}"
        if cls.info.parents:
            parent_names = ", ".join(p.split("::")[-1] for p in cls.info.parents)
            class_decl += f"({parent_names})"
        class_decl += ":"
        lines.append(class_decl)

        body_lines: list[str] = []

        for fld in cls.info.fields:
            fld_str = fld.name
            if getattr(fld, "type", None):
                fld_str += f": {fld.type}"
            if getattr(fld, "value", None) is not None:
                fld_str += f" = {fld.value}"
            body_lines.append(fld_str)

        # TODO: нужны ли отдельно enums?
        if cls.info.is_enum:
            if not body_lines:
                body_lines.append("pass")
            indented_body = self._indent_code("\n".join(body_lines))
            lines.append(indented_body)
            return "\n".join(lines)

        sorted_methods = sorted(
            cls.methods.values(),
            key=lambda m: (0 if m.key.endswith("__init__") else 1, m.key),
        )

        for method in sorted_methods:
            body_lines.append("")
            for deco in method.info.decorators:
                body_lines.append(f"@{deco}")

            if method.show_full_body:
                body_lines.append(method.info.code)
            else:
                body_lines.append(f"{method.info.signature}: ...")

        if not body_lines:
            body_lines.append("pass")

        indented_body = self._indent_code("\n".join(body_lines))
        lines.append(indented_body)

        return "\n".join(lines)

    def _render_function(self, func: CollectedFunction) -> str:
        lines: list[str] = []

        for deco in func.info.decorators:
            lines.append(f"@{deco}")

        if func.show_full_body:
            lines.append(func.info.code)
        else:
            lines.append(f"{func.info.signature}: ...")

        return "\n".join(lines)

    def _is_method_key(self, key: str) -> bool:
        name_part = key.split("::")[-1]
        return "." in name_part

    def _class_key_from_method(self, method_key: str) -> str:
        file_path, name = method_key.rsplit("::", 1)
        class_name = name.rsplit(".", 1)[0]
        return f"{file_path}::{class_name}"

    def _get_function_or_raise(self, function_key: str) -> FunctionInfo:
        function_info = self.project_indexer.functions.get(function_key)
        if not function_info:
            raise ValueError(f"Функция {function_key} не найдена")
        return function_info

    def _indent_code(self, code: str, indent_level: int = DEFAULT_INDENT) -> str:
        indent = " " * indent_level
        return "\n".join(f"{indent}{line}" for line in code.split("\n"))

    def _relative(self, file_path: str) -> str:
        return self.project_indexer.relative_path(file_path)

    def _file_path_from_key(self, key: str) -> str:
        return key.split("::")[0]
