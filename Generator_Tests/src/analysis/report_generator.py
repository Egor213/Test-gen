# ===== FILE: src/analysis/report_generator.py =====
import logging
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.analysis.analyzers.base import AnalyzerVerdict, BaseAnalyzer
from src.analysis.analyzers.coverage_analyzer import CoverageAnalyzer
from src.analysis.analyzers.duplication import DuplicationAnalyzer
from src.analysis.analyzers.mutation_analyzer import MutationAnalyzer
from src.analysis.analyzers.reliability import ReliabilityAnalyzer
from src.analysis.mutation_tester import MutationResult, MutationTester
from src.app.logger import NullLogger
from src.utils.workspace_helper import WorkspaceHelper


@dataclass
class AnalysisReport:
    timestamp: str = ""
    project_root: str = ""
    verdicts: dict[str, AnalyzerVerdict] = field(default_factory=dict)
    mutation_results: dict[str, MutationResult] = field(default_factory=dict)
    coverage_html_path: str | None = None
    coverage_annotate_path: str | None = None
    coverage_annotate_stats: dict = field(default_factory=dict)


class ReportGenerator:

    def __init__(
        self,
        project_root: Path,
        workspace_helper: WorkspaceHelper,
        mutation_tester: MutationTester | None = None,
        logger: logging.Logger | None = None,
        enable_reliability: bool = True,
        enable_mutation: bool = True,
    ):
        self.project_root = project_root.resolve()
        self.logger = logger or NullLogger()
        self.workspace_helper = workspace_helper

        self.analyzers: list[BaseAnalyzer] = [
            CoverageAnalyzer(workspace_helper=workspace_helper, logger=self.logger),
            DuplicationAnalyzer(logger=self.logger),
        ]

        if enable_reliability:
            self.analyzers.append(
                ReliabilityAnalyzer(workspace_helper=workspace_helper, logger=self.logger)
            )

        self.mutation_analyzer: MutationAnalyzer | None = None
        if enable_mutation and mutation_tester:
            self.mutation_analyzer = MutationAnalyzer(
                mutation_tester=mutation_tester,
                logger=self.logger,
            )
            self.analyzers.append(self.mutation_analyzer)

    def collect_files(
        self,
        test_dir: Path | str,
        source_dirs: list[Path | str] | None = None,
    ) -> tuple[dict[Path, str], dict[Path, str]]:
        test_dir = Path(test_dir)
        test_files: dict[Path, str] = {}
        source_files: dict[Path, str] = {}

        if test_dir.is_file():
            test_files[test_dir] = test_dir.read_text(encoding="utf-8")
        elif test_dir.is_dir():
            for pat in ("test_*.py", "*_test.py"):
                for f in sorted(test_dir.rglob(pat)):
                    if f not in test_files:
                        try:
                            test_files[f] = f.read_text(encoding="utf-8")
                        except Exception as e:
                            self.logger.warning(f"Cannot read {f}: {e}")

        skip = {
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "node_modules",
            ".tox",
            "tests",
            "test",
        }
        for sd in source_dirs or [self.project_root]:
            sp = Path(sd)
            if not sp.exists():
                continue
            for f in sorted(sp.rglob("*.py")):
                if any(p in skip for p in f.parts):
                    continue
                if f.name.startswith("test_") or f.name.endswith("_test.py"):
                    continue
                try:
                    source_files[f] = f.read_text(encoding="utf-8")
                except Exception as e:
                    self.logger.warning(f"Cannot read {f}: {e}")

        return test_files, source_files

    def generate(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
    ) -> AnalysisReport:
        report = AnalysisReport(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            project_root=str(self.project_root),
        )

        for analyzer in self.analyzers:
            self.logger.info(f"[REPORT] {analyzer.name} ...")
            try:
                verdict = analyzer.analyze(
                    test_files=test_files,
                    source_files=source_files,
                    project_root=self.project_root,
                )
                report.verdicts[analyzer.name] = verdict
            except Exception as e:
                self.logger.error(f"[REPORT] {analyzer.name} crashed: {e}")
                report.verdicts[analyzer.name] = AnalyzerVerdict()

        if self.mutation_analyzer:
            report.mutation_results = dict(self.mutation_analyzer.results_by_function)

        return report

    def generate_coverage_html(
        self,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        output_dir: Path,
    ) -> Path | None:
        cov_dir = output_dir / "coverage_html"
        test_paths = list(test_files.keys())
        if not test_paths:
            return None

        test_file_set = set(test_files.keys())

        cov_dirs: set[str] = set()

        for sp in source_files:
            if sp in test_file_set:
                continue

            parts_lower = [p.lower() for p in sp.parts]
            if any(p in ("tests", "test") or p.startswith("test_") for p in parts_lower):
                continue

            try:
                rel = sp.relative_to(self.project_root)
            except ValueError:
                continue

            top = rel.parts[0] if len(rel.parts) > 1 else "."
            cov_dirs.add(top)

        if not cov_dirs:
            self.logger.warning("[REPORT] No source dirs to measure coverage")
            return None

        coveragerc_path = output_dir / ".coveragerc"
        omit_lines = "\n    ".join(
            [
                "*/tests/*",
                "*/test_*.py",
                "*/test.py",
                "*/__pycache__/*",
                "*/conftest.py",
            ]
        )
        coveragerc_path.write_text(
            f"[run]\nomit =\n    {omit_lines}\n\n"
            f"[report]\nomit =\n    {omit_lines}\n\n"
            f"[html]\ndirectory = {cov_dir}\n",
            encoding="utf-8",
        )

        cmd = [
            self.workspace_helper._venv_pytest,
            "--tb=no",
            "--no-header",
            "-q",
            f"--cov-report=html:{cov_dir}",
            f"--cov-config={coveragerc_path}",
        ]

        for d in sorted(cov_dirs):
            cmd.append(f"--cov={d}")

        for tp in test_paths:
            cmd.append(str(tp))

        self.logger.debug(f"[REPORT] Coverage cmd: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(self.project_root),
                env=self.workspace_helper.build_env(),
            )
            self.logger.debug(f"[REPORT] stdout: {result.stdout[-1000:]}")
            if result.stderr:
                self.logger.debug(f"[REPORT] stderr: {result.stderr[-800:]}")

            idx = cov_dir / "index.html"
            return cov_dir if idx.exists() else None

        except Exception as e:
            self.logger.error(f"[REPORT] Coverage HTML error: {e}")
            return None

    def _generate_coverage_annotate(
        self, test_files: dict[Path, str], source_files: dict[Path, str], output_dir: Path
    ) -> tuple[Path | None, dict[str, dict]]:
        annotate_dir = output_dir / "coverage_annotate"
        if annotate_dir.exists():
            shutil.rmtree(annotate_dir)
        test_paths = list(test_files.keys())
        if not test_paths:
            return None, {}

        cov_sources: set[str] = set()
        for sp in source_files:
            try:
                rel = sp.relative_to(self.project_root)
                cov_sources.add(str(rel.parent))
            except ValueError:
                cov_sources.add(str(sp.parent))
        if not cov_sources:
            cov_sources.add(".")

        cmd = [
            self.workspace_helper._venv_pytest,
            "--tb=no",
            "--no-header",
            "-q",
            f"--cov-report=annotate:{annotate_dir}",
        ]

        for src in cov_sources:
            cmd.append(f"--cov={src}")
        for tp in test_paths:
            cmd.append(str(tp))

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(self.project_root),
                env=self.workspace_helper.build_env(),
            )
        except Exception as e:
            self.logger.error(f"[COVERAGE] Annotate generation failed: {e}")
            return None, {}

        if not annotate_dir.exists():
            return None, {}

        normalized_sources = {}
        for src_path, src_content in source_files.items():
            normalized = self._normalize_code_with_black(src_content)
            normalized_sources[src_path] = normalized

        basename_to_paths = defaultdict(list)
        for src_path in source_files:
            basename_to_paths[src_path.stem].append(src_path)

        file_stats = {}
        pattern = re.compile(r"^z_([a-f0-9]+)_(.+)\.py,cover$")
        used_names = defaultdict(int)

        for cover_file in annotate_dir.glob("z_*.py,cover"):
            if "__init__.py" in cover_file.name:
                continue

            match = pattern.match(cover_file.name)
            if not match:
                self.logger.warning(f"Unexpected filename pattern: {cover_file.name}")
                continue

            file_hash = match.group(1)
            basename = match.group(2)

            if basename.startswith("test_"):
                self.logger.debug(f"Skipping test file: {cover_file.name}")
                continue

            candidates = basename_to_paths.get(basename, [])
            if not candidates:
                self.logger.warning(f"No source file with basename '{basename}' for {cover_file}")
                continue

            try:
                content = cover_file.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.error(f"Failed to read {cover_file}: {e}")
                continue

            clean_content = self._strip_coverage_markers(content)
            normalized_clean = self._normalize_code_with_black(clean_content)

            matched_path = None
            best_match = None
            best_similarity = 0.0

            for cand in candidates:
                normalized_src = normalized_sources.get(cand, "")

                similarity = self._calculate_similarity(normalized_clean, normalized_src)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cand

            if matched_path is None:
                matched_path = best_match
                self.logger.debug(
                    f"Using best match ({best_similarity:.1%}) for {cover_file}: {best_match}"
                )

            try:
                rel_path = matched_path.relative_to(self.project_root)
            except ValueError:
                rel_path = matched_path

            percent = self._parse_annotate_percent(content)

            readable_name = str(rel_path).replace("/", "_").replace("\\", "_")
            if readable_name.endswith(".py"):
                readable_name = readable_name[:-3]

            if used_names[readable_name] > 0:
                unique_name = f"{readable_name}_{file_hash[:8]}"
            else:
                unique_name = readable_name

            used_names[readable_name] += 1
            new_name = unique_name + ".cover"
            new_path = annotate_dir / new_name

            if new_path.exists():
                self.logger.warning(f"File {new_path} already exists, using hash suffix")
                unique_name = f"{readable_name}_{file_hash[:8]}"
                new_name = unique_name + ".cover"
                new_path = annotate_dir / new_name

            try:
                cover_file.rename(new_path)
            except Exception as e:
                self.logger.error(f"[COVERAGE] Failed to rename {cover_file} to {new_path}: {e}")
                continue

            file_stats[unique_name] = {
                "path": str(new_path.relative_to(annotate_dir)),
                "original_path": str(rel_path),
                "percent": percent,
                "cover_file": new_name,
            }

        return annotate_dir, file_stats

    def _strip_coverage_markers(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            if line and line[0] in (">", "!", " "):
                lines.append(line[1:])
            else:
                lines.append(line)
        return "\n".join(lines)

    def _normalize_code_with_black(self, code: str) -> str:
        try:
            import black

            mode = black.Mode(
                line_length=100,
                string_normalization=True,
                is_pyi=False,
            )

            formatted = black.format_str(code, mode=mode)
            return formatted.strip()
        except ImportError:
            self.logger.debug("[COVERAGE] Black not available, using original code")
            return code.strip()
        except Exception as e:
            self.logger.debug(f"[COVERAGE] Black formatting failed: {e}")
            return code.strip()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        import difflib

        lines1 = [l.strip() for l in text1.splitlines() if l.strip()]
        lines2 = [l.strip() for l in text2.splitlines() if l.strip()]
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        return matcher.ratio()

    def _parse_annotate_percent(self, content: str) -> float:
        total = 0
        executed = 0
        for line in content.splitlines():
            if line and line[0] in (">", "!"):
                total += 1
                if line[0] == ">":
                    executed += 1
        if total == 0:
            return 100.0
        return (executed / total) * 100

    def save_report(
        self,
        report: AnalysisReport,
        test_files: dict[Path, str],
        source_files: dict[Path, str],
        output_dir: Path | str | None = None,
    ) -> tuple[Path, Path | None, Path | None]:
        out_dir = Path(output_dir) if output_dir else self.project_root
        report_dir = out_dir / "test_analysis_report"
        report_dir.mkdir(parents=True, exist_ok=True)

        # HTML coverage
        cov_html_dir = self.generate_coverage_html(test_files, source_files, report_dir)
        if cov_html_dir:
            report.coverage_html_path = str((cov_html_dir / "index.html").relative_to(report_dir))

        # Annotate coverage
        cov_annotate_dir, annotate_stats = self._generate_coverage_annotate(
            test_files, source_files, report_dir
        )
        if cov_annotate_dir:
            report.coverage_annotate_path = str(cov_annotate_dir.relative_to(report_dir))
            report.coverage_annotate_stats = annotate_stats

        from src.analysis.html_renderer import build_html

        html_path = report_dir / "index.html"
        html_path.write_text(build_html(report), encoding="utf-8")
        self.logger.info(f"[REPORT] HTML → {html_path}")
        return html_path, cov_html_dir, cov_annotate_dir
