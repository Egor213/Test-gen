# File path: Generator_Tests/src/llm/invokers/openrouter.py

import logging
from typing import Any

from src.entity.llm import LLMResponse
from src.llm.errors import APIError
from src.llm.invoker import LLMInvoker
from src.managers.config import Config

logger = logging.getLogger(__name__)


class RequestInvoker(LLMInvoker):
    def __init__(self, config: Config):
        super().__init__(config)
        self.base_url = getattr(config.ai, "base_url")
        self.api_key = config.ai_api_key

    async def invoke(self, payload: dict[str, Any]) -> LLMResponse:
        await self._ensure_session()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-project",
            "X-Title": "Test Generator",
        }

        url = f"{self.base_url}/chat/completions"

        try:

            async with self._session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()

                if response.status != 200:
                    error_msg = response_data.get("error", {}).get("message", str(response_data))
                    raise APIError(f"OpenRouter API error ({response.status}): {error_msg}")

                choice = response_data["choices"][0]
                content = choice["message"]["content"]

                usage = response_data.get("usage", {})

                return LLMResponse(
                    content=content,
                    model=response_data.get("model", payload.get("model")),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                )
        except APIError:
            raise
        except Exception as e:
            logger.error(f"Ошибка при вызове OpenRouter API: {e}", exc_info=True)
            raise APIError(f"OpenRouter API error: {e}")
