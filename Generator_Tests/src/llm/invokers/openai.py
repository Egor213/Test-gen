# File path: Generator_Tests/src/llm/invokers/openai.py

from typing import Any

from openai import AsyncOpenAI

from src.entity.llm import LLMResponse
from src.llm.errors import APIError
from src.llm.invoker import LLMInvoker
from src.managers.config import Config


class OpenAIInvoker(LLMInvoker):
    def __init__(self, config: Config):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.ai_api_key,
            base_url=getattr(config.ai, "base_url", None),
            timeout=config.ai.timeout,
        )

    async def invoke(self, payload: dict[str, Any]) -> LLMResponse:
        try:
            response = await self._client.chat.completions.create(**payload)
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )
        except Exception as e:
            raise APIError(f"OpenAI API error: {e}")

    async def close(self) -> None:
        await self._client.close()
        await super().close()
