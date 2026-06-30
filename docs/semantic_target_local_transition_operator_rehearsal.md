# Semantic-Target Local Transition Operator Rehearsal

This stage adds a reviewed local operator boundary for the semantic-paper
transition bridge.

It does not call Alpaca, does not alter runtime-clone state, does not expose a
scheduler, and does not enable real-money trading. It only runs the local
on-disk semantic-paper broker through explicit transition legs.

## Command

The new command is:

```text
quant semantic-paper transition-target \
  --request-path reviewed-local-paper-request.json \
  --output-root data/semantic-target/local-paper-transition
```

The command has no mode selector, broker selector, Alpaca selector, scheduler
selector, or runtime selector.

## Request Boundary

The command consumes the existing reviewed
`ActivatedSemanticPaperOperatorRequest` artifact shape. It:

1. preserves the request under `operator-requests/`;
2. verifies the referenced activation-consumption rehearsal still matches the
   passing base rehearsal;
3. loads the contributor set, strategy target decisions, and strategy
   evaluations named by the request;
4. rebuilds the portfolio target and risk target from the request;
5. runs `run_semantic_target_paper_transition(...)` with local paper safety;
6. writes evidence under `semantic-paper-transition/`.

The older command:

```text
quant semantic-paper activated-target
```

is unchanged and still uses the existing single-order local semantic-paper
orchestration path.

## Evidence Shape

The transition operator writes:

```text
<output-root>/operator-requests/<request-id>.json
<output-root>/semantic-paper-transition/state.json
<output-root>/semantic-paper-transition/lifecycle/
<output-root>/semantic-paper-transition/orders/
<output-root>/semantic-paper-transition/fills/
<output-root>/semantic-paper-transition/snapshots/
<output-root>/semantic-paper-transition/reconciliations/
```

For a reviewed request starting at `AAPL=-2` and targeting `AAPL=+3`, the
transition plan records:

```text
leg 1: close_short BUY 2
leg 2: open_long   BUY 3
```

Rerunning the same command reuses the satisfied durable plan and creates no
duplicate local paper orders or fills.

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_activated_semantic_paper_cli.py tests/test_semantic_paper.py
18 passed

.venv/bin/ruff check src/quant/cli.py src/quant/workflows/activated_dry_run_operator.py src/quant/workflows/__init__.py tests/test_activated_semantic_paper_cli.py
All checks passed!
```

The tests prove:

- the command runs a reviewed short-to-long request successfully;
- the transition leg statuses are `reconciled, reconciled`;
- the final local paper state reaches the requested target;
- a second run does not duplicate orders or fills;
- the CLI help exposes no Alpaca, scheduler, or mode selector.

## Remaining Boundary

This is still local paper only. The next stage should add a small verifier for
transition-operator evidence so future runtime or paper-broker promotion can
consume a durable pass/fail report instead of relying on manual inspection.
