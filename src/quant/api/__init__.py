"""Read-only API package for the quant-system web console.

All models in this package are sanitized API response schemas. They are
separate from domain models in ``quant.models`` to enforce the rule that
the browser must never read arbitrary runtime files directly.

Security contract
-----------------
* No secrets, credentials, raw broker payloads, or unredacted account IDs
  are exposed through these schemas.
* Every status field carries freshness metadata so stale or missing evidence
  cannot silently appear healthy.
* Unavailable evidence is explicitly labeled ``not_configured`` or
  ``unavailable`` rather than being omitted.

"""
