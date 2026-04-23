# FILE: src/prompt_system/prompt_engine.py
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, select_autoescape

logger = logging.getLogger(__name__)


class PromptEngine:
    """Генератор промптов на основе Jinja2 шаблонов"""

    def __init__(self, templates_dir: str | Path = "prompts"):
        self.templates_dir = Path(templates_dir)

        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Папка с шаблонами не найдена: {templates_dir}")

        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, **kwargs) -> str:
        """Рендерит шаблон с переданными параметрами"""
        template = self._load_template(template_name)
        return template.render(**kwargs)

    def _load_template(self, template_name: str) -> Template:
        """Загружает шаблон по имени"""
        try:
            template = self.env.get_template(template_name)
            logger.debug(f"Шаблон '{template_name}' загружен")
            return template
        except Exception as e:
            raise ValueError(f"Ошибка загрузки шаблона {template_name}: {e}")
