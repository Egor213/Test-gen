import argparse
from pathlib import Path
import os

class ConsoleManager:
    def __init__(self):
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()

    def get_args(self):
        args = self.parser.parse_args()
        for action in self.parser._actions:
            env_name = f"INPUT_{action.dest.upper()}"
            if env_name in os.environ and getattr(args, action.dest) is None:
                setattr(args, action.dest, os.environ[env_name])
        return args

    @staticmethod
    def create_parser():
        parser = argparse.ArgumentParser(
            description="Интерфейс командной строки для генератора тестов LLM."
        )
        parser.add_argument(
            "--max_async_workers", type=int, help="Максимальное количество асинхронных воркеров."
        )
        parser.add_argument(
            "--project",
            "-p",
            type=Path,
            required=True,
            help="Путь до директории с проектом (например: src).",
        )
        parser.add_argument(
            "--max-generate-retries",
            type=int,
            default=3,
            help="Максимальное количество попыток генерации тестов (переопределяет конфиг).",
        )
        parser.add_argument(
            "--target_line_coverage",
            type=int,
            default=60,
            help="Целевое значение тестового покрытия строк",
        )
        parser.add_argument(
            "--max-fix-attempts",
            type=int,
            default=4,
            help="Максимальное количество попыток исправления тестов (переопределяет конфиг).",
        )
        parser.add_argument(
            "--model",
            type=str,
            help="Модель LLM для использования (переопределяет конфиг).",
        )
        parser.add_argument(
            "--temperature",
            type=float,
            help="Температура генерации (переопределяет конфиг).",
        )
        parser.add_argument(
            "--config",
            type=Path,
            default=Path("config/config.yaml"),
            help="Путь к файлу конфигурации YAML. (по умолчанию: config/config.yaml)",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Включить подробный лог (DEBUG).",
        )

        target_group = parser.add_argument_group("Цели генерации")
        target_group.add_argument(
            "--target-dir",
            type=str,
            default=None,
            help="Генерировать тесты только для файлов в указанной папке (относительный путь)",
        )
        target_group.add_argument(
            "--target-function",
            type=str,
            default=None,
            help=(
                "Генерировать тесты только для указанной функции. "
                "Формат: 'function_name' или 'ClassName.method_name' "
                "или относительный путь 'path/to/file.py::ClassName.method_name'"
            ),
        )
        target_group.add_argument(
            "--target-class",
            type=str,
            default=None,
            help=(
                "Генерировать тесты только для указанного класса. "
                "Формат: 'ClassName' "
                "или относительный путь 'path/to/file.py::ClassName'"
            ),
        )
        target_group.add_argument(
            "--target-file",
            type=str,
            default=None,
            help=(
                "Генерировать тесты только для указанного файла. "
                "Формат: 'file.py' "
                "или относительный путь 'path/to/file.py'"
            ),
        )
        parser.add_argument(
            "--tests-dir",
            type=str,
            default="tests",
            help=(
                "Директория для сохранения тестов "
                "(относительно проекта или абсолютный путь). "
                "По умолчанию: tests"
            ),
        )
        return parser
