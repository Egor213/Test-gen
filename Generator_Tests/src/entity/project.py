from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldInfo:
    name: str
    type: str
    value: Any | None = None


@dataclass
class FunctionInfo:
    name: str
    code: str
    signature: str
    cls: str | None = None
    signature_dependencies: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    reverse_dependencies: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    is_enum: bool = False
    is_init_defined: bool = False


@dataclass
class FailedTest:
    class_name: str | None
    method_name: str
    param_id: str | None
