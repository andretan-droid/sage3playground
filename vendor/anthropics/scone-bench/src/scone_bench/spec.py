# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
import math
from dataclasses import dataclass


@dataclass(kw_only=True, frozen=True)
class Grade:
    """Result returned by the `grade_problem` MCP tool."""

    subscores: dict[str, float]
    weights: dict[str, float]
    metadata: dict[str, str] | None = None
    profit: float | None = None

    @property
    def score(self) -> float:
        assert self.subscores.keys() == self.weights.keys()
        assert math.isclose(sum(self.weights.values()), 1.0)
        assert min(self.subscores.values()) >= 0
        assert max(self.subscores.values()) <= 1

        score = sum(self.subscores[k] * self.weights[k] for k in self.subscores)
        assert 0 <= score <= 1
        return score
