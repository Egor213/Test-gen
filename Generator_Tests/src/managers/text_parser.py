import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TextParser:
    """Парсит тесты из ответов LLM и результаты pytest"""

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)

    @staticmethod
    def extract_code(text: str) -> str:
        """Извлечение Python кода из текста"""
        if "```python" in text:
            start = text.find("```python") + 9
            end = text.find("```", start)
            code = text[start:end].strip()
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                code = parts[1].strip()
                if code.startswith("python\n"):
                    code = code[7:]
            else:
                code = text.strip()
        else:
            code = text.strip()

        return code.strip("`").strip()
