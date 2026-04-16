"""Converter interface and shared types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ConvertResult:
    body: str
    title: str | None = None
    warnings: list[str] = field(default_factory=list)


class ConversionError(Exception):
    def __init__(self, src: Path, reason: str) -> None:
        super().__init__(f"{src}: {reason}")
        self.src = src
        self.reason = reason


class Converter(Protocol):
    name: str
    extensions: tuple[str, ...]

    def convert(self, src: Path) -> ConvertResult:
        ...
