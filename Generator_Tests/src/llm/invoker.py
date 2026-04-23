# File path: Generator_Tests/src/llm/invoker.py

import asyncio
import logging
import ssl
from abc import ABC, abstractmethod
from typing import Any

import aiohttp

from src.entity.llm import LLMResponse
from src.managers.config import Config

from .errors import APIError

logger = logging.getLogger(__name__)


class LLMInvoker(ABC):
    def __init__(self, config: Config):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.ai.timeout)

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)

            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @abstractmethod
    async def invoke(self, payload: dict[str, Any]) -> LLMResponse:
        pass

    async def invoke_with_retry(self, payload: dict[str, Any]) -> LLMResponse:
        await self._ensure_session()
        last_exception = None
        for attempt in range(self.config.ai.max_invoke_retries + 1):
            try:
                return await self.invoke(payload)
            except APIError as e:
                last_exception = e
                if attempt < self.config.ai.max_invoke_retries:
                    wait = 2**attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during LLM invocation: {e}", exc_info=True)
                raise

        raise last_exception or RuntimeError("Invocation failed after retries")
