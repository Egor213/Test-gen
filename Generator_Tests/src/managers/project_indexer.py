# FILE: src/managers/project_indexer.py
import ast
import logging
import os
from pathlib import Path
from typing import Callable

from src.app.logger import NullLogger
from src.entity.project import ClassInfo, FieldInfo, FunctionInfo


class ProjectIndexer:
    EXCLUDED_DIRS = {"venv", ".venv", "__pycache__", ".vscode", ".git", ".idea"}

    _INNER_FUNC_FLAG = "flag_inner_func"
    _CLASS_FLAG = "flag_class"

    def __init__(
        self,
        project_path: Path | str,
        extend_excluded_dirs: set[str] | None = None,
        logger: logging.Logger | None = None,
    ):
        project_path = Path(project_path).resolve()
        self.logger = logger or NullLogger()
        self.logger.info(f"Инициализация ProjectIndexer для пути: {project_path}")

        if not project_path.exists():
            self.logger.error(f"Путь не найден: {project_path}")
            raise FileNotFoundError(f"Путь до проекта не найден: {project_path}")

        if not project_path.is_dir():
            self.logger.error(f"Путь не является директорией: {project_path}")
            raise FileNotFoundError(f"Путь не является директорией: {project_path}")

        self.project_path = project_path
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.transform_imports: dict[str, str] = {}

        if extend_excluded_dirs:
            self.EXCLUDED_DIRS = self.EXCLUDED_DIRS | extend_excluded_dirs

        self.logger.info(
            f"ProjectIndexer успешно инициализирован. "
            f"Исключаемые директории: {self.EXCLUDED_DIRS}"
        )

    def get_functions(self) -> dict[str, FunctionInfo]:
        return self.functions

    def get_classes(self) -> dict[str, ClassInfo]:
        return self.classes

    def relative_path(self, path: str | Path) -> str:
        try:
            return str(Path(path).relative_to(self.project_path))
        except ValueError:
            return str(path)

    def analyze(self) -> None:
        self.classes.clear()
        self.functions.clear()
        self._walk_project(self._build_base_index)
        self._walk_project(self._build_general_index)

    def _walk_project(self, callback: Callable[[Path], None]) -> None:
        for dirpath, dirnames, filenames in os.walk(self.project_path):
            dirnames[:] = [d for d in dirnames if d not in self.EXCLUDED_DIRS]
            for filename in filenames:
                if filename.endswith(".py"):
                    callback(Path(dirpath) / filename)

    def _read_source(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.logger.warning(f"Не удалось прочитать файл {path} (кодировка не UTF-8)")
        except Exception as e:
            self.logger.error(f"Ошибка чтения файла {path}: {e}")
        return None

    def _parse_source(self, source: str, path: Path) -> ast.Module | None:
        try:
            return ast.parse(source)
        except SyntaxError as e:
            self.logger.error(f"Синтаксическая ошибка в файле {path}: {e}")
        return None

    def _read_and_parse(self, path: Path) -> tuple[str, ast.Module] | None:
        source = self._read_source(path)
        if source is None:
            return None
        tree = self._parse_source(source, path)
        if tree is None:
            return None
        return source, tree

    def _mark_inner_functions(self, node: ast.AST, parent: ast.AST | None = None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                setattr(node, self._INNER_FUNC_FLAG, True)
            elif isinstance(parent, ast.ClassDef):
                setattr(node, self._CLASS_FLAG, parent.name)

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._mark_inner_functions(child, node)
                elif isinstance(child, ast.ClassDef):
                    self._mark_inner_functions(child, parent)

        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                self._mark_inner_functions(child, node)

    def _mark_all_inner_functions(self, tree: ast.Module) -> None:
        for node in tree.body:
            self._mark_inner_functions(node)

    def _is_inner_function(self, node: ast.AST) -> bool:
        return getattr(node, self._INNER_FUNC_FLAG, False)

    def _get_owner_class(self, node: ast.AST) -> str | None:
        return getattr(node, self._CLASS_FLAG, None)

    def _build_base_index(self, path: Path) -> None:
        self.logger.debug(f"Построение базового индекса для: {path}")

        result = self._read_and_parse(path)
        if result is None:
            return
        source, tree = result

        self._mark_all_inner_functions(tree)

        functions_count = 0
        classes_count = 0

        for node in ast.walk(tree):
            if self._is_inner_function(node):
                continue

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._get_owner_class(node) is None:
                    func_info = self._process_standalone_function(node, path, source)
                    if func_info:
                        functions_count += 1

            elif isinstance(node, ast.ClassDef):
                class_info, m_count, f_count = self._process_class(node, path, source)
                if class_info:
                    classes_count += 1
                    self.logger.debug(
                        f"Добавлен класс: {class_info.name} "
                        f"(методы: {m_count}, поля: {f_count})"
                    )

        if functions_count > 0 or classes_count > 0:
            self.logger.info(f"Файл {path}: {functions_count} функций, {classes_count} классов")

    def _extract_signature(self, source: str, node: ast.AST) -> tuple[str, str] | None:
        code = ast.get_source_segment(source, node)
        if code is None:
            return None
        signature = code.split(":\n", 1)[0]
        return code, signature

    def _process_standalone_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, path: Path, source: str
    ) -> FunctionInfo | None:
        full_name = f"{path}::{node.name}"
        try:
            result = self._extract_signature(source, node)
            if result is None:
                return None
            code, signature = result
            func_info = FunctionInfo(full_name, code, signature)
            self.functions[full_name] = func_info
            self.logger.debug(f"Добавлена функция: {full_name}")
            return func_info
        except Exception as e:
            self.logger.error(f"Ошибка при обработке функции {node.name} в {path}: {e}")
            return None

    def _process_class(
        self, node: ast.ClassDef, path: Path, source: str
    ) -> tuple[ClassInfo | None, int, int]:
        full_name = f"{path}::{node.name}"
        class_info = ClassInfo(full_name)
        methods_count = 0
        fields_count = 0

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._is_inner_function(item):
                    continue
                if self._process_method(item, node.name, full_name, source, class_info):
                    methods_count += 1

            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                fields_count += self._process_class_field(item, node.name, class_info)

        self.classes[full_name] = class_info
        return class_info, methods_count, fields_count

    def _process_method(
        self,
        item: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str,
        class_full_name: str,
        source: str,
        class_info: ClassInfo,
    ) -> bool:
        method_full_name = f"{class_full_name}.{item.name}"
        try:
            result = self._extract_signature(source, item)
            if result is None:
                return False
            code, signature = result
            class_info.methods.append(method_full_name)
            self.functions[method_full_name] = FunctionInfo(
                method_full_name,
                self._dedent_code(code, spaces=4),
                signature,
                cls=class_name,
            )
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при обработке метода {item.name} в классе {class_name}: {e}")
            return False

    def _process_class_field(
        self, item: ast.Assign | ast.AnnAssign, class_name: str, class_info: ClassInfo
    ) -> int:
        try:
            if isinstance(item, ast.AnnAssign):
                targets = [item.target]
                annotation = ast.unparse(item.annotation) if item.annotation else "Any"
                value = item.value
            else:
                targets = item.targets
                annotation = None
                value = item.value

            names = []
            for t in targets:
                names.extend(self._extract_names(t))

            values = self._extract_values(value)

            if len(values) == 1 and len(names) > 1:
                values = values * len(names)
            if len(values) < len(names):
                values.extend([None] * (len(names) - len(values)))

            count = 0
            for name, val in zip(names, values):
                field_type = annotation or "Any"
                class_info.fields.append(FieldInfo(name, field_type, val))
                count += 1
            return count

        except Exception as e:
            self.logger.error(f"Ошибка при обработке поля в классе {class_name}: {e}")
            return 0

    def _build_general_index(self, path: Path) -> None:
        self.logger.debug(f"Построение расширенного индекса для: {path}")

        result = self._read_and_parse(path)
        if result is None:
            return
        source, tree = result

        self.transform_imports.clear()
        dependency_files = self.find_dependencies(path) + [path]

        self.logger.debug(f"Для {path} найдено {len(dependency_files)} файлов зависимостей")

        self._mark_all_inner_functions(tree)

        classes_processed = 0
        functions_processed = 0

        for node in ast.walk(tree):
            if self._is_inner_function(node):
                continue

            if isinstance(node, ast.ClassDef):
                if self._enrich_class_info(node, path, dependency_files):
                    classes_processed += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._enrich_function_info(node, path, dependency_files):
                    functions_processed += 1

        self._deduplicate_all()

        self.logger.info(
            f"Файл {path} обработан: {classes_processed} классов, {functions_processed} функций"
        )

    def _enrich_class_info(
        self, node: ast.ClassDef, path: Path, dependency_files: list[Path | str]
    ) -> bool:
        full_name = f"{path}::{node.name}"
        class_info = self.classes.get(full_name)
        if class_info is None:
            self.logger.warning(f"Класс {full_name} не найден в базовом индексе")
            return False

        for base in node.bases:
            base_str = ast.unparse(base)
            resolved = self.transform_imports.get(base_str.split(".")[0], base_str)

            if "Enum" in resolved or "enum" in resolved.lower():
                class_info.is_enum = True

            if not isinstance(base, ast.Name):
                continue
            base_name = self.transform_imports.get(base.id, base.id)

            is_appended = False
            for file_path in dependency_files:
                dep_str = str(Path(file_path))
                full_base_name = f"{dep_str}::{base_name}"
                if full_base_name in self.classes:
                    is_appended = True
                    class_info.parents.append(full_base_name)

            if not is_appended:
                class_info.parents.append(base_name)

        class_info.decorators.extend(self._extract_decorators(node))
        return True

    def _enrich_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        path: Path,
        dependency_files: list[Path | str],
    ) -> bool:
        owner_class = self._get_owner_class(node)
        if owner_class:
            full_name = f"{path}::{owner_class}.{node.name}"
        else:
            full_name = f"{path}::{node.name}"

        func_info = self.functions.get(full_name)
        if func_info is None:
            self.logger.warning(f"Функция {full_name} не найдена в базовом индексе")
            return False

        if func_info.cls:
            func_info.cls = f"{path}::{owner_class}"

        sig_deps = self._extract_signature_dependencies(node)
        sign_deps = self._extract_sygn_class_dep_files(sig_deps, dependency_files)
        deps = self._extract_call_dependencies(node, dependency_files, func_info)
        func_info.dependencies.extend(deps)
        func_info.decorators.extend(self._extract_decorators(node))
        func_info.signature_dependencies.extend(sign_deps)
        return True

    def _extract_sygn_class_dep_files(
        self, sig_deps: list[str], dependency_files: list[Path | str]
    ) -> list[str]:
        result: set[str] = set()
        for dep_file in dependency_files:
            dep_str = str(Path(dep_file))
            for signature in sig_deps:
                candidate = dep_str + "::" + signature
                if candidate in self.classes:
                    result.add(candidate)
        return list(result)

    def _deduplicate_all(self) -> None:
        for class_info in self.classes.values():
            class_info.methods = list(set(class_info.methods))
            class_info.fields = list(set(class_info.fields))
            class_info.parents = list(set(class_info.parents))

        for func_info in self.functions.values():
            func_info.dependencies = list(set(func_info.dependencies))
            func_info.reverse_dependencies = list(set(func_info.reverse_dependencies))

    def _extract_decorators(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        decorators = []
        for deco in node.decorator_list:
            deco_str = ast.unparse(deco)
            parts = deco_str.split(".")
            resolved = self.transform_imports.get(parts[0], parts[0])
            if len(parts) > 1:
                resolved += "." + parts[-1]
            decorators.append(resolved)
        return decorators

    def _extract_call_dependencies(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        dependency_files: list[str],
        func_info: FunctionInfo,
    ) -> set[str]:
        deps: set[str] = set()
        param_names = {arg.arg for arg in func_node.args.args}

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            if node in func_node.decorator_list:
                continue

            call_name = self._resolve_call_name(node, param_names)
            if call_name is None:
                continue

            call_name = self.transform_imports.get(call_name, call_name)

            for func_path in dependency_files:
                full_name = f"{func_path}::{call_name}"

                for funcs in self.functions:
                    if str(funcs).startswith(str(func_path)) and str(funcs).endswith(call_name):
                        full_name = funcs
                        break

                if full_name in self.functions and full_name != func_info.name:
                    deps.add(full_name)
                    func_info_dep = self.functions.get(full_name)
                    if func_info_dep is not None:
                        func_info_dep.reverse_dependencies.append(func_info.name)
                elif full_name in self.classes:
                    deps.add(full_name)
        return deps

    @staticmethod
    def _resolve_call_name(node: ast.Call, param_names: set[str]) -> str | None:
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in param_names:
                return None
            return name
        return None

    def _resolve_import(self, module_name: str, parent: Path | str | None = None) -> list[Path]:
        parent = Path(parent) if parent else self.project_path
        parts = module_name.split(".")
        candidates = [
            parent.joinpath(*parts).with_suffix(".py"),
            parent.joinpath(*parts, "__init__.py"),
        ]
        return [p for p in candidates if p.exists()]

    def find_dependencies(
        self,
        file_path: Path | str,
        visited: set[Path] | None = None,
        depth: int = 0,
    ) -> list[Path]:
        file_path = Path(file_path).resolve()
        visited = visited or set()

        if file_path in visited:
            return []
        visited.add(file_path)

        source, tree = self._read_and_parse(file_path)

        if not tree:
            return []

        raw_deps = self._collect_import_targets(tree, file_path)

        resolved: list[str] = []
        for dep in raw_deps:
            if dep.exists():
                resolved.append(str(dep))
                if str(dep).endswith("__init__.py") and depth == 0:
                    resolved.extend(self.find_dependencies(dep, visited, depth + 1))

        return list(set(resolved))

    def _collect_import_targets(self, tree: ast.Module, file_path: Path) -> list[Path]:
        deps: list[Path] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.transform_imports[alias.asname or alias.name] = alias.name
                    deps.extend(self._resolve_import(alias.name))

            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    modules_names = node.names
                    for alias in modules_names:
                        module_name = alias.name
                        self._collect_deps_import_from(deps, module_name, file_path, node)
                else:
                    module_name = node.module
                    self._collect_deps_import_from(deps, module_name, file_path, node)
        return deps

    def _collect_deps_import_from(
        self, deps: list, module_name: str, file_path: Path, node: ast.ImportFrom
    ):
        for alias in node.names:
            self.transform_imports[alias.asname or alias.name] = alias.name

        if node.level > 0:
            parent = file_path.parent
            for _ in range(node.level - 1):
                parent = parent.parent
            deps.extend(self._resolve_import(module_name, parent))
        else:
            deps.extend(self._resolve_import(module_name))

    @staticmethod
    def _dedent_code(code: str, spaces: int = 4) -> str:
        lines = code.splitlines()
        processed = []
        for line in lines:
            leading = len(line) - len(line.lstrip(" "))
            remove = min(spaces, leading)
            processed.append(line[remove:])
        return "\n".join(processed)

    @staticmethod
    def _extract_names(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            names: list[str] = []
            for elt in target.elts:
                names.extend(ProjectIndexer._extract_names(elt))
            return names
        return []

    @staticmethod
    def _extract_values(value: ast.AST | None) -> list:
        if value is None:
            return [None]
        if isinstance(value, ast.Constant):
            return [value.value]
        if isinstance(value, (ast.Tuple, ast.List)):
            vals: list = []
            for elt in value.elts:
                vals.extend(ProjectIndexer._extract_values(elt))
            return vals
        return [None]

    def _extract_signature_dependencies(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        BUILTIN_TYPES = {
            "int",
            "str",
            "float",
            "bool",
            "bytes",
            "None",
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
            "self",
            "cls",
        }

        deps: list[str] = []

        def collect_names_from_annotation(annotation: ast.expr | None) -> None:
            if annotation is None:
                return

            if isinstance(annotation, ast.Name):
                name = annotation.id
                if name not in BUILTIN_TYPES:
                    deps.append(name)

            elif isinstance(annotation, ast.Attribute):
                name = ast.unparse(annotation)
                deps.append(name)

            elif isinstance(annotation, ast.Subscript):
                collect_names_from_annotation(annotation.slice)

            elif isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
                collect_names_from_annotation(annotation.left)
                collect_names_from_annotation(annotation.right)

            elif isinstance(annotation, ast.Tuple):
                for elt in annotation.elts:
                    collect_names_from_annotation(elt)

            elif isinstance(annotation, ast.Constant):
                if isinstance(annotation.value, str):
                    value = annotation.value.strip()
                    if value not in BUILTIN_TYPES:
                        deps.append(value)

        for arg in node.args.args:
            if arg.annotation is not None:
                collect_names_from_annotation(arg.annotation)

        for arg in node.args.kwonlyargs + node.args.posonlyargs:
            if arg.annotation is not None:
                collect_names_from_annotation(arg.annotation)

        if node.args.vararg and node.args.vararg.annotation:
            collect_names_from_annotation(node.args.vararg.annotation)

        if node.args.kwarg and node.args.kwarg.annotation:
            collect_names_from_annotation(node.args.kwarg.annotation)

        if node.returns is not None:
            collect_names_from_annotation(node.returns)

        seen = set()
        result = []
        for dep in deps:
            if dep not in seen:
                seen.add(dep)
                result.append(dep)

        return result
