# tests/test_project_indexer.py

import ast
import logging
import textwrap
from pathlib import Path

import pytest

from src.entity.project import ClassInfo, FieldInfo, FunctionInfo
from src.managers.project_indexer import ProjectIndexer

# ─────────────────────────── fixtures ───────────────────────────


@pytest.fixture
def project_dir(tmp_path):
    """Creates a minimal project directory."""
    return tmp_path


@pytest.fixture
def make_file(project_dir):
    """Helper to create a Python file inside the project directory."""

    def _make(relative_path: str, content: str) -> Path:
        p = project_dir / relative_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    return _make


@pytest.fixture
def indexer(project_dir):
    return ProjectIndexer(project_dir)


# ═══════════════════════ Initialization ═════════════════════════


class TestInit:
    def test_valid_path(self, project_dir):
        idx = ProjectIndexer(project_dir)
        assert idx.project_path == project_dir.resolve()
        assert idx.functions == {}
        assert idx.classes == {}

    def test_nonexistent_path_raises(self, tmp_path):
        bad = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError, match="не найден"):
            ProjectIndexer(bad)

    def test_file_instead_of_dir_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(FileNotFoundError, match="не является директорией"):
            ProjectIndexer(f)

    def test_extend_excluded_dirs(self, project_dir):
        idx = ProjectIndexer(project_dir, extend_excluded_dirs={"node_modules", "dist"})
        assert "node_modules" in idx.EXCLUDED_DIRS
        assert "dist" in idx.EXCLUDED_DIRS

    def test_accepts_string_path(self, project_dir):
        idx = ProjectIndexer(str(project_dir))
        assert idx.project_path == project_dir.resolve()

    def test_custom_logger(self, project_dir):
        logger = logging.getLogger("test_custom")
        idx = ProjectIndexer(project_dir, logger=logger)
        assert idx.logger is logger

    def test_default_logger_is_null(self, project_dir):
        idx = ProjectIndexer(project_dir)
        # NullLogger — should not crash on calls
        idx.logger.info("test")
        idx.logger.debug("test")


# ═══════════════════════ relative_path ══════════════════════════


class TestRelativePath:
    def test_inside_project(self, project_dir, indexer):
        full = project_dir / "pkg" / "mod.py"
        assert indexer.relative_path(full) == str(Path("pkg") / "mod.py")

    def test_outside_project_returns_as_is(self, indexer):
        outside = Path("/some/random/path.py")
        result = indexer.relative_path(outside)
        assert "path.py" in result

    def test_string_input(self, project_dir, indexer):
        full = str(project_dir / "a.py")
        assert indexer.relative_path(full) == "a.py"


# ═══════════════════ Excluded directories ═══════════════════════


class TestWalkExclusion:
    def test_venv_excluded(self, project_dir, make_file):
        make_file("venv/pkg/mod.py", "def hidden(): pass")
        make_file("main.py", "def visible(): pass")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        keys = list(idx.functions.keys())
        assert any("visible" in k for k in keys)
        assert not any("hidden" in k for k in keys)

    def test_pycache_excluded(self, project_dir, make_file):
        make_file("__pycache__/cached.py", "def cached(): pass")
        make_file("app.py", "def app_func(): pass")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert not any("cached" in k for k in idx.functions)

    def test_custom_excluded_dir(self, project_dir, make_file):
        make_file("build/gen.py", "def generated(): pass")
        make_file("src/real.py", "def real(): pass")

        idx = ProjectIndexer(project_dir, extend_excluded_dirs={"build"})
        idx.analyze()

        assert not any("generated" in k for k in idx.functions)
        assert any("real" in k for k in idx.functions)


# ═══════════════════ Simple function indexing ═══════════════════


class TestFunctionIndexing:
    def test_simple_function(self, project_dir, make_file):
        make_file(
            "mod.py",
            """\
            def greet(name):
                return f"Hello, {name}"
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.functions) == 1
        key = list(idx.functions.keys())[0]
        assert "greet" in key
        fi = idx.functions[key]
        assert fi.name == key
        assert "greet" in fi.signature
        assert fi.cls is None

    def test_async_function(self, project_dir, make_file):
        make_file(
            "async_mod.py",
            """\
            async def fetch(url):
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert any("fetch" in k for k in idx.functions)

    def test_multiple_functions(self, project_dir, make_file):
        make_file(
            "multi.py",
            """\
            def foo():
                pass

            def bar():
                pass

            def baz():
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        names = {k.split("::")[-1] for k in idx.functions}
        assert names == {"foo", "bar", "baz"}

    def test_inner_functions_excluded(self, project_dir, make_file):
        make_file(
            "outer.py",
            """\
            def outer():
                def inner():
                    pass
                return inner()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.functions) == 1
        assert any([k.endswith("outer") for k in idx.functions])
        assert not any([k.endswith("inner") for k in idx.functions])

    def test_deeply_nested_inner_excluded(self, project_dir, make_file):
        make_file(
            "deep.py",
            """\
            def level0():
                def level1():
                    def level2():
                        pass
                    return level2()
                return level1()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.functions) == 1


# ═══════════════════════ Class indexing ══════════════════════════


class TestClassIndexing:
    def test_simple_class(self, project_dir, make_file):
        make_file(
            "models.py",
            """\
            class User:
                name: str = "default"

                def greet(self):
                    return self.name
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.classes) == 1
        key = list(idx.classes.keys())[0]
        assert "User" in key
        ci = idx.classes[key]
        assert len(ci.methods) == 1
        assert any("greet" in m for m in ci.methods)
        assert len(ci.fields) == 1
        assert ci.fields[0].name == "name"
        assert ci.fields[0].type == "str"
        assert ci.fields[0].value == "default"

    def test_class_methods_in_functions_dict(self, project_dir, make_file):
        make_file(
            "svc.py",
            """\
            class Service:
                def start(self):
                    pass

                def stop(self):
                    pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        method_keys = [k for k in idx.functions if "Service." in k]
        assert len(method_keys) == 2
        for mk in method_keys:
            assert idx.functions[mk].cls is not None

    def test_class_with_async_method(self, project_dir, make_file):
        make_file(
            "async_svc.py",
            """\
            class AsyncService:
                async def run(self):
                    pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert any("run" in k for k in idx.functions)

    def test_multiple_classes(self, project_dir, make_file):
        make_file(
            "entities.py",
            """\
            class A:
                pass

            class B:
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        class_names = {k.split("::")[-1] for k in idx.classes}
        assert class_names == {"A", "B"}

    def test_inner_method_functions_excluded(self, project_dir, make_file):
        make_file(
            "cls_inner.py",
            """\
            class Processor:
                def process(self):
                    def helper():
                        pass
                    helper()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert not any("helper" in k for k in idx.functions)
        assert any("process" in k for k in idx.functions)


# ═══════════════════════ Field extraction ═══════════════════════


class TestFieldExtraction:
    def test_annotated_field_with_default(self, project_dir, make_file):
        make_file(
            "fields.py",
            """\
            class Config:
                debug: bool = True
                port: int = 8080
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        field_map = {f.name: f for f in ci.fields}
        assert "debug" in field_map
        assert field_map["debug"].type == "bool"
        assert field_map["debug"].value is True
        assert field_map["port"].value == 8080

    def test_annotated_field_no_default(self, project_dir, make_file):
        make_file(
            "fields2.py",
            """\
            class Model:
                value: int
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        assert len(ci.fields) == 1
        assert ci.fields[0].name == "value"
        assert ci.fields[0].type == "int"
        assert ci.fields[0].value is None

    def test_plain_assignment(self, project_dir, make_file):
        make_file(
            "fields3.py",
            """\
            class Defaults:
                x = 10
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        assert len(ci.fields) == 1
        assert ci.fields[0].name == "x"
        assert ci.fields[0].value == 10

    def test_tuple_unpacking_assignment(self, project_dir, make_file):
        make_file(
            "fields4.py",
            """\
            class Multi:
                a, b = 1, 2
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        field_map = {f.name: f for f in ci.fields}
        assert "a" in field_map
        assert "b" in field_map
        assert field_map["a"].value == 1
        assert field_map["b"].value == 2

    def test_complex_value_becomes_none(self, project_dir, make_file):
        make_file(
            "fields5.py",
            """\
            class Comp:
                data = dict()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        assert ci.fields[0].value is None


# ═══════════════════ Inheritance / parents ═══════════════════════


class TestInheritance:
    def test_single_inheritance_same_file(self, project_dir, make_file):
        make_file(
            "inherit.py",
            """\
            class Base:
                pass

            class Child(Base):
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        child_key = [k for k in idx.classes if "Child" in k][0]
        ci = idx.classes[child_key]
        assert len(ci.parents) == 1
        assert "Base" in ci.parents[0]

    def test_no_parents(self, project_dir, make_file):
        make_file(
            "noparent.py",
            """\
            class Standalone:
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = list(idx.classes.values())[0]
        assert ci.parents == []


# ═══════════════════════ Decorators ═════════════════════════════


class TestDecorators:
    def test_function_decorator(self, project_dir, make_file):
        make_file(
            "deco.py",
            """\
            def my_decorator(f):
                return f

            @my_decorator
            def decorated():
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        fi = [v for k, v in idx.functions.items() if "decorated" in k][0]
        assert "my_decorator" in fi.decorators

    def test_class_decorator(self, project_dir, make_file):
        make_file(
            "cls_deco.py",
            """\
            def class_deco(cls):
                return cls

            @class_deco
            class Decorated:
                pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        ci = [v for k, v in idx.classes.items() if "Decorated" in k][0]
        assert "class_deco" in ci.decorators

    def test_method_decorator(self, project_dir, make_file):
        make_file(
            "method_deco.py",
            """\
            class MyClass:
                @staticmethod
                def my_static():
                    pass
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        fi = [v for k, v in idx.functions.items() if "my_static" in k][0]
        assert "staticmethod" in fi.decorators


# ══════════════════════ Dependencies ════════════════════════════


class TestDependencies:
    def test_function_calls_another(self, project_dir, make_file):
        make_file(
            "deps.py",
            """\
            def helper():
                pass

            def main():
                helper()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        main_fi = [v for k, v in idx.functions.items() if k.endswith("::main")][0]
        assert any("helper" in d for d in main_fi.dependencies)

    def test_reverse_dependency(self, project_dir, make_file):
        make_file(
            "rev_deps.py",
            """\
            def callee():
                pass

            def caller():
                callee()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        callee_fi = [v for k, v in idx.functions.items() if k.endswith("::callee")][0]
        assert any("caller" in rd for rd in callee_fi.reverse_dependencies)

    def test_no_self_dependency(self, project_dir, make_file):
        make_file(
            "no_self.py",
            """\
            def recursive():
                recursive()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        # recursive calls itself — it should still show up
        # but verify it doesn't crash
        assert len(idx.functions) == 1


# ══════════════════ Import resolution ═══════════════════════════


class TestFindDependencies:
    def test_resolves_local_module(self, project_dir, make_file):
        make_file("utils.py", "def util(): pass")
        entry = make_file(
            "main.py",
            """\
            import utils
            """,
        )
        idx = ProjectIndexer(project_dir)
        deps = idx.find_dependencies(entry)

        assert any("utils.py" in str(d) for d in deps)

    def test_resolves_package_init(self, project_dir, make_file):
        make_file("pkg/__init__.py", "")
        entry = make_file(
            "main.py",
            """\
            import pkg
            """,
        )
        idx = ProjectIndexer(project_dir)
        deps = idx.find_dependencies(entry)

        assert any("__init__.py" in str(d) for d in deps)

    def test_relative_import(self, project_dir, make_file):
        make_file("pkg/__init__.py", "")
        make_file("pkg/helper.py", "def h(): pass")
        entry = make_file(
            "pkg/main.py",
            """\
            from . import helper
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()
        deps = idx.find_dependencies(entry)
        assert any("helper.py" in str(d) for d in deps)

    def test_nonexistent_import_ignored(self, project_dir, make_file):
        entry = make_file(
            "main.py",
            """\
            import nonexistent_module
            """,
        )
        idx = ProjectIndexer(project_dir)
        deps = idx.find_dependencies(entry)

        assert deps == []

    def test_circular_import_no_infinite_loop(self, project_dir, make_file):
        make_file(
            "a.py",
            """\
            import b
            """,
        )
        make_file(
            "b.py",
            """\
            import a
            """,
        )
        idx = ProjectIndexer(project_dir)
        deps = idx.find_dependencies(project_dir / "a.py")
        # Should not hang; just verify it returns
        assert isinstance(deps, list)

    def test_from_import(self, project_dir, make_file):
        make_file("lib.py", "def lib_func(): pass")
        entry = make_file(
            "consumer.py",
            """\
            from lib import lib_func
            """,
        )
        idx = ProjectIndexer(project_dir)
        deps = idx.find_dependencies(entry)

        assert any("lib.py" in str(d) for d in deps)


# ══════════════════ Cross-file dependencies ═════════════════════


class TestCrossFileDependencies:
    def test_function_from_imported_module(self, project_dir, make_file):
        make_file(
            "helpers.py",
            """\
            def do_work():
                pass
            """,
        )
        make_file(
            "app.py",
            """\
            from helpers import do_work

            def run():
                do_work()
            """,
        )
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        run_fi = [v for k, v in idx.functions.items() if k.endswith("::run")][0]
        assert any("do_work" in d for d in run_fi.dependencies)


# ═══════════════════ Error handling ═════════════════════════════


class TestErrorHandling:
    def test_syntax_error_file_skipped(self, project_dir, make_file):
        make_file("bad.py", "def broken(:\n    pass")
        make_file("good.py", "def ok(): pass")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert any("ok" in k for k in idx.functions)
        assert not any("broken" in k for k in idx.functions)

    def test_non_utf8_file_skipped(self, project_dir):
        p = project_dir / "binary.py"
        p.write_bytes(b"\x80\x81\x82\x83")

        (project_dir / "normal.py").write_text("def normal(): pass", encoding="utf-8")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert any("normal" in k for k in idx.functions)

    def test_empty_file(self, project_dir, make_file):
        make_file("empty.py", "")
        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.functions) == 0
        assert len(idx.classes) == 0


# ═══════════════════ analyze() idempotency ══════════════════════


class TestAnalyzeIdempotency:
    def test_double_analyze_clears(self, project_dir, make_file):
        make_file("mod.py", "def f(): pass")

        idx = ProjectIndexer(project_dir)
        idx.analyze()
        count1 = len(idx.functions)

        idx.analyze()
        count2 = len(idx.functions)

        assert count1 == count2 == 1


# ═══════════════ _dedent_code utility ═════════════════════


class TestRemoveFourSpaces:
    def test_removes_exactly_four(self):
        code = "    def method(self):\n        pass"
        result = ProjectIndexer._dedent_code(code)
        assert result == "def method(self):\n    pass"

    def test_less_than_four_spaces(self):
        code = "  x = 1"
        result = ProjectIndexer._dedent_code(code)
        assert result == "x = 1"

    def test_no_spaces(self):
        code = "x = 1"
        result = ProjectIndexer._dedent_code(code)
        assert result == "x = 1"

    def test_more_than_four_spaces(self):
        code = "        y = 2"
        result = ProjectIndexer._dedent_code(code)
        assert result == "    y = 2"

    def test_empty_string(self):
        assert ProjectIndexer._dedent_code("") == ""

    def test_multiline(self):
        code = "    line1\n        line2\n    line3"
        result = ProjectIndexer._dedent_code(code)
        assert result == "line1\n    line2\nline3"


# ════════════ _extract_names / _extract_values helpers ════════════


class TestExtractHelpers:
    def test_extract_names_simple(self, indexer):
        node = ast.parse("x = 1").body[0].targets[0]
        assert indexer._extract_names(node) == ["x"]

    def test_extract_names_tuple(self, indexer):
        node = ast.parse("a, b, c = 1, 2, 3").body[0].targets[0]
        assert indexer._extract_names(node) == ["a", "b", "c"]

    def test_extract_names_unsupported(self, indexer):
        # attribute target like obj.x
        node = ast.parse("obj.x = 1", mode="exec").body[0].targets[0]
        assert indexer._extract_names(node) == []

    def test_extract_values_constant(self, indexer):
        node = ast.parse("x = 42").body[0].value
        assert indexer._extract_values(node) == [42]

    def test_extract_values_tuple(self, indexer):
        node = ast.parse("x = (1, 2, 3)").body[0].value
        assert indexer._extract_values(node) == [1, 2, 3]

    def test_extract_values_complex(self, indexer):
        node = ast.parse("x = dict()").body[0].value
        assert indexer._extract_values(node) == [None]


# ══════════════════ get_functions / get_classes ══════════════════


class TestGetters:
    def test_get_functions(self, project_dir, make_file):
        make_file("g.py", "def getter(): pass")
        idx = ProjectIndexer(project_dir)
        idx.analyze()
        assert idx.get_functions() is idx.functions
        assert len(idx.get_functions()) == 1

    def test_get_classes(self, project_dir, make_file):
        make_file("g.py", "class Getter: pass")
        idx = ProjectIndexer(project_dir)
        idx.analyze()
        assert idx.get_classes() is idx.classes
        assert len(idx.get_classes()) == 1


# ═══════════════════ Non-.py files ignored ══════════════════════


class TestNonPythonFilesIgnored:
    def test_txt_file_ignored(self, project_dir):
        (project_dir / "notes.txt").write_text("not python")
        (project_dir / "real.py").write_text("def real(): pass", encoding="utf-8")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        assert len(idx.functions) == 1
        assert any("real" in k for k in idx.functions)


# ════════════════════ Complex scenario ══════════════════════════


class TestComplexScenario:
    def test_full_project(self, project_dir, make_file):
        make_file(
            "models/base.py",
            """\
            class BaseModel:
                id: int = 0

                def save(self):
                    pass
            """,
        )
        make_file(
            "models/user.py",
            """\
            from models.base import BaseModel

            class User(BaseModel):
                name: str = ""

                def greet(self):
                    return self.name
            """,
        )
        make_file("models/__init__.py", "")
        make_file(
            "services/user_service.py",
            """\
            from models.user import User

            def create_user(name):
                u = User()
                u.save()
                return u
            """,
        )
        make_file("services/__init__.py", "")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        # Verify classes
        assert any("BaseModel" in k for k in idx.classes)
        assert any("User" in k for k in idx.classes)

        # Verify methods
        assert any("save" in k for k in idx.functions)
        assert any("greet" in k for k in idx.functions)

        # Verify standalone function
        assert any("create_user" in k for k in idx.functions)

        # Verify fields
        user_ci = [v for k, v in idx.classes.items() if k.endswith("User")][0]
        field_names = {f.name for f in user_ci.fields}

        assert "name" in field_names

    def test_multiple_files_same_function_name(self, project_dir, make_file):
        make_file("a.py", "def process(): pass")
        make_file("b.py", "def process(): pass")

        idx = ProjectIndexer(project_dir)
        idx.analyze()

        process_keys = [k for k in idx.functions if "process" in k]
        assert len(process_keys) == 2
        # They should have different paths
        assert process_keys[0] != process_keys[1]
