from __future__ import annotations

from datetime import timedelta

from pam.temporal.activities import (
    BuildClustersArgs,
    ComputeDailyBriefArgs,
    PersistOutputsArgs,
    WorkflowArgs,
    build_correlation_clusters_activity,
    compute_daily_brief,
    fetch_market_data,
    persist_outputs,
    validate_inputs,
)
from temporalio import workflow


@workflow.defn
class DailyPortfolioAlphaWorkflow:
    @workflow.run
    async def run(self, args: WorkflowArgs) -> str:
        await workflow.execute_activity(
            validate_inputs,
            args,
            start_to_close_timeout=timedelta(minutes=2),
        )
        market_ref = await workflow.execute_activity(
            fetch_market_data,
            args,
            start_to_close_timeout=timedelta(minutes=10),
        )
        clusters_json = await workflow.execute_activity(
            build_correlation_clusters_activity,
            BuildClustersArgs(workflow=args, market=market_ref),
            start_to_close_timeout=timedelta(minutes=10),
        )
        content = await workflow.execute_activity(
            compute_daily_brief,
            ComputeDailyBriefArgs(
                workflow=args,
                market=market_ref,
                clusters_json=clusters_json,
            ),
            start_to_close_timeout=timedelta(minutes=30),
        )
        out_json = await workflow.execute_activity(
            persist_outputs,
            PersistOutputsArgs(workflow=args, content=content),
            start_to_close_timeout=timedelta(minutes=5),
        )
        return out_json
