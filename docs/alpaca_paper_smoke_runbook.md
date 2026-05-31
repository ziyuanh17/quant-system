# Alpaca Paper Smoke Runbook

This runbook is the first human-operated check for the Alpaca paper path.

Run it only against an Alpaca paper account. It is intentionally manual and
small so the first broker-connected workflow is inspected before any scheduled
automation is added.

## Stop Criteria

Stop immediately and do not continue to scheduling if:

- any command touches a real-money account
- any command writes API keys or secret keys to artifacts or logs
- a safety gate passes without the required confirmation phrase
- order, fill, snapshot, or reconciliation artifacts look surprising
- reconciliation status is not `passed`
- Alpaca reports a different account than expected

## Preconditions

Confirm the current code is healthy:

```bash
make check
```

Install the optional Alpaca dependency only for this broker-connected path:

```bash
uv sync --extra dev --extra broker-alpaca
```

Or with pip:

```bash
python -m pip install -e ".[dev,broker-alpaca]"
```

Export Alpaca paper credentials. Do not put real values into committed files:

```bash
export QUANT_ALPACA_PAPER_API_KEY="..."
export QUANT_ALPACA_PAPER_SECRET_KEY="..."
export QUANT_ALPACA_PAPER_ACCOUNT_ID="..."
```

If you need a test/proxy endpoint, set:

```bash
export QUANT_ALPACA_PAPER_URL_OVERRIDE="..."
```

Set live safety variables explicitly. These gates are required even though the
broker environment is Alpaca paper:

```bash
export QUANT_TRADING_MODE=live
export QUANT_LIVE_TRADING_ENABLED=true
export QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
export QUANT_BROKER=alpaca-paper
```

Choose the one-share smoke symbol and a current reference price immediately
before the order. The reference price is written to the audit record and is
used by the local notional gate; do not use a placeholder such as `1` for a
symbol trading materially above `$1`.

```bash
export QUANT_SMOKE_SYMBOL=AAPL
export QUANT_SMOKE_REFERENCE_PRICE="..."
export QUANT_MAX_ORDER_NOTIONAL="..."
```

Set `QUANT_MAX_ORDER_NOTIONAL` deliberately above one share at the current
reference price, but no higher than you are comfortable testing in the paper
account.

Use a unique client order ID for the run:

```bash
export QUANT_SMOKE_CLIENT_ORDER_ID="alpaca-paper-smoke-$(date +%Y%m%d-%H%M%S)"
```

## Blocked Safety Check

First confirm the order command fails closed without safety approval:

```bash
quant live alpaca-paper-order \
  --symbol "$QUANT_SMOKE_SYMBOL" \
  --side buy \
  --quantity 1 \
  --price "$QUANT_SMOKE_REFERENCE_PRICE" \
  --client-order-id blocked-smoke-check
```

Expected result:

```text
Allowed: False
```

No files should be written under `data/live/orders`,
`data/live/fills`, or `data/live/account_snapshots` by this blocked command.

Now confirm the explicit environment safety configuration passes:

```bash
quant safety check --from-env
```

Expected result:

```text
Mode: live
Allowed: True
```

## Baseline Snapshot

Fetch a paper account snapshot before submitting an order:

```bash
quant live alpaca-paper-snapshot --from-env
```

Inspect the printed account ID, cash, buying power, and position count. Confirm
they match the intended Alpaca paper account.

## Tiny Paper Order

Submit one very small paper order:

```bash
quant live alpaca-paper-order \
  --from-env \
  --symbol "$QUANT_SMOKE_SYMBOL" \
  --side buy \
  --quantity 1 \
  --price "$QUANT_SMOKE_REFERENCE_PRICE" \
  --client-order-id "$QUANT_SMOKE_CLIENT_ORDER_ID"
```

The `--price` value is the local reference price for safety and audit records;
Alpaca executes the paper market order using its own paper market behavior.
Use a current price so the local cap and audit record are meaningful.

Expected output includes:

```text
Alpaca paper order:
Status:
Client order ID:
Order records:
Fill records:
Snapshot records:
```

If the order is rejected, stop and inspect the rejection reason. Do not retry
with a larger order until the cause is understood.

## Reconciliation

Run reconciliation against Alpaca paper broker state:

```bash
quant live alpaca-paper-reconcile --from-env
```

Expected result:

```text
Status: passed
Differences: 0
```

If status is `failed`, inspect:

```text
data/live/reconciliation/latest.json
```

Stop until the drift is explained.

## Artifact Review

Inspect the newest files in:

```text
data/live/orders/
data/live/fills/
data/live/account_snapshots/
data/live/reconciliation/latest.json
```

Check that:

- no API key or secret key appears in any artifact
- `broker_name` is `alpaca-paper`
- `broker_environment` is `paper`
- `account_id` is the expected sanitized account ID
- `client_order_id` equals `$QUANT_SMOKE_CLIENT_ORDER_ID`
- order status and fill status match what Alpaca paper shows
- reconciliation status is `passed`

## Cleanup Notes

Leave the artifacts in place unless they contain secrets. They are the audit
trail for this smoke run.

Unset credentials when the session is over:

```bash
unset QUANT_ALPACA_PAPER_API_KEY
unset QUANT_ALPACA_PAPER_SECRET_KEY
unset QUANT_ALPACA_PAPER_ACCOUNT_ID
unset QUANT_ALPACA_PAPER_URL_OVERRIDE
```

## After The Run

Record the outcome in your notes or commit message:

```text
Alpaca paper smoke run:
- date:
- symbol:
- client order ID:
- order status:
- reconciliation status:
- surprises:
```

Only consider scheduled Alpaca workflows after this runbook has passed at least
once and the resulting artifacts have been reviewed.
