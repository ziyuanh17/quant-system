# Short-Selling Risk Policy

The Alpaca paper strategy workflow supports intentional short positions only
through an explicit, bounded pre-trade risk policy. Short selling remains
disabled by default.

## Projected-Portfolio Check

Before broker submission, the workflow calculates the position and exposure
that would exist if the requested order filled completely:

```text
projected position = current signed position + signed order quantity
```

Signed quantities distinguish:

- selling part or all of a long position,
- opening or increasing a short position,
- covering part or all of a short position,
- opening or increasing a long position.

The check rejects new risk that would violate a configured limit. It still
allows risk-reducing orders, such as covering an existing short, even when
short selling has since been disabled or the existing position is already
over-limit.

## Required Configuration

To permit opening or increasing short positions, all controls must be set:

```text
QUANT_SHORT_SELLING_ENABLED=true
QUANT_MAX_SHORT_POSITION_NOTIONAL=...
QUANT_MAX_TOTAL_SHORT_EXPOSURE_PCT_EQUITY=...
QUANT_MAX_GROSS_EXPOSURE_PCT_EQUITY=...
QUANT_MIN_BUYING_POWER_BUFFER_PCT=...
```

If short selling is enabled while any limit is missing or invalid, config
loading fails before the workflow can reach Alpaca.

### Limit Meanings

- `QUANT_MAX_SHORT_POSITION_NOTIONAL`: maximum absolute short market value for
  the requested symbol after the order fills.
- `QUANT_MAX_TOTAL_SHORT_EXPOSURE_PCT_EQUITY`: maximum absolute value of all
  short positions divided by account equity.
- `QUANT_MAX_GROSS_EXPOSURE_PCT_EQUITY`: maximum absolute value of all long and
  short positions divided by account equity.
- `QUANT_MIN_BUYING_POWER_BUFFER_PCT`: minimum projected buying power retained
  after the order, divided by account equity.

The local buying-power calculation applies Alpaca's conservative 3% cushion to
new market short exposure.

## Current Safety Boundary

The workflow still fails closed while any broker order is unsettled. A future
version can include signed pending-order quantities in projected exposure, but
blocking overlapping orders is safer until that state is modeled reliably.

Alpaca asset shortability and daily easy-to-borrow status are not yet exposed
through the local broker protocol. Alpaca remains the final borrow-availability
gate for now. Adding an explicit local asset-borrow check is the next
short-selling risk increment.

## Rehearsal Gate

Do not enable short selling in the runtime `.env` or reload the recurring
schedule until:

1. the policy implementation and selected limits are reviewed,
2. unit and workflow checks pass,
3. a controlled paper rehearsal is explicitly approved,
4. resulting order, fill, snapshot, reconciliation, log, and dashboard
   artifacts are reviewed.

