import time
from pathlib import Path

from src.analysis.analyzers.base import AnalyzerVerdict, BaseAnalyzer
from src.analysis.mutation_tester import MutationResult, MutationTester


class MutationAnalyzer(BaseAnalyzer):

    @property
    def name(self) -> str:
        return "mutation"

    def __init__(self, mutation_tester: MutationTester, **kwargs):
        super().__init__(**kwargs)
        self.mutation_tester = mutation_tester
        self._results_by_function: dict[str, MutationResult] = {}

    @property
    def results_by_function(self) -> dict[str, MutationResult]:
        return self._results_by_function

    def analyze(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        project_root: Path,
        **kwargs,
    ) -> AnalyzerVerdict:
        self._results_by_function.clear()

        function_map = self._map_tests_to_sources(test_files, source_files, project_root)

        if not function_map:
            return AnalyzerVerdict()

        total_killed = 0
        total_mutants = 0
        total_survived = 0
        start_time = time.time()

        for func_name, mapping in function_map.items():
            source_file = mapping["source_file"]
            source_code = mapping["source_code"]
            test_code = mapping["test_code"]
            test_filename = mapping["test_filename"]

            self.logger.info(f"[MUTATION_ANALYZER] Testing function: {func_name}")

            try:
                result = self.mutation_tester.run_mutation_testing(
                    source_code=source_code,
                    source_file=source_file,
                    test_code=test_code,
                    test_filename=test_filename,
                    function_name=func_name,
                )

                self._results_by_function[func_name] = result

                total_killed += result.killed
                total_mutants += result.total_mutants
                total_survived += result.survived

            except Exception as e:
                self.logger.error(f"[MUTATION_ANALYZER] Error testing {func_name}: {e}")

        duration = time.time() - start_time

        return AnalyzerVerdict(
            metadata={
                "total_mutants": total_mutants,
                "total_killed": total_killed,
                "total_survived": total_survived,
                "duration_seconds": round(duration, 1),
                "functions_tested": len(self._results_by_function),
                "results_by_function": {
                    fn: r.to_dict() for fn, r in self._results_by_function.items()
                },
            },
        )

    def _map_tests_to_sources(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        project_root: Path,
    ) -> dict[str, dict]:
        import ast

        function_map: dict[str, dict] = {}

        for test_path, test_code in test_files.items():
            source_file = self._find_source_for_test(test_path, source_files)
            if source_file is None:
                continue

            source_code = source_files[source_file]

            try:
                tree = ast.parse(source_code)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("__") and node.name.endswith("__"):
                        continue
                    if node.name.startswith("test"):
                        continue

                    func_name = node.name
                    for parent_node in ast.walk(tree):
                        if isinstance(parent_node, ast.ClassDef):
                            for item in parent_node.body:
                                if item is node:
                                    func_name = f"{parent_node.name}.{node.name}"
                                    break

                    if func_name not in function_map:
                        function_map[func_name] = {
                            "source_file": source_file,
                            "source_code": source_code,
                            "test_code": test_code,
                            "test_filename": test_path.name,
                        }

        return function_map

    def _find_source_for_test(
        self,
        test_path: Path,
        source_files: dict[Path, str],
    ) -> Path | None:
        test_name = test_path.stem
        if test_name.startswith("test_"):
            source_name = test_name[5:]
        else:
            return None

        for source_path in source_files:
            if source_path.stem == source_name:
                return source_path

        for source_path in source_files:
            if source_name in source_path.stem:
                return source_path

        return None
