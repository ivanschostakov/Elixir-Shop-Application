from dataclasses import dataclass
from typing import TypedDict, Literal, Callable, Awaitable, Any


class ToolPropertySchema(TypedDict, total=False):
    type: str
    minimum: int
    maximum: int
    minLength: int
    maxLength: int


class ToolParametersSchema(TypedDict, total=False):
    type: Literal["object"]
    properties: dict[str, ToolPropertySchema]
    required: list[str]
    additionalProperties: bool


class ShopAIFunctionTool(TypedDict):
    type: Literal["function"]
    name: str
    description: str
    parameters: ToolParametersSchema



ToolArguments = dict[str, Any]
ToolMethod = Callable[..., Awaitable[ToolArguments]]


@dataclass
class ShopAIToolCall:
    tool_name: str
    arguments: ToolArguments
    ok: bool
    duration_ms: int
    error: str | None = None