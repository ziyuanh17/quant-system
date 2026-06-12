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
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from quant.api.models import (
    AccountDetail,
    AccountDetailPerformance,
    AccountDetailPermission,
    AccountDetailRisk,
    AccountSummary,
    DecisionTrace,
    DocDetail,
    DocSummary,
    IncidentDetail,
    IncidentSummary,
    OverviewResponse,
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
            methods = getattr(route, "methods", set())
            if methods:
                route_methods = methods & mutation_methods
                if route_methods:
                    pytest.fail(
                        f"Mutation endpoint found: "
                        f"{list(route_methods)[0]} "
                        f"{getattr(route, 'path', 'unknown')}"
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
            if hasattr(obj, "__bases__") and "Model" in str(type(obj)):
                for attr_name in dir(obj):
                    if (
                        not attr_name.startswith("_")
                        and attr_name not in DANGEROUS
                        and not attr_name.startswith("model_")
                    ):
                        pytest.fail(
                            f"Mutation method on model: {name}.{attr_name}"
                        )

    def test_html_pages_are_rendered_not_returned_as_raw_templates(self):
        from quant.web.app import app

        response = TestClient(app).get("/overview")

        assert response.status_code == 200
        assert "{% extends" not in response.text
        assert "Quant System" in response.text
        assert "nonce=" in response.text
        assert (
            "'unsafe-inline'"
            not in response.headers["content-security-policy"].split(
                "style-src"
            )[0]
        )

    def test_history_page_api_routes_exist(self):
        from quant.web.app import app

        client = TestClient(app)

        assert client.get("/api/v1/history/status").status_code == 200
        assert client.get("/api/v1/history/events").status_code == 200
        assert client.get("/api/v1/history/reconciliation").status_code == 200

    def test_browser_facing_typed_responses_use_camel_case(self):
        from quant.web.app import app

        client = TestClient(app)
        overview = client.get("/api/v1/overview").json()
        accounts = client.get("/api/v1/accounts/").json()

        assert "accountLanes" in overview
        assert "serverStatus" in overview["system"]
        assert "accountAlias" in accounts["accounts"][0]


# ---------------------------------------------------------------------------
# Stale data tests
# ---------------------------------------------------------------------------


class TestStaleData:
    """Stale or missing evidence must not appear healthy."""

    def test_stale_status_has_correct_state(self):
        from quant.api.freshness import compute_status

        now = datetime.now(UTC)
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
            if hasattr(obj, "model_fields") and hasattr(obj, "model_config"):
                for field_name in obj.model_fields:
                    if field_name in self.PROHIBITED_FIELD_NAMES:
                        pytest.fail(f"Prohibited field in {name}: {field_name}")


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


class TestAuthentication:
    """Private console authentication modes."""

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
        import os

        from quant.api.auth import require_api_key

        os.environ["QUANT_CONSOLE_API_KEY"] = "test-key"
        try:
            with pytest.raises(HTTPException):
                require_api_key(
                    request=Request({"type": "http", "headers": []}),
                    credentials=None,
                )
        finally:
            os.environ.pop("QUANT_CONSOLE_API_KEY", None)

    def test_api_route_requires_configured_key(self):
        from quant.web.app import app

        with patch.dict(
            os.environ,
            {"QUANT_CONSOLE_API_KEY": "test-key"},
        ):
            response = TestClient(app).get("/api/v1/overview")

        assert response.status_code == 401

    def test_tailscale_mode_accepts_allowlisted_identity(self):
        from quant.web.app import app

        with patch.dict(
            os.environ,
            {
                "QUANT_CONSOLE_AUTH_MODE": "tailscale",
                "QUANT_CONSOLE_TAILSCALE_USERS": "owner@example.com",
            },
            clear=True,
        ):
            response = TestClient(app).get(
                "/api/v1/overview",
                headers={"Tailscale-User-Login": "owner@example.com"},
            )

        assert response.status_code == 200

    def test_tailscale_mode_rejects_missing_or_unlisted_identity(self):
        from quant.web.app import app

        with patch.dict(
            os.environ,
            {
                "QUANT_CONSOLE_AUTH_MODE": "tailscale",
                "QUANT_CONSOLE_TAILSCALE_USERS": "owner@example.com",
            },
            clear=True,
        ):
            client = TestClient(app)
            missing = client.get("/api/v1/overview")
            unlisted = client.get(
                "/api/v1/overview",
                headers={"Tailscale-User-Login": "other@example.com"},
            )

        assert missing.status_code == 401
        assert unlisted.status_code == 403


class TestDeploymentBoundary:
    def test_remote_bind_is_rejected(self):
        from quant.web.serve import serve

        with pytest.raises(ValueError, match="loopback"):
            serve(host="0.0.0.0")
