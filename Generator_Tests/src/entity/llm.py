# File path: Generator_Tests/src/entity/llm.py

import time
from dataclasses import dataclass, field
from enum import Enum


class LLMProvider(str, Enum):
    OPENAI = "openai"
    REQUEST = "request"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int]
    created_at: float = field(default_factory=time.time)
