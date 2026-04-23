# FILE: src/orchestrator/feedback_parser.py

import re


class FeedbackParser:
    @staticmethod
    def extract_failures(pytest_output: str) -> str:
        sections = []
        failures = FeedbackParser._extract_section(pytest_output, r"={3,}\s*FAILURES\s*={3,}")
        if failures:
            sections.append(failures)

        errors = FeedbackParser._extract_section(pytest_output, r"={3,}\s*ERRORS\s*={3,}")
        if errors:
            sections.append(errors)

        if not sections:
            lines = pytest_output.strip().splitlines()
            return "\n".join(lines[-50:])

        return "\n\n".join(sections)

    @staticmethod
    def _extract_section(output: str, header_pattern: str) -> str | None:
        header_match = re.search(header_pattern, output, re.IGNORECASE)

        if not header_match:
            return None

        rest_of_output = output[header_match.end() :]

        end_pattern = r"\n={3,}\s*\w+.*?={3,}"
        end_match = re.search(end_pattern, rest_of_output)

        if end_match:
            body = rest_of_output[: end_match.start()].strip()
        else:
            body = rest_of_output.strip()

        if body:
            return body
        return None

    @staticmethod
    def count_failures(pytest_output: str) -> tuple[int, int]:
        failed = 0
        total = 0

        fail_match = re.search(r"(\d+)\s+failed", pytest_output)
        pass_match = re.search(r"(\d+)\s+passed", pytest_output)
        err_match = re.search(r"(\d+)\s+error", pytest_output)

        if fail_match:
            failed += int(fail_match.group(1))
        if err_match:
            failed += int(err_match.group(1))
        if pass_match:
            total += int(pass_match.group(1))
        total += failed

        return failed, total
