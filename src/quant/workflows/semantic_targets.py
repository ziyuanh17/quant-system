"""Orchestrate the controlled semantic-target pipeline."""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.execution.reconciliation import reconcile_live_state
from quant.execution.target_dry_run import run_semantic_target_dry_run
from quant.execution.target_paper import (
    SemanticPaperReconciliationRunner,
    run_semantic_target_paper,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    Position,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    PortfolioTargetDecision,
    PortfolioTargetStatus,
    ResearchRiskPolicy,
    RiskTargetDecision,
    RiskTargetStatus,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
    TargetUnit,
)
from quant.models.workflow import (
    SemanticTargetWorkflowMode,
    SemanticTargetWorkflowRecord,
    SemanticTargetWorkflowStatus,
)
from quant.operations import FileLock
from quant.research.portfolio_targets import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)
from quant.research.target_artifacts import (
    load_contributor_set,
    load_portfolio_target_decision,
    load_risk_target_decision,
    load_strategy_evaluation,
    load_strategy_target_decision,
    write_contributor_set,
    write_portfolio_target_decision,
    write_risk_target_decision,
    write_strategy_evaluation,
    write_strategy_target_decision,
)


@dataclass(frozen=True)
class SemanticTargetWorkflowResult:
    record: SemanticTargetWorkflowRecord
    portfolio_target: PortfolioTargetDecision
    risk_target: RiskTargetDecision


def run_semantic_target_dry_run_workflow(
    *,
    orchestration_id: str,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    account: LiveAccountSnapshot,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    output_root: Path,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> SemanticTargetWorkflowResult:
    """Persist a target pipeline and observe it without broker submission."""
    input_fingerprint = _input_fingerprint(
        mode=SemanticTargetWorkflowMode.DRY_RUN,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        strategy_evaluations=strategy_evaluations,
        risk_policy=risk_policy,
        portfolio_target_id=portfolio_target_id,
        portfolio_target_revision=portfolio_target_revision,
        risk_target_id=risk_target_id,
        risk_target_revision=risk_target_revision,
        evaluated_at=evaluated_at,
        evidence_refs=evidence_refs,
        operational_inputs={
            "account": account.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "reference_price": reference_price,
            "safety_check": safety_check.model_dump(mode="json"),
        },
    )

    def execute(
        portfolio_target: PortfolioTargetDecision,
        risk_target: RiskTargetDecision,
    ) -> SemanticTargetWorkflowRecord:
        observation = run_semantic_target_dry_run(
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            risk_policy=risk_policy,
            account=account,
            policy=policy,
            reference_price=reference_price,
            safety_check=safety_check,
            artifact_root=output_root / "lifecycle",
            evaluated_at=evaluated_at,
            evidence_refs=evidence_refs,
        )
        return _record(
            orchestration_id=orchestration_id,
            input_fingerprint=input_fingerprint,
            mode=SemanticTargetWorkflowMode.DRY_RUN,
            status=SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            strategy_evaluations=strategy_evaluations,
            portfolio_target=portfolio_target,
            risk_target=risk_target,
            output_root=output_root,
            evaluated_at=evaluated_at,
            execution_plan_id=observation.execution_plan_id,
            dry_run_observation_id=observation.observation_id,
            dry_run_status=observation.status,
            reason=(
                "semantic target dry-run observed: "
                f"{observation.status.value}"
            ),
        )

    return _run_workflow(
        orchestration_id=orchestration_id,
        input_fingerprint=input_fingerprint,
        mode=SemanticTargetWorkflowMode.DRY_RUN,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        strategy_evaluations=strategy_evaluations,
        risk_policy=risk_policy,
        portfolio_target_id=portfolio_target_id,
        portfolio_target_revision=portfolio_target_revision,
        risk_target_id=risk_target_id,
        risk_target_revision=risk_target_revision,
        output_root=output_root,
        evaluated_at=evaluated_at,
        evidence_refs=evidence_refs,
        execute=execute,
    )


def run_semantic_target_paper_workflow(
    *,
    orchestration_id: str,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    output_root: Path,
    initial_cash: float,
    evaluated_at: datetime,
    initial_positions: tuple[Position, ...] = (),
    evidence_refs: tuple[str, ...] = (),
    reconciliation_runner: SemanticPaperReconciliationRunner = (
        reconcile_live_state
    ),
    reconciliation_runner_id: str = "reconcile_live_state_v1",
) -> SemanticTargetWorkflowResult:
    """Persist a target pipeline and execute it only in durable local paper."""
    if not reconciliation_runner_id:
        raise ValueError("reconciliation_runner_id must not be empty")
    input_fingerprint = _input_fingerprint(
        mode=SemanticTargetWorkflowMode.SEMANTIC_PAPER,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        strategy_evaluations=strategy_evaluations,
        risk_policy=risk_policy,
        portfolio_target_id=portfolio_target_id,
        portfolio_target_revision=portfolio_target_revision,
        risk_target_id=risk_target_id,
        risk_target_revision=risk_target_revision,
        evaluated_at=evaluated_at,
        evidence_refs=evidence_refs,
        operational_inputs={
            "policy": policy.model_dump(mode="json"),
            "reference_price": reference_price,
            "safety_check": safety_check.model_dump(mode="json"),
            "initial_cash": initial_cash,
            "initial_positions": [
                item.model_dump(mode="json") for item in initial_positions
            ],
            "reconciliation_runner_id": reconciliation_runner_id,
            "reconciliation_runner_callable": _callable_identity(
                reconciliation_runner
            ),
        },
    )

    def execute(
        portfolio_target: PortfolioTargetDecision,
        risk_target: RiskTargetDecision,
    ) -> SemanticTargetWorkflowRecord:
        paper_root = output_root / "semantic-paper"
        result = run_semantic_target_paper(
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            risk_policy=risk_policy,
            policy=policy,
            reference_price=reference_price,
            safety_check=safety_check,
            state_path=paper_root / "state.json",
            artifact_root=output_root / "lifecycle",
            order_output_dir=paper_root / "orders",
            fill_output_dir=paper_root / "fills",
            snapshot_output_dir=paper_root / "snapshots",
            reconciliation_output_dir=paper_root / "reconciliations",
            initial_cash=initial_cash,
            initial_positions=initial_positions,
            evaluated_at=evaluated_at,
            evidence_refs=evidence_refs,
            reconciliation_runner=reconciliation_runner,
        )
        return _record(
            orchestration_id=orchestration_id,
            input_fingerprint=input_fingerprint,
            mode=SemanticTargetWorkflowMode.SEMANTIC_PAPER,
            status=SemanticTargetWorkflowStatus.EXECUTION_COMPLETED,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            strategy_evaluations=strategy_evaluations,
            portfolio_target=portfolio_target,
            risk_target=risk_target,
            output_root=output_root,
            evaluated_at=evaluated_at,
            execution_plan_id=result.plan.execution_plan_id,
            execution_status=result.status,
            reconciliation_report_id=(
                result.reconciliation.id
                if result.reconciliation is not None
                else None
            ),
            reason=f"semantic paper execution completed: {result.status.value}",
        )

    return _run_workflow(
        orchestration_id=orchestration_id,
        input_fingerprint=input_fingerprint,
        mode=SemanticTargetWorkflowMode.SEMANTIC_PAPER,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        strategy_evaluations=strategy_evaluations,
        risk_policy=risk_policy,
        portfolio_target_id=portfolio_target_id,
        portfolio_target_revision=portfolio_target_revision,
        risk_target_id=risk_target_id,
        risk_target_revision=risk_target_revision,
        output_root=output_root,
        evaluated_at=evaluated_at,
        evidence_refs=evidence_refs,
        execute=execute,
    )


def _run_workflow(
    *,
    orchestration_id: str,
    input_fingerprint: str,
    mode: SemanticTargetWorkflowMode,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    output_root: Path,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...],
    execute: Callable[
        [PortfolioTargetDecision, RiskTargetDecision],
        SemanticTargetWorkflowRecord,
    ],
) -> SemanticTargetWorkflowResult:
    _require_safe_id(orchestration_id)
    _validate_evaluations(
        contributor_set, strategy_decisions, strategy_evaluations
    )
    record_path = output_root / "orchestrations" / f"{orchestration_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{orchestration_id}.lock",
        lock_name=f"semantic-target-workflow:{orchestration_id}",
        stale_after_seconds=300,
    ):
        if record_path.exists():
            record = SemanticTargetWorkflowRecord.model_validate_json(
                record_path.read_text()
            )
            _require_record_identity(
                record=record,
                input_fingerprint=input_fingerprint,
                mode=mode,
                contributor_set=contributor_set,
                strategy_decisions=strategy_decisions,
                strategy_evaluations=strategy_evaluations,
                portfolio_target_id=portfolio_target_id,
                portfolio_target_revision=portfolio_target_revision,
                risk_target_id=risk_target_id,
                risk_target_revision=risk_target_revision,
            )
            return SemanticTargetWorkflowResult(
                record=record,
                portfolio_target=load_portfolio_target_decision(
                    _portfolio_path(output_root, record)
                ),
                risk_target=load_risk_target_decision(
                    _risk_path(output_root, record)
                ),
            )

        _persist_inputs(
            output_root=output_root,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            strategy_evaluations=strategy_evaluations,
        )
        portfolio_target = aggregate_strategy_targets(
            portfolio_target_id=portfolio_target_id,
            revision=portfolio_target_revision,
            contributor_set=contributor_set,
            decisions=strategy_decisions,
            evaluated_at=evaluated_at,
            evidence_refs=evidence_refs,
        )
        _persist_or_verify(
            portfolio_target,
            output_root / "portfolio-targets",
            write_portfolio_target_decision,
            _portfolio_path_for(portfolio_target, output_root),
            load_portfolio_target_decision,
        )
        risk_target = evaluate_research_risk_target(
            risk_target_id=risk_target_id,
            revision=risk_target_revision,
            portfolio_target=portfolio_target,
            policy=risk_policy,
            evaluated_at=evaluated_at,
            evidence_refs=evidence_refs,
        )
        _persist_or_verify(
            risk_target,
            output_root / "risk-targets",
            write_risk_target_decision,
            _risk_path_for(risk_target, output_root),
            load_risk_target_decision,
        )

        if portfolio_target.status == PortfolioTargetStatus.BLOCKED:
            record = _record(
                orchestration_id=orchestration_id,
                input_fingerprint=input_fingerprint,
                mode=mode,
                status=SemanticTargetWorkflowStatus.PORTFOLIO_BLOCKED,
                contributor_set=contributor_set,
                strategy_decisions=strategy_decisions,
                strategy_evaluations=strategy_evaluations,
                portfolio_target=portfolio_target,
                risk_target=risk_target,
                output_root=output_root,
                evaluated_at=evaluated_at,
                reason=portfolio_target.reason,
            )
        elif risk_target.status == RiskTargetStatus.REJECTED:
            record = _record(
                orchestration_id=orchestration_id,
                input_fingerprint=input_fingerprint,
                mode=mode,
                status=SemanticTargetWorkflowStatus.RISK_REJECTED,
                contributor_set=contributor_set,
                strategy_decisions=strategy_decisions,
                strategy_evaluations=strategy_evaluations,
                portfolio_target=portfolio_target,
                risk_target=risk_target,
                output_root=output_root,
                evaluated_at=evaluated_at,
                reason="; ".join(risk_target.reasons),
            )
        else:
            operational_reason = _operational_block_reason(risk_target)
            if operational_reason is not None:
                record = _record(
                    orchestration_id=orchestration_id,
                    input_fingerprint=input_fingerprint,
                    mode=mode,
                    status=SemanticTargetWorkflowStatus.OPERATIONALLY_BLOCKED,
                    contributor_set=contributor_set,
                    strategy_decisions=strategy_decisions,
                    strategy_evaluations=strategy_evaluations,
                    portfolio_target=portfolio_target,
                    risk_target=risk_target,
                    output_root=output_root,
                    evaluated_at=evaluated_at,
                    reason=operational_reason,
                )
            else:
                record = execute(portfolio_target, risk_target)

        _write_model_exclusive(record_path, record)
        return SemanticTargetWorkflowResult(
            record, portfolio_target, risk_target
        )


def _persist_inputs(
    *,
    output_root: Path,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
) -> None:
    _persist_or_verify(
        contributor_set,
        output_root / "contributor-sets",
        write_contributor_set,
        output_root
        / "contributor-sets"
        / contributor_set.contributor_set_id
        / f"{contributor_set.revision}.json",
        load_contributor_set,
    )
    for decision in strategy_decisions:
        _persist_or_verify(
            decision,
            output_root / "strategy-targets",
            write_strategy_target_decision,
            output_root
            / "strategy-targets"
            / decision.strategy_id
            / f"{decision.decision_id}.json",
            load_strategy_target_decision,
        )
    for evaluation in strategy_evaluations:
        _persist_or_verify(
            evaluation,
            output_root / "strategy-evaluations",
            write_strategy_evaluation,
            output_root
            / "strategy-evaluations"
            / evaluation.strategy_id
            / f"{evaluation.evaluation_id}.json",
            load_strategy_evaluation,
        )


def _persist_or_verify[ModelT: BaseModel](
    model: ModelT,
    output_root: Path,
    writer: Callable[[ModelT, Path], Path],
    path: Path,
    loader: Callable[[Path], ModelT],
) -> None:
    try:
        writer(model, output_root)
    except FileExistsError:
        if loader(path) != model:
            raise ValueError(
                f"immutable artifact conflicts with input: {path}"
            ) from None


def _validate_evaluations(
    contributor_set: ContributorSet,
    decisions: tuple[StrategyTargetDecision, ...],
    evaluations: tuple[StrategyEvaluation, ...],
) -> None:
    expected = {
        (item.strategy_id, item.strategy_version)
        for item in contributor_set.expected_contributors
    }
    seen: set[tuple[str, str]] = set()
    decision_by_id = {item.decision_id: item for item in decisions}
    if len(decision_by_id) != len(decisions):
        raise ValueError("strategy decision IDs must be unique")
    for evaluation in evaluations:
        identity = (evaluation.strategy_id, evaluation.strategy_version)
        if (
            identity not in expected
            or evaluation.symbol != contributor_set.symbol
        ):
            raise ValueError("strategy evaluation is outside contributor set")
        if identity in seen:
            raise ValueError(
                "one strategy evaluation is allowed per contributor"
            )
        seen.add(identity)
        if evaluation.outcome != StrategyEvaluationOutcome.UNAVAILABLE:
            decision = decision_by_id.get(
                evaluation.effective_target_decision_id or ""
            )
            if decision is None or (
                decision.strategy_id,
                decision.strategy_version,
                decision.symbol,
            ) != (
                evaluation.strategy_id,
                evaluation.strategy_version,
                evaluation.symbol,
            ):
                raise ValueError(
                    "strategy evaluation must reference its effective decision"
                )
    if seen != expected:
        raise ValueError("every expected contributor requires one evaluation")


def _operational_block_reason(risk_target: RiskTargetDecision) -> str | None:
    if risk_target.unit != TargetUnit.SHARES:
        return "operational execution currently requires share targets"
    value = risk_target.approved_target_value
    if value is None:
        return "operational execution requires an approved target"
    if value != value.to_integral_value():
        return "operational whole-share targets cannot be fractional"
    return None


def _record(
    *,
    orchestration_id: str,
    input_fingerprint: str,
    mode: SemanticTargetWorkflowMode,
    status: SemanticTargetWorkflowStatus,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    portfolio_target: PortfolioTargetDecision,
    risk_target: RiskTargetDecision,
    output_root: Path,
    evaluated_at: datetime,
    reason: str,
    execution_plan_id: str | None = None,
    execution_status: ExecutionPlanStatus | None = None,
    dry_run_observation_id: str | None = None,
    dry_run_status: ExecutionDryRunStatus | None = None,
    reconciliation_report_id: str | None = None,
) -> SemanticTargetWorkflowRecord:
    paths = [
        output_root
        / "contributor-sets"
        / contributor_set.contributor_set_id
        / f"{contributor_set.revision}.json",
        *(
            output_root
            / "strategy-targets"
            / item.strategy_id
            / f"{item.decision_id}.json"
            for item in strategy_decisions
        ),
        *(
            output_root
            / "strategy-evaluations"
            / item.strategy_id
            / f"{item.evaluation_id}.json"
            for item in strategy_evaluations
        ),
        _portfolio_path_for(portfolio_target, output_root),
        _risk_path_for(risk_target, output_root),
    ]
    return SemanticTargetWorkflowRecord(
        orchestration_id=orchestration_id,
        input_fingerprint=input_fingerprint,
        mode=mode,
        status=status,
        evaluated_at=evaluated_at,
        contributor_set_id=contributor_set.contributor_set_id,
        contributor_set_revision=contributor_set.revision,
        strategy_decision_ids=tuple(
            item.decision_id for item in strategy_decisions
        ),
        strategy_evaluation_ids=tuple(
            item.evaluation_id for item in strategy_evaluations
        ),
        portfolio_target_id=portfolio_target.portfolio_target_id,
        portfolio_target_revision=portfolio_target.revision,
        risk_target_id=risk_target.risk_target_id,
        risk_target_revision=risk_target.revision,
        artifact_paths=tuple(str(path) for path in paths),
        execution_plan_id=execution_plan_id,
        execution_status=execution_status,
        dry_run_observation_id=dry_run_observation_id,
        dry_run_status=dry_run_status,
        reconciliation_report_id=reconciliation_report_id,
        reason=reason,
    )


def _require_record_identity(
    *,
    record: SemanticTargetWorkflowRecord,
    input_fingerprint: str,
    mode: SemanticTargetWorkflowMode,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
) -> None:
    expected = (
        input_fingerprint,
        mode,
        contributor_set.contributor_set_id,
        contributor_set.revision,
        tuple(item.decision_id for item in strategy_decisions),
        tuple(item.evaluation_id for item in strategy_evaluations),
        portfolio_target_id,
        portfolio_target_revision,
        risk_target_id,
        risk_target_revision,
    )
    actual = (
        record.input_fingerprint,
        record.mode,
        record.contributor_set_id,
        record.contributor_set_revision,
        record.strategy_decision_ids,
        record.strategy_evaluation_ids,
        record.portfolio_target_id,
        record.portfolio_target_revision,
        record.risk_target_id,
        record.risk_target_revision,
    )
    if actual != expected:
        raise ValueError("orchestration ID is already bound to other inputs")


def _input_fingerprint(
    *,
    mode: SemanticTargetWorkflowMode,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...],
    operational_inputs: dict[str, object],
) -> str:
    payload = {
        "mode": mode.value,
        "contributor_set": contributor_set.model_dump(mode="json"),
        "strategy_decisions": [
            item.model_dump(mode="json") for item in strategy_decisions
        ],
        "strategy_evaluations": [
            item.model_dump(mode="json") for item in strategy_evaluations
        ],
        "risk_policy": risk_policy.model_dump(mode="json"),
        "portfolio_target_id": portfolio_target_id,
        "portfolio_target_revision": portfolio_target_revision,
        "risk_target_id": risk_target_id,
        "risk_target_revision": risk_target_revision,
        "evaluated_at": evaluated_at.isoformat(),
        "evidence_refs": evidence_refs,
        "operational_inputs": operational_inputs,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return sha256(encoded).hexdigest()


def _callable_identity(value: object) -> str:
    module = getattr(value, "__module__", type(value).__module__)
    name = getattr(value, "__qualname__", type(value).__qualname__)
    return f"{module}.{name}"


def _portfolio_path(
    output_root: Path, record: SemanticTargetWorkflowRecord
) -> Path:
    return (
        output_root
        / "portfolio-targets"
        / record.portfolio_target_id
        / f"{record.portfolio_target_revision}.json"
    )


def _risk_path(
    output_root: Path, record: SemanticTargetWorkflowRecord
) -> Path:
    return (
        output_root
        / "risk-targets"
        / record.risk_target_id
        / f"{record.risk_target_revision}.json"
    )


def _portfolio_path_for(
    target: PortfolioTargetDecision, output_root: Path
) -> Path:
    return (
        output_root
        / "portfolio-targets"
        / target.portfolio_target_id
        / f"{target.revision}.json"
    )


def _risk_path_for(target: RiskTargetDecision, output_root: Path) -> Path:
    return (
        output_root
        / "risk-targets"
        / target.risk_target_id
        / f"{target.revision}.json"
    )


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_safe_id(value: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("orchestration ID must be a safe path component")
