"""Benchmark runner for reproducible AstroBridge performance snapshots."""

from __future__ import annotations

import asyncio
import time
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field

from astrobridge.api import QueryRequest


class BenchmarkConfig(BaseModel):
    """Configuration for one benchmark run."""

    iterations: int = Field(default=20, ge=1, le=10000)


class BenchmarkRunner:
    """Run a repeatable query workload and summarize accuracy/latency metrics."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    async def run(self, config: BenchmarkConfig) -> dict[str, Any]:
        latencies_ms: list[float] = []
        statuses: list[str] = []

        workload = [
            QueryRequest(query_type="name", name="Proxima Centauri", auto_route=True),
            QueryRequest(
                query_type="natural_language",
                description="Find nearby red dwarf stars",
                auto_route=True,
            ),
            QueryRequest(query_type="name", name="M31", auto_route=True),
        ]

        for i in range(config.iterations):
            request = workload[i % len(workload)]
            started = time.perf_counter()
            response = await self.orchestrator.execute_query(request)
            elapsed = (time.perf_counter() - started) * 1000
            latencies_ms.append(elapsed)
            statuses.append(response.status)

            # Yield control during larger runs to keep loop responsive.
            if i % 25 == 0:
                await asyncio.sleep(0)

        completed = sum(1 for status in statuses if status in {"success", "partial"})
        success_rate = completed / len(statuses)
        sorted_lat = sorted(latencies_ms)

        # Calculate percentiles using proper nearest-rank method with rounding
        # Handles edge cases for small sample sizes
        if len(sorted_lat) == 0:
            return {
                "iterations": config.iterations,
                "status_counts": {"success": 0, "partial": 0, "error": 0},
                "success_rate": 0.0,
                "latency_ms": {"mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0},
            }

        # For percentile p, the index is round(p * (n-1)) where n is sample size
        # This gives the nearest rank and ensures proper interpolation for small samples
        p50_index = min(len(sorted_lat) - 1, max(0, round(0.50 * (len(sorted_lat) - 1))))
        p95_index = min(len(sorted_lat) - 1, max(0, round(0.95 * (len(sorted_lat) - 1))))

        return {
            "iterations": config.iterations,
            "status_counts": {
                "success": statuses.count("success"),
                "partial": statuses.count("partial"),
                "error": statuses.count("error"),
            },
            "success_rate": success_rate,
            "latency_ms": {
                "mean": mean(latencies_ms),
                "p50": sorted_lat[p50_index],
                "p95": sorted_lat[p95_index],
                "max": max(latencies_ms),
            },
        }
