# src/analysis/mutator.py
import ast
import copy
import logging
from dataclasses import dataclass
from enum import Enum

from src.app.logger import NullLogger


class MutationType(str, Enum):
    COMPARISON_SWAP = "comparison_swap"
    BOOLEAN_SWAP = "boolean_swap"
    ARITHMETIC_SWAP = "arithmetic_swap"
    RETURN_NONE = "return_none"
    NEGATE_CONDITION = "negate_condition"
    CONSTANT_SWAP = "constant_swap"


@dataclass
class Mutant:
    id: int
    mutation_type: MutationType
    original_code: str
    mutated_code: str
    line_number: int
    description: str
    killed: bool = False
    survived: bool = False
    function_name: str = ""

    @property
    def status(self) -> str:
        if self.killed:
            return "killed"
        if self.survived:
            return "survived"
        return "pending"

    @property
    def status_icon(self) -> str:
        if self.killed:
            return "✅"
        if self.survived:
            return "❌"
        return "⏳"

    def get_diff_lines(self, context_lines: int = 3) -> list[dict]:
        """Генерирует diff между оригиналом и мутантом.

        Возвращает список dict с ключами:
          - type: 'context' | 'removed' | 'added' | 'header'
          - line_no: номер строки (или None для header)
          - content: текст строки
        """
        import difflib

        tree_temp = ast.parse(self.original_code)
        ast.fix_missing_locations(tree_temp)
        normalized_original = ast.unparse(tree_temp)
        original_lines = normalized_original.splitlines(keepends=True)
        mutated_lines = self.mutated_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            mutated_lines,
            fromfile="original",
            tofile="mutant",
            lineterm="",
            n=context_lines,
        )

        result: list[dict] = []
        old_line = 0
        new_line = 0

        for line in diff:
            if line.startswith("@@"):
                result.append({"type": "header", "line_no": None, "content": line.strip()})
                import re

                match = re.search(r"-(\d+)", line)
                if match:
                    old_line = int(match.group(1)) - 1
                match = re.search(r"\+(\d+)", line)
                if match:
                    new_line = int(match.group(1)) - 1
            elif line.startswith("---") or line.startswith("+++"):
                continue
            elif line.startswith("-"):
                old_line += 1
                result.append(
                    {
                        "type": "removed",
                        "line_no": old_line,
                        "content": line[1:].rstrip("\n"),
                    }
                )
            elif line.startswith("+"):
                new_line += 1
                result.append(
                    {
                        "type": "added",
                        "line_no": new_line,
                        "content": line[1:].rstrip("\n"),
                    }
                )
            else:
                old_line += 1
                new_line += 1
                result.append(
                    {
                        "type": "context",
                        "line_no": old_line,
                        "content": (
                            line[1:].rstrip("\n") if line.startswith(" ") else line.rstrip("\n")
                        ),
                    }
                )

        return result


class _ComparisonSwapper(ast.NodeTransformer):
    """Меняет операторы сравнения: > → >=, == → != и т.д."""

    SWAP_MAP = {
        ast.Gt: ast.GtE,
        ast.GtE: ast.Gt,
        ast.Lt: ast.LtE,
        ast.LtE: ast.Lt,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
    }

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        if node.lineno != self.target_line or self.applied:
            return node

        new_ops = []
        changed = False
        for op in node.ops:
            swap_to = self.SWAP_MAP.get(type(op))
            if swap_to and not changed:
                new_ops.append(swap_to())
                changed = True
                self.applied = True
            else:
                new_ops.append(op)

        if changed:
            node.ops = new_ops
        return node


class _BooleanSwapper(ast.NodeTransformer):
    """Меняет True ↔ False."""

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if node.lineno != self.target_line or self.applied:
            return node

        if isinstance(node.value, bool):
            node.value = not node.value
            self.applied = True

        return node


class _ArithmeticSwapper(ast.NodeTransformer):
    """Меняет арифметические операторы: + → -, * → / и т.д."""

    SWAP_MAP = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.Div,
        ast.Div: ast.Mult,
        ast.FloorDiv: ast.Div,
        ast.Mod: ast.Mult,
    }

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_BinOp(self, node: ast.BinOp) -> ast.BinOp:
        if node.lineno != self.target_line or self.applied:
            return node

        swap_to = self.SWAP_MAP.get(type(node.op))
        if swap_to:
            node.op = swap_to()
            self.applied = True

        return node


class _ReturnNoneTransformer(ast.NodeTransformer):
    """Заменяет return X → return None."""

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_Return(self, node: ast.Return) -> ast.Return:
        if node.lineno != self.target_line or self.applied:
            return node

        if node.value is not None:
            node.value = ast.Constant(value=None)
            self.applied = True

        return node


class _NegateConditionTransformer(ast.NodeTransformer):
    """Оборачивает условие if в not: if x → if not x."""

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_If(self, node: ast.If) -> ast.If:
        if node.lineno != self.target_line or self.applied:
            return node

        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        self.applied = True
        return node


class _ConstantSwapper(ast.NodeTransformer):
    """Меняет числовые константы: 0→1, 1→0, N→N+1."""

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.applied = False

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if node.lineno != self.target_line or self.applied:
            return node

        if isinstance(node.value, bool):
            return node

        if isinstance(node.value, int):
            if node.value == 1:
                node.value = 0
            else:
                node.value = node.value + 1
            self.applied = True
        elif isinstance(node.value, float):
            node.value = node.value + 1.0
            self.applied = True

        return node


class Mutator:
    MAX_MUTANTS_PER_FUNCTION = 30

    TRANSFORMER_MAP = {
        MutationType.COMPARISON_SWAP: _ComparisonSwapper,
        MutationType.BOOLEAN_SWAP: _BooleanSwapper,
        MutationType.ARITHMETIC_SWAP: _ArithmeticSwapper,
        MutationType.RETURN_NONE: _ReturnNoneTransformer,
        MutationType.NEGATE_CONDITION: _NegateConditionTransformer,
        MutationType.CONSTANT_SWAP: _ConstantSwapper,
    }

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or NullLogger()
        self._mutant_counter = 0

    def generate_mutants(
        self,
        source_code: str,
        function_name: str,
    ) -> list[Mutant]:
        """
        Генерирует мутанты для исходного кода.

        Args:
            source_code: исходный код файла/функции
            function_name: если задано — мутируем только эту функцию
                           формат: "func_name" или "ClassName.method_name"
        """
        tree_temp = ast.parse(source_code)
        ast.fix_missing_locations(tree_temp)
        normalized_code = ast.unparse(tree_temp)

        try:
            tree = ast.parse(normalized_code)
        except SyntaxError as e:
            self.logger.error(f"[Mutator] Синтаксическая ошибка: {e}")
            return []

        target_lines = self._collect_mutable_lines(tree, function_name)
        self.logger.debug(
            f"[Mutator] Найдено {len(target_lines)} точек мутации (функция: {function_name or 'все'})"
        )

        mutants: list[Mutant] = []
        for line_no, mutation_type in target_lines:
            if len(mutants) >= self.MAX_MUTANTS_PER_FUNCTION:
                self.logger.info(f"[Mutator] Лимит мутантов ({self.MAX_MUTANTS_PER_FUNCTION})")
                break

            mutant = self._create_mutant(
                normalized_code,
                tree,
                line_no,
                mutation_type,
            )
            if mutant is not None:
                mutants.append(mutant)

        self.logger.info(
            f"[Mutator] Сгенерировано {len(mutants)} мутантов для {function_name or 'модуля'}"
        )
        return mutants

    def _collect_mutable_lines(
        self,
        tree: ast.Module,
        function_name: str,
    ) -> list[tuple[int, MutationType]]:
        """Собирает пары (номер_строки, тип_мутации)."""
        targets: list[tuple[int, MutationType]] = []
        seen = set()

        for node in ast.walk(tree):
            if not self._is_inside_function(node, tree, function_name):
                continue

            line = getattr(node, "lineno", None)
            if line is None:
                continue

            item = None
            if isinstance(node, ast.Compare):
                item = (line, MutationType.COMPARISON_SWAP)

            elif isinstance(node, ast.BinOp):
                item = (line, MutationType.ARITHMETIC_SWAP)

            elif isinstance(node, ast.Constant):
                if isinstance(node.value, bool):
                    if self._is_boolean_in_if_test(node, tree):
                        item = (line, MutationType.BOOLEAN_SWAP)
                elif isinstance(node.value, (int, float)):
                    item = (line, MutationType.CONSTANT_SWAP)

            elif isinstance(node, ast.Return) and node.value is not None:
                item = (line, MutationType.RETURN_NONE)

            elif isinstance(node, ast.If):
                item = (line, MutationType.NEGATE_CONDITION)

            if item and item not in seen:
                seen.add(item)
                targets.append(item)

        return targets

    def _is_boolean_in_if_test(self, node: ast.Constant, tree: ast.Module) -> bool:
        for if_node in ast.walk(tree):
            if not isinstance(if_node, ast.If):
                continue
            for subnode in ast.walk(if_node.test):
                if subnode is node:
                    return True
        return False

    def _is_inside_function(
        self,
        node: ast.AST,
        tree: ast.Module,
        function_name: str,
    ) -> bool:
        """Проверяет, находится ли узел внутри заданной функции."""
        parts = function_name.split(".")
        if len(parts) == 2:
            class_name, method_name = parts
        else:
            class_name, method_name = None, parts[0]

        node_line = getattr(node, "lineno", None)
        if node_line is None:
            return False

        for top_node in ast.walk(tree):
            if class_name:
                if not isinstance(top_node, ast.ClassDef):
                    continue
                if top_node.name != class_name:
                    continue
                for item in top_node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            return item.lineno <= node_line <= item.end_lineno
            else:
                if isinstance(top_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if top_node.name == method_name:
                        return top_node.lineno <= node_line <= top_node.end_lineno

        return False

    def _create_mutant(
        self,
        source_code: str,
        tree: ast.Module,
        line_no: int,
        mutation_type: MutationType,
    ) -> Mutant | None:
        """Создаёт один мутант, применяя AST-трансформацию."""
        tree_copy = copy.deepcopy(tree)

        transformer_cls = self.TRANSFORMER_MAP.get(mutation_type)
        if transformer_cls is None:
            return None

        transformer = transformer_cls(line_no)

        try:
            mutated_tree = transformer.visit(tree_copy)
            if not transformer.applied:
                return None

            ast.fix_missing_locations(mutated_tree)
            mutated_code = ast.unparse(mutated_tree)
        except Exception as e:
            self.logger.debug(f"[Mutator] Не удалось создать мутант на строке {line_no}: {e}")
            return None

        self._mutant_counter += 1

        source_lines = source_code.splitlines()
        original_line = source_lines[line_no - 1].strip() if line_no <= len(source_lines) else "?"

        return Mutant(
            id=self._mutant_counter,
            mutation_type=mutation_type,
            original_code=source_code,
            mutated_code=mutated_code,
            line_number=line_no,
            description=(f"{mutation_type.value} на строке {line_no}: '{original_line}'"),
        )
