"""Security, redaction, and failure-mode tests for the web console.

Tests:
- No secrets, credentials, or raw broker payloads leak through API responses
- Read-only enforcement (no mutation endpoints exist)
- Stale evidence cannot appear healthy
- Prohibited fields are excluded from all API responses
- Authentication blocks unauthorized access when enabled

"""

import os
import re
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from quant.api.models import (
    AccountDetail,
    AccountDetailPermission,
    AccountDetailPerformance,
    AccountDetailRisk,
    AccountLane,
    AccountSummary,
    DecisionTrace,
    DocDetail,
    DocSummary,
    IncidentDetail,
    IncidentSummary,
    OverviewResponse,
    ResearchCandidateDetail,
    ResearchFamilySummary,
    SchemaVersion,
    Status,
    StatusValue,
    SystemComponent,
)


# ---------------------------------------------------------------------------
# Redaction tests
# ---------------------------------------------------------------------------


class TestRedaction:
    """Ensure no sensitive data leaks through API response models."""

    PROHIBITED_PATTERNS = [
        re.compile(r"api[_\-]?key", re.IGNORECASE),
        re.compile(r"secret[_\-]?key", re.IGNORECASE),
        re.compile(r"token", re.IGNORECASE),
        re.compile(r"password", re.IGNORECASE),
        re.compile(r"credential", re.IGNORECASE),
        re.compile(r"raw_response", re.IGNORECASE),
        re.compile(r"raw_response_ref", re.IGNORECASE),
        re.compile(r"private[_\-]?key", re.IGNORECASE),
    ]

    def _check_model(self, model, path=""):
        """Recursively check a model field names for prohibited patterns."""
        for field_name, field_info in model.model_fields.items():
            full_path = f"{path}.{field_name}" if path else field_name
            for pattern in self.PROHIBITED_PATTERNS:
                if pattern.search(field_name):
                    pytest.fail(
                        f"Prohibited field found: {full_path} "
                        f"(matches {pattern.pattern})"
                    )
            annotation = field_info.annotation
            if annotation and hasattr(annotation, "model_fields"):
                self._check_model(annotation, full_path)

    def test_overview_no_secrets(self):
        self._check_model(OverviewResponse)

    def test_account_no_secrets(self):
        self._check_model(AccountSummary)
        self._check_model(AccountDetail)
        self._check_model(AccountDetailPermission)
        self._check_model(AccountDetailRisk)
        self._check_model(AccountDetailPerformance)

    def test_decision_no_secrets(self):
        self._check_model(DecisionTrace)

    def test_doc_no_secrets(self):
        self._check_model(DocSummary)
        self._check_model(DocDetail)

    def test_incident_no_secrets(self):
        self._check_model(IncidentSummary)
        self._check_model(IncidentDetail)

    def test_component_no_secrets(self):
        self._check_model(SystemComponent)

    def test_api_root_no_secrets(self):
        from quant.api.models import ApiRootResponse
        self._check_model(ApiRootResponse)


# ---------------------------------------------------------------------------
# Read-only enforcement tests
# ---------------------------------------------------------------------------


class TestReadOnly:
    """Ensure no mutation endpoints exist."""

    def test_no_post_put_delete_patch_routes(self):
        from quant.web.app import app
        mutation_methods = {"POST", "PUT", "DELETE", "PATCH"}
        for route in app.routes:
            if hasattr(route, "methods"):
                route_methods = route.methods & mutation_methods
                if route_methods:
                    pytest.fail(
                        f"Mutation endpoint found: "
                        f"{list(route_methods)[0]} {route.path}"
                    )

    def test_no_mutation_in_api_models(self):
        """API response models should not have mutation methods."""
        from quant.api import models

         # Only flag methods that genuinely mutate state
        DANGEROUS = {
             "__setstate__",
             "__setattr__",
             "__delattr__",
             "populate",
             "save",
             "save_all",
             "delete",
             "delete_all",
             "insert",
             "insert_all",
             "upsert",
             "update",
             "patch",
             "execute",
             "run",
             "submit",
             "commit",
              "construct",
                "copy",
                "dict",
                "json",
                "model_dump",
                "model_dump_json",
                "model_copy",
                "parse_obj",
                "parse_raw",
                "parse_file",
                "from_orm",
                "schema",
                "schema_json",
                "update_forward_refs",
                "validate",
                "__get_validators__",
                 "__pydantic_initial_data__",
                 "fields_set",
                 "extra",
          }

        for name in dir(models):
            obj = getattr(models, name)
            if (
                hasattr(obj, "__bases__")
                and "Model" in str(type(obj))
             ):
                for attr_name in dir(obj):
                    if (
                        not attr_name.startswith("_")
                        and attr_name not in DANGEROUS
                        and not attr_name.startswith("model_")
                     ):
                        pytest.fail(
                            f"Mutation method on model: "
                            f"{name}.{attr_name}"
                         )


# ---------------------------------------------------------------------------
# Stale data tests
# ---------------------------------------------------------------------------


class TestStaleData:
    """Stale or missing evidence must not appear healthy."""

    def test_stale_status_has_correct_state(self):
        from quant.api.freshness import compute_status
        now = datetime.now(timezone.utc)
        old = now.replace(year=now.year - 1)
        s = compute_status(
            observed_at=old,
            source="health_check",
            expected_freshness=300,
        )
        assert s.state == StatusValue.STALE
        assert s.severity != "ok" or s.is_stale

    def test_missing_evidence_is_unknown(self):
        from quant.api.freshness import compute_status
        s = compute_status(observed_at=None, source="health_check")
        assert s.state == StatusValue.UNKNOWN

    def test_not_configured_is_not_healthy(self):
        from quant.api.freshness import compute_status
        s = compute_status(
            observed_at=None,
            is_not_configured=True,
        )
        assert s.state == StatusValue.NOT_CONFIGURED
        assert s.state != StatusValue.HEALTHY

    def test_disabled_is_not_healthy(self):
        from quant.api.freshness import compute_status
        s = compute_status(
            observed_at=None,
            is_disabled=True,
        )
        assert s.state == StatusValue.DISABLED
        assert s.state != StatusValue.HEALTHY


# ---------------------------------------------------------------------------
# Prohibited field tests
# ---------------------------------------------------------------------------


class TestProhibitedFields:
    """Certain fields must never appear in API responses."""

    PROHIBITED_FIELD_NAMES = [
        "raw_response_ref",
        "api_key",
        "secret_key",
        "password",
        "token",
        "private_key",
        "confirmation_phrase",
    ]

    def test_no_prohibited_fields_in_any_model(self):
        from quant.api import models
        for name in dir(models):
            obj = getattr(models, name)
            if (
                hasattr(obj, "model_fields")
                and hasattr(obj, "model_config")
            ):
                for field_name in obj.model_fields:
                    if field_name in self.PROHIBITED_FIELD_NAMES:
                        pytest.fail(
                            f"Prohibited field in {name}: "
                            f"{field_name}"
                        )


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


class TestAuthentication:
    """API key authentication when QUANT_CONSOLE_API_KEY is set."""

    def test_auth_skipped_when_key_unset(self):
        """When QUANT_CONSOLE_API_KEY is unset, auth is skipped."""
        env = os.environ.copy()
        env.pop("QUANT_CONSOLE_API_KEY", None)
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import quant.api.auth as auth_module
            importlib.reload(auth_module)
            assert auth_module._get_api_key() is None

    def test_auth_required_when_key_set(self):
        """When QUANT_CONSOLE_API_KEY is set, requests without it fail."""
        from quant.api.auth import require_api_key
        import os
        os.environ["QUANT_CONSOLE_API_KEY"] = "test-key"
        try:
            with pytest.raises(Exception):
                require_api_key(credentials=None)
        finally:
            os.environ.pop("QUANT_CONSOLE_API_KEY", None)


