from __future__ import annotations

"""Minimal stub of Pydantic's API for tests without external dependency."""

from dataclasses import dataclass, field, asdict, MISSING
from typing import Any


def Field(*, default: Any = MISSING, default_factory: Any | None = MISSING):
    """Simplified ``Field`` helper mirroring ``pydantic.Field``."""
    if default_factory is not MISSING:
        return field(default_factory=default_factory)
    if default is not MISSING:
        return field(default=default)
    return field()


class _ModelMeta(type):
    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, dict(namespace))
        return dataclass(cls)  # type: ignore[misc]


class BaseModel(metaclass=_ModelMeta):
    """Tiny ``BaseModel`` replacement supporting ``model_dump``."""

    def model_dump(self) -> dict:
        return asdict(self)


__all__ = ["BaseModel", "Field"]
