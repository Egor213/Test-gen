from __future__ import annotations
import ast
import operator
import math
from typing import List, Union, Optional

Number = Union[int, float]

class CalcError(Exception):
    """Базовое исключение калькулятора."""
    pass

class Calculator:
    """
    Простой калькулятор.

    Основные методы:
    - add/sub/mul/div/pow/sqrt/negate
    - evaluate(expr: str) — безопасное вычисление выражения
    - memory store/recall/clear
    - history — список (строка операции, результат)
    """

    def __init__(self) -> None:
        self._memory: Optional[Number] = None
        self.history: List[str] = []

    # --- Простые операции, возвращают число и записывают в историю ---
    def add(self, a: Number, b: Number) -> Number:
        res = a + b
        self._record(f"{a} + {b} = {res}")
        return res

    def sub(self, a: Number, b: Number) -> Number:
        res = a - b
        self._record(f"{a} - {b} = {res}")
        return res

    def mul(self, a: Number, b: Number) -> Number:
        res = a * b
        self._record(f"{a} * {b} = {res}")
        return res

    def div(self, a: Number, b: Number) -> Number:
        if b == 0:
            raise CalcError("Деление на ноль")
        res = a / b
        self._record(f"{a} / {b} = {res}")
        return res

    def pow(self, a: Number, b: Number) -> Number:
        res = a ** b
        self._record(f"{a} ** {b} = {res}")
        return res

    def sqrt(self, a: Number) -> Number:
        if a < 0:
            raise CalcError("Квадратный корень из отрицательного числа")
        res = math.sqrt(a)
        self._record(f"sqrt({a}) = {res}")
        return res

    def negate(self, a: Number) -> Number:
        res = -a
        self._record(f"neg({a}) = {res}")
        return res

    # --- Память ---
    def memory_store(self, value: Number) -> None:
        self._memory = value
        self._record(f"MS {value}")

    def memory_recall(self) -> Optional[Number]:
        self._record(f"MR -> {self._memory}")
        return self._memory

    def memory_clear(self) -> None:
        self._memory = None
        self._record("MC")

    # --- История ---
    def _record(self, line: str) -> None:
        self.history.append(line)

    def clear_history(self) -> None:
        self.history.clear()

    # --- Безопасное вычисление выражений строкой ---
    # Поддерживаются: +, -, *, /, %, **, унарный -, скобки, числа (int/float)
    def evaluate(self, expr: str) -> Number:
        """
        Безопасно вычисляет арифметическое выражение в строке.
        Пример: calc.evaluate("2 + 3*(4-1) / 2")
        """
        try:
            node = ast.parse(expr, mode="eval")
            res = self._eval_node(node.body)
        except (SyntaxError, ValueError, TypeError) as e:
            raise CalcError(f"Неверное выражение: {e}")
        self._record(f"{expr} = {res}")
        return res

    def _eval_node(self, node: ast.AST) -> Number:
        # операторы
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = node.op
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Mod: operator.mod,
                ast.Pow: operator.pow,
                ast.FloorDiv: operator.floordiv,
            }
            fn = ops.get(type(op))
            if fn is None:
                raise CalcError(f"Оператор {type(op)} не поддерживается")
            if isinstance(op, ast.Div) and right == 0:
                raise CalcError("Деление на ноль")
            return fn(left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise CalcError(f"Унарный оператор {type(node.op)} не поддерживается")

        if isinstance(node, ast.Num):  # Py <3.8
            return node.n

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):  # Py3.8+
            return node.value

        if isinstance(node, ast.Expr):
            return self._eval_node(node.value)

        # запрещаем всё остальное (вызовы функций, имена, атрибуты и т.д.)
        raise CalcError(f"Недопустимый элемент в выражении: {ast.dump(node)}")

# ---------------- Примеры использования ----------------
if __name__ == "__main__":
    calc = Calculator()

    print("Примеры:")
    print("2 + 3 =", calc.add(2, 3))
    print("10 / 4 =", calc.div(10, 4))
    print("sqrt(16) =", calc.sqrt(16))
    print("evaluate('2 + 3*(4-1)/2') =", calc.evaluate("2 + 3*(4-1)/2"))

    calc.memory_store(42)
    print("memory recall:", calc.memory_recall())

    print("\nИстория:")
    for line in calc.history:
        print(" ", line)
