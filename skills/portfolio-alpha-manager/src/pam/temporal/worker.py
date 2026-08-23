from __future__ import annotations

import asyncio
import os

from pam.temporal.activities import (
    build_correlation_clusters_activity,
    compute_daily_brief,
    fetch_market_data,
    persist_outputs,
    validate_inputs,
)
from pam.temporal.workflow import DailyPortfolioAlphaWorkflow
from temporalio.client import Client
from temporalio.worker import Worker


async def _run() -> None:
    target = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    task_queue = os.environ.get("PAM_TASK_QUEUE", "pam-daily")
    client = await Client.connect(target)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[DailyPortfolioAlphaWorkflow],
        activities=[
            validate_inputs,
            fetch_market_data,
            build_correlation_clusters_activity,
            compute_daily_brief,
            persist_outputs,
        ],
    )
    await worker.run()


def main() -> None:
    asyncio.run(_run())
