"""Typed loaders for effective-dated contract configuration."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Weekday = Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
WEEKDAY_INDEX = {"MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, "FRIDAY": 4}


class LotSizeEntry(BaseModel):
    effective_from: date
    lot_size: int = Field(gt=0)
    verified: bool
    note: str = ""


class UnderlyingSpec(BaseModel):
    lot_sizes: list[LotSizeEntry]
    has_weekly: bool
    monthly_weekday: Weekday
    weekly_weekday: Weekday | None = None

    def model_post_init(self, _ctx: object) -> None:
        self.lot_sizes = sorted(self.lot_sizes, key=lambda e: e.effective_from)
        if self.has_weekly and self.weekly_weekday is None:
            raise ValueError("has_weekly=true requires weekly_weekday")


class ContractsConfig(BaseModel):
    underlyings: dict[str, UnderlyingSpec]

    def spec(self, underlying: str) -> UnderlyingSpec:
        if underlying not in self.underlyings:
            raise KeyError(f"unknown underlying: {underlying}")
        return self.underlyings[underlying]


def load_contracts(path: str | Path) -> ContractsConfig:
    with open(path, encoding="utf-8") as fh:
        return ContractsConfig.model_validate(yaml.safe_load(fh))
