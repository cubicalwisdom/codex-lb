from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import JsonValue


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str] | None = None
    items: list[JsonValue] = Field(default_factory=list, max_length=20)


class ConversationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str]


class ConversationItemsCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[JsonValue] = Field(min_length=1, max_length=20)


class InputTokenCountRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    input: JsonValue | None = None
    instructions: str | None = None
    tools: list[JsonValue] = Field(default_factory=list)
    conversation: str | dict[str, JsonValue] | None = None
    previous_response_id: str | None = None
