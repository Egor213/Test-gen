# File path: Generator_Tests/src/factories/invoker_factory.py

from src.entity.llm import LLMProvider
from src.llm.invoker import LLMInvoker
from src.llm.invokers.openai import OpenAIInvoker
from src.llm.invokers.request import RequestInvoker
from src.managers.config import Config


def create_invoker(provider: LLMProvider, config: Config) -> LLMInvoker:
    if provider == LLMProvider.OPENAI:
        return OpenAIInvoker(config)
    elif provider == LLMProvider.REQUEST:
        return RequestInvoker(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
