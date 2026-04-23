import ast
import logging
import re

from src.app.logger import NullLogger


class _UnusedImportRemover(ast.NodeTransformer):
    def __init__(self, used_names: set[str]):
        self.used_names = used_names
        self.removed: list[str] = []

    def _is_used(self, alias: ast.alias) -> bool:
        if alias.name == "*":
            return True
        local_name = alias.asname or alias.name
        top_name = local_name.split(".")[0]
        return top_name in self.used_names

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom | None:
        kept = [a for a in node.names if self._is_used(a)]
        removed = [a.asname or a.name for a in node.names if not self._is_used(a)]
        self.removed.extend(removed)

        if not kept:
            return None

        node.names = kept
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import | None:
        kept = [a for a in node.names if self._is_used(a)]
        removed = [a.asname or a.name for a in node.names if not self._is_used(a)]
        self.removed.extend(removed)

        if not kept:
            return None

        node.names = kept
        return node


class _NameCollector(ast.NodeVisitor):
    def __init__(self):
        self.used_names: set[str] = set()

    def visit_Import(self, node: ast.Import):
        pass

    def visit_ImportFrom(self, node: ast.ImportFrom):
        pass

    def visit_Name(self, node: ast.Name):
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self.used_names.add(root.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        for deco in node.decorator_list:
            self.visit(deco)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        for deco in node.decorator_list:
            self.visit(deco)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        for deco in node.decorator_list:
            self.visit(deco)
        for base in node.bases:
            self.visit(base)
        self.generic_visit(node)


class ImportCleaner:

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or NullLogger()

    def clean_unused_imports(self, code: str) -> str:
        if not code.strip():
            return code

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.logger.warning(e)
            return code

        used_names = self._collect_used_names(tree)

        remover = _UnusedImportRemover(used_names)
        cleaned_tree = remover.visit(tree)

        if not remover.removed:
            return code

        self.logger.info(
            f"Удалено {len(remover.removed)} неиспользуемых импортов: {remover.removed}"
        )

        ast.fix_missing_locations(cleaned_tree)
        return ast.unparse(cleaned_tree)

    def remove_unused_from_nodes(
        self,
        import_nodes: list[ast.Import | ast.ImportFrom],
        body_code: str,
    ) -> list[ast.Import | ast.ImportFrom]:
        used_names = self._collect_used_names_from_code(body_code)

        temp_module = ast.Module(body=list(import_nodes), type_ignores=[])
        ast.fix_missing_locations(temp_module)

        remover = _UnusedImportRemover(used_names)
        cleaned_tree = remover.visit(temp_module)

        if remover.removed:
            self.logger.info(
                f"Удалено {len(remover.removed)} неиспользуемых импортов: {remover.removed}"
            )

        return [
            node for node in cleaned_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        ]

    def _collect_used_names(self, tree: ast.Module) -> set[str]:
        collector = _NameCollector()
        collector.visit(tree)
        return collector.used_names

    def _collect_used_names_from_code(self, code: str) -> set[str]:
        if not code.strip():
            return set()

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set(re.findall(r"\b([A-Za-z_]\w*)\b", code))

        return self._collect_used_names(tree)
