from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageResult:
    stage: str
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    duration_sec: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    stages: list[StageResult] = field(default_factory=list)
    success: bool = True

    def add_stage(self, result: StageResult) -> None:
        self.stages.append(result)
        if result.failed > 0:
            self.success = False
