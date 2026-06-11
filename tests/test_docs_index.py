"""Tests for the docs index builder and renderer.

Verifies collection categorization, doc type detection, title/summary
extraction, and markdown-to-HTML rendering.

"""

import json
import tempfile
from pathlib import Path

from quant.web.docs_index import (
     build_docs_index,
     render_doc,
     _categorize_collection,
     _categorize_doc_type,
     _extract_summary,
     _extract_title,
     _simple_markdown_to_html,
)


# ---------------------------------------------------------------------------
# Title and summary extraction
# ---------------------------------------------------------------------------


class TestTitleExtraction:
     def test_h1_becomes_title(self):
          assert _extract_title("# My Doc\n\nBody text") == "My Doc"

     def test_no_h1_returns_untitled(self):
          assert _extract_title("No heading here") == "Untitled"

     def test_h1_trims_whitespace(self):
          assert _extract_title("#  Hello World  \n\nBody") == "Hello World"


class TestSummaryExtraction:
     def test_first_paragraph(self):
          text = "# Title\n\nThis is the summary.\n\nMore text."
          assert "This is the summary." in _extract_summary(text)

     def test_skips_code_blocks(self):
          text = "# Title\n\n```\nxyzzy_secret_data\n```\n\nReal summary text."
          summary = _extract_summary(text)
          assert "xyzzy_secret_data" not in summary.lower()

     def test_truncates_long_text(self):
          text = "# Title\n\n" + "a " * 200
          assert len(_extract_summary(text)) <= 203


# ---------------------------------------------------------------------------
# Collection and doc type categorization
# ---------------------------------------------------------------------------


class TestCollectionCategorization:
     def test_incident_doc(self):
          assert _categorize_collection("actionable_paper_order_incident_2026-06-09.md") == "incidents_and_rehearsals"

     def test_launchd_doc(self):
          assert _categorize_collection("launchd_local_preflight.md") == "migration_and_scheduling"

     def test_alpaca_doc(self):
          assert _categorize_collection("alpaca_paper_adapter.md") == "safety_and_broker"

     def test_runbook_doc(self):
          assert _categorize_collection("runbook.md") == "operate"

     def test_default_is_project_management(self):
          assert _categorize_collection("random_notes.md") == "project_management"


class TestDocTypeCategorization:
     def test_incident_doc_type(self):
          assert _categorize_doc_type("actionable_paper_order_incident_2026-06-09.md") == "incident"

     def test_runbook_doc_type(self):
          assert _categorize_doc_type("alpaca_paper_smoke_runbook.md") == "runbook"

     def test_design_doc_type(self):
          assert _categorize_doc_type("alpaca_paper_adapter_design.md") == "design"

     def test_default_is_canonical_guidance(self):
          assert _categorize_doc_type("architecture.md") == "canonical_guidance"


# ---------------------------------------------------------------------------
# Markdown to HTML rendering
# ---------------------------------------------------------------------------


class TestMarkdownRendering:
     def test_headings(self):
          html = _simple_markdown_to_html("# H1\n## H2\n### H3")
          assert "<h1>H1</h1>" in html
          assert "<h2>H2</h2>" in html
          assert "<h3>H3</h3>" in html

     def test_code_blocks(self):
          html = _simple_markdown_to_html("```\ncode here\n```")
          assert "<pre><code" in html
          assert "code here" in html

     def test_inline_code(self):
          html = _simple_markdown_to_html("Use `quant run` to start.")
          assert "<code>quant run</code>" in html

     def test_bold_and_italic(self):
          html = _simple_markdown_to_html("**bold** and *italic*")
          assert "<strong>bold</strong>" in html
          assert "<em>italic</em>" in html

     def test_links(self):
          html = _simple_markdown_to_html("[link](https://example.com)")
          assert '<a href="https://example.com">link</a>' in html

     def test_unordered_list(self):
          html = _simple_markdown_to_html("- item one\n- item two")
          assert "<ul>" in html
          assert "<li>item one</li>" in html
          assert "<li>item two</li>" in html

     def test_horizontal_rule(self):
          html = _simple_markdown_to_html("---")
          assert "<hr>" in html


# ---------------------------------------------------------------------------
# End-to-end: build and render a real docs index
# ---------------------------------------------------------------------------


class TestEndToEnd:
     def test_build_index_from_real_docs(self):
          manifest = build_docs_index("docs")
          assert len(manifest.docs) > 0
          assert all(d.slug for d in manifest.docs)
          assert all(d.title for d in manifest.docs)
          assert all(d.collection in ("start_here", "operate", "safety_and_broker", "research_and_data", "migration_and_scheduling", "incidents_and_rehearsals", "project_management") for d in manifest.docs)

     def test_render_real_doc(self):
          doc = render_doc("architecture", "docs")
          assert doc["slug"] == "architecture"
          assert "title" in doc
          assert "renderedContent" in doc
          assert len(doc["renderedContent"]) > 0

     def test_render_missing_doc_returns_error(self):
          doc = render_doc("nonexistent_doc_xyz", "docs")
          assert "error" in doc

     def test_manifest_serialization(self):
          manifest = build_docs_index("docs")
          data = manifest.to_dict()
          assert "schema" in data
          assert "docs" in data
          assert "collections" in data
          assert data["schema"]["schemaVersion"] == "v1"
