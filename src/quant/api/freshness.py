"""Freshness and status semantics for the web console.

Every status displayed by the console is derived from these rules.
No endpoint invents its own status logic — they all compose from
these building blocks.

Status values
-------------
The canonical status values and their meaning:

* ``healthy``       — evidence is present and within expected cadence
* ``degraded``      — evidence is present but outside expected cadence,
                       or a non-critical check failed
* ``failed``        — a critical check failed or data is corrupted
* ``running``       — a process is currently executing
* ``disabled``       — the feature is explicitly disabled (neutral when
                        expected)
* ``not_configured`` — the data source or feature is not configured
                        (neutral when expected)
* ``unknown``        — the system cannot determine the state
* ``stale``          — evidence exists but has not been refreshed
                        within the expected cadence

Freshness cadence
-----------------
Each data source has an expected maximum age (in seconds). If the
latest evidence is older than this threshold, the status transitions
from ``healthy`` to ``stale``.

Source                     Expected cadence
-----------------------------------------
workflow runs              1 hour  (3600s)
scheduler runs             1 hour  (3600s)
paper state                30 min  (1800s)
broker snapshot            5 min   (300s)
reconciliation             1 hour  (3600s)
data validation            1 hour  (3600s)
health check               5 min   (300s)
research evaluation        24 hours (86400s)
docs index                 1 day   (86400s)

"""

from datetime import datetime, timedelta, timezone

from quant.api.models import Severity, Status, StatusValue


# Expected maximum age for each data source (seconds).
# If evidence is older than this, the status becomes stale.
EXPECTED_FRESHNESS: dict[str, int] = {
     "workflow": 3600,
     "scheduler": 3600,
     "paper_state": 1800,
     "broker_snapshot": 300,
     "reconciliation": 3600,
     "data_validation": 3600,
     "health_check": 300,
     "research_evaluation": 86400,
     "docs_index": 86400,
     "system": 300,
}


def compute_status(
     observed_at: datetime | None,
     source: str = "system",
     expected_freshness: int | None = None,
     critical_failure: bool = False,
     non_critical_failure: bool = False,
     is_running: bool = False,
     is_disabled: bool = False,
     is_not_configured: bool = False,
) -> Status:
     """Derive a Status from raw observations and freshness rules.

    Parameters
    ----------
     observed_at :
         Timestamp of the latest evidence. ``None`` means no evidence.
     source :
         Data source key (used to look up expected cadence).
     expected_freshness :
         Override the default cadence for this source.
     critical_failure :
         A critical check failed (e.g. corrupted data).
     non_critical_failure :
         A non-critical check failed (e.g. late update).
     is_running :
         A process is currently executing.
     is_disabled :
         The feature is explicitly disabled.
     is_not_configured :
         The data source is not configured.

     Returns
    -------
     Status
         The derived status with freshness metadata attached.

     """
     now = datetime.now(timezone.utc)

      # Determine expected freshness
     if expected_freshness is None:
         expected_freshness = EXPECTED_FRESHNESS.get(source, 3600)

      # Build the status step by step
     state = StatusValue.HEALTHY
     severity = Severity.OK
     message = ""
     is_stale = False

      # Disabled and not_configured are neutral states
     if is_not_configured:
         state = StatusValue.NOT_CONFIGURED
         severity = Severity.OK
         message = "not configured"
         return Status(
             state=state,
             severity=severity,
             observed_at=now,
             source_updated_at=observed_at,
             expected_freshness_seconds=expected_freshness,
             is_stale=False,
             source_type=source,
             message=message,
         )

     if is_disabled:
         state = StatusValue.DISABLED
         severity = Severity.OK
         message = "disabled"
         return Status(
             state=state,
             severity=severity,
             observed_at=now,
             source_updated_at=observed_at,
             expected_freshness_seconds=expected_freshness,
             is_stale=False,
             source_type=source,
             message=message,
         )

      # No evidence at all
     if observed_at is None:
         state = StatusValue.UNKNOWN
         severity = Severity.WARNING
         message = "no evidence"
         return Status(
             state=state,
             severity=severity,
             observed_at=now,
             source_updated_at=None,
             expected_freshness_seconds=expected_freshness,
             is_stale=False,
             source_type=source,
             message=message,
         )

      # Process is running
     if is_running:
         state = StatusValue.RUNNING
         severity = Severity.OK
         message = "running"
         age = (now - observed_at).total_seconds()
         is_stale = age > expected_freshness
         if is_stale:
             severity = Severity.WARNING
             message = "running (stale)"
         return Status(
             state=state,
             severity=severity,
             observed_at=now,
             source_updated_at=observed_at,
             expected_freshness_seconds=expected_freshness,
             is_stale=is_stale,
             source_type=source,
             message=message,
         )

      # Check for failures
     age = (now - observed_at).total_seconds()
     is_stale = age > expected_freshness

     if critical_failure:
         state = StatusValue.FAILED
         severity = Severity.ERROR
         message = "critical failure"
     elif non_critical_failure:
         state = StatusValue.DEGRADED
         severity = Severity.WARNING
         message = "degraded"
     elif is_stale:
         state = StatusValue.STALE
         severity = Severity.WARNING
         message = f"stale ({int(age)}s, expected <{expected_freshness}s)"
     else:
         state = StatusValue.HEALTHY
         severity = Severity.OK
         message = "healthy"

     return Status(
         state=state,
         severity=severity,
         observed_at=now,
         source_updated_at=observed_at,
         expected_freshness_seconds=expected_freshness,
         is_stale=is_stale,
         source_type=source,
         message=message,
     )


def is_fresh(
     observed_at: datetime | None,
     source: str = "system",
     expected_freshness: int | None = None,
) -> bool:
     """Return True if the evidence for *source* is within expected cadence."""
     if observed_at is None:
         return False
     if expected_freshness is None:
         expected_freshness = EXPECTED_FRESHNESS.get(source, 3600)
     now = datetime.now(timezone.utc)
     age = (now - observed_at).total_seconds()
     return age <= expected_freshness


def age_seconds(observed_at: datetime | None) -> int | None:
     """Return the age in seconds of the latest evidence, or None."""
     if observed_at is None:
         return None
     now = datetime.now(timezone.utc)
     return max(0, int((now - observed_at).total_seconds()))
