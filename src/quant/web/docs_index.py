"""Build and serve a searchable index of repository documentation.

Scans ``docs/`` for Markdown files, extracts metadata (title, collection,
doc type, last modified time), and renders documents to HTML on demand.

Uses ``markdown2`` for robust, full-featured Markdown rendering with
safe-mode escaping. A legacy regex-based converter (_simple_markdown_to_html)
is retained for backward compatibility with existing tests.

"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import markdown2

# ---------------------------------------------------------------------------
# Collection taxonomy (hardcoded from design doc)
# ---------------------------------------------------------------------------

COLLECTIONS = (
    "start_here",
    "operate",
    "safety_and_broker",
    "research_and_data",
    "migration_and_scheduling",
    "incidents_and_rehearsals",
    "project_management",
)

# Filename pattern → collection mapping
COLLECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^actionable_paper_order_incident_", re.IGNORECASE),
        "incidents_and_rehearsals",
    ),
    (re.compile(r"^alpaca_paper_", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^controlled_alpaca_", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^read_only_alpaca_", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^launchd_", re.IGNORECASE), "migration_and_scheduling"),
    (re.compile(r"^mac_studio_", re.IGNORECASE), "migration_and_scheduling"),
    (re.compile(r"^live_broker_", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^short_selling_", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^broker_adapters", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^dry_run_trading", re.IGNORECASE), "research_and_data"),
    (re.compile(r"^data_quality", re.IGNORECASE), "research_and_data"),
    (re.compile(r"^strategy_evaluation", re.IGNORECASE), "research_and_data"),
    (re.compile(r"^trading_safety", re.IGNORECASE), "safety_and_broker"),
    (re.compile(r"^trading_stages", re.IGNORECASE), "start_here"),
    (re.compile(r"^operations", re.IGNORECASE), "operate"),
    (re.compile(r"^runbook", re.IGNORECASE), "operate"),
    (re.compile(r"^deployment", re.IGNORECASE), "operate"),
    (re.compile(r"^workflows", re.IGNORECASE), "operate"),
    (re.compile(r"^system_design_notes", re.IGNORECASE), "start_here"),
    (re.compile(r"^architecture", re.IGNORECASE), "start_here"),
    (re.compile(r"^roadmap", re.IGNORECASE), "project_management"),
    (
        re.compile(r"^codex_project_handoff", re.IGNORECASE),
        "project_management",
    ),
    (re.compile(r"^quant_system_web_app", re.IGNORECASE), "project_management"),
    (re.compile(r".*_rehearsal_", re.IGNORECASE), "incidents_and_rehearsals"),
    (re.compile(r".*_smoke_", re.IGNORECASE), "incidents_and_rehearsals"),
    (re.compile(r".*_design", re.IGNORECASE), "research_and_data"),
]

# Filename pattern → doc type mapping
DOC_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^actionable_paper_order_incident_", re.IGNORECASE),
        "incident",
    ),
    (re.compile(r".*_runbook", re.IGNORECASE), "runbook"),
    (re.compile(r".*_design", re.IGNORECASE), "design"),
    (re.compile(r".*_roadmap", re.IGNORECASE), "design"),
    (re.compile(r".*_handoff", re.IGNORECASE), "historical_evidence"),
    (re.compile(r".*_migration_", re.IGNORECASE), "historical_evidence"),
    (re.compile(r".*_rehearsal_", re.IGNORECASE), "historical_evidence"),
    (re.compile(r".*_smoke_", re.IGNORECASE), "historical_evidence"),
    (re.compile(r".*_diagnosis", re.IGNORECASE), "historical_evidence"),
]


class DocEntry:
    """Metadata for one documentation file."""

    __slots__ = (
        "slug",
        "title",
        "collection",
        "doc_type",
        "summary",
        "last_modified",
        "source_commit",
        "status",
        "superseded_by",
    )

    def __init__(
        self,
        slug: str,
        title: str,
        collection: str,
        doc_type: str,
        summary: str = "",
        last_modified: datetime | None = None,
        source_commit: str | None = None,
        status: str = "current",
        superseded_by: str | None = None,
    ) -> None:
        self.slug = slug
        self.title = title
        self.collection = collection
        self.doc_type = doc_type
        self.summary = summary
        self.last_modified = last_modified
        self.source_commit = source_commit
        self.status = status
        self.superseded_by = superseded_by

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for API response."""
        return {
            "slug": self.slug,
            "title": self.title,
            "collection": self.collection,
            "docType": self.doc_type,
            "summary": self.summary,
            "lastModified": self.last_modified.isoformat()
            if self.last_modified
            else None,
            "sourceCommit": self.source_commit,
            "status": self.status,
            "supersededBy": self.superseded_by,
        }


class DocManifest:
    """Complete index of documentation files."""

    __slots__ = ("schema_version", "generated_at", "docs", "collections")

    def __init__(
        self,
        docs: list[DocEntry],
        collections: tuple[str, ...] = COLLECTIONS,
        schema_version: str = "v1",
    ) -> None:
        self.schema_version = schema_version
        self.generated_at = datetime.now(UTC)
        self.docs = docs
        self.collections = collections

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for API response."""
        return {
            "schema": {
                "schemaVersion": self.schema_version,
                "generatedAt": self.generated_at.isoformat(),
            },
            "docs": [d.to_dict() for d in self.docs],
            "collections": list(self.collections),
        }


# ---------------------------------------------------------------------------
# Markdown extraction helpers
# ---------------------------------------------------------------------------


def _extract_title(text: str) -> str:
    """Extract the document title from the first H1 heading."""
    match = re.search(r"^# (.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled"


def _extract_summary(text: str, max_length: int = 200) -> str:
    """Extract a short summary from the first paragraph after the title."""
    lines = text.split("\n")
    # Skip title line and any blank lines after it
    summary_lines: list[str] = []
    found_title = False
    in_code_block = False
    for line in lines:
        if not found_title:
            if line.startswith("# "):
                found_title = True
            continue
        stripped = line.strip()
        # Toggle code block state
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped and not stripped.startswith("#"):
            summary_lines.append(stripped)
        if len("\n".join(summary_lines)) > max_length:
            break
    summary = " ".join(summary_lines).strip()
    return (
        (summary[: max_length - 3] + "...")
        if len(summary) > max_length
        else summary
    )


def _categorize_collection(filename: str) -> str:
    """Determine the collection for a document based on its filename."""
    for pattern, collection in COLLECTION_PATTERNS:
        if pattern.search(filename):
            return collection
    return "project_management"  # default


def _categorize_doc_type(filename: str) -> str:
    """Determine the doc type based on its filename."""
    for pattern, doc_type in DOC_TYPE_PATTERNS:
        if pattern.search(filename):
            return doc_type
    return "canonical_guidance"  # default


def _simple_markdown_to_html(text: str) -> str:
    """Convert Markdown to HTML using simple regex rules.

    Handles: headings, paragraphs, code blocks, inline code, lists,
    blockquotes, links, bold, italic, horizontal rules, and fenced code.
    Does not handle tables, images, or complex nesting.
    """
    lines = text.split("\n")
    html_lines: list[str] = []
    in_code_block = False
    in_list = False
    in_blockquote = False
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            content = "\n".join(paragraph_buffer)
            content = _inline_format(content)
            html_lines.append(f"<p>{content}</p>")
            paragraph_buffer.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_lines.append("</ul>")
            in_list = False

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            html_lines.append("</blockquote>")
            in_blockquote = False

    for line in lines:
        # Fenced code block
        if line.strip().startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                close_list()
                close_blockquote()
                flush_paragraph()
                lang = re.sub(r"[^a-zA-Z0-9_-]", "", line.strip()[3:].strip())
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(html.escape(line))
            continue

        # Blank line
        if not line.strip():
            flush_paragraph()
            close_list()
            close_blockquote()
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            close_list()
            close_blockquote()
            level = len(heading_match.group(1))
            html_lines.append(
                f"<h{level}>{_inline_format(heading_match.group(2))}</h{level}>"
            )
            continue

        # Blockquote
        if line.startswith("> "):
            flush_paragraph()
            close_list()
            if not in_blockquote:
                html_lines.append("<blockquote>")
                in_blockquote = True
            html_lines.append(_inline_format(line[2:]))
            continue

        # Unordered list
        list_match = re.match(r"^[-*+]\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            close_blockquote()
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_format(list_match.group(1))}</li>")
            continue

        # Ordered list
        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered_match:
            flush_paragraph()
            close_blockquote()
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            html_lines.append(
                f"<li>{_inline_format(ordered_match.group(1))}</li>"
            )
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_paragraph()
            close_list()
            close_blockquote()
            html_lines.append("<hr>")
            continue

        # Regular paragraph text
        paragraph_buffer.append(line)

    # Flush remaining content
    flush_paragraph()
    close_list()
    close_blockquote()

    return "\n".join(html_lines)


def _inline_format(text: str) -> str:
    """Apply inline Markdown formatting."""
    text = html.escape(text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _safe_link, text)
    return text


def _safe_link(match: re.Match[str]) -> str:
    """Render a Markdown link only when its target uses an allowed scheme."""
    label, target = match.groups()
    parsed = urlsplit(html.unescape(target))
    if parsed.scheme not in ("", "http", "https"):
        return label
    return f'<a href="{target}">{label}</a>'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_docs_index(docs_dir: str | Path = "docs") -> DocManifest:
    """Scan ``docs_dir`` and build a searchable index of Markdown files.

    Parameters
    ----------
    docs_dir : str | Path
        Path to the directory containing documentation files.

    Returns
    -------
    DocManifest
        Complete index with metadata for every Markdown file found.
    """
    docs_path = Path(docs_dir)
    entries: list[DocEntry] = []

    for filepath in sorted(docs_path.glob("*.md")):
        slug = filepath.stem
        text = filepath.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)

        entry = DocEntry(
            slug=slug,
            title=_extract_title(text),
            collection=_categorize_collection(filepath.name),
            doc_type=_categorize_doc_type(filepath.name),
            summary=_extract_summary(text),
            last_modified=mtime,
            status="current",
        )
        entries.append(entry)

    return DocManifest(docs=entries)


def render_doc(slug: str, docs_dir: str | Path = "docs") -> dict:
    """Render a single document to HTML with metadata.

    Parameters
    ----------
    slug : str
        Document filename stem (without .md extension).
    docs_dir : str | Path
        Path to the documentation directory.

    Returns
    -------
    dict
        Document detail with rendered HTML content.
    """
    filepath = Path(docs_dir) / f"{slug}.md"
    if not filepath.exists():
        return {"error": f"Document not found: {slug}"}

    text = filepath.read_text(encoding="utf-8")
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)

    rendered = markdown2.markdown(
        text,
        extras=["tables", "fenced-code-blocks", "breaks"],
        safe_mode="escape",
    )
    # Build a simple TOC from H2/H3 headings
    toc: list[dict[str, str]] = []
    for match in re.finditer(r"^(#{2,3})\s+(.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        toc.append({"level": f"h{level}", "title": title, "anchor": anchor})

    return {
        "slug": slug,
        "title": _extract_title(text),
        "collection": _categorize_collection(f"{slug}.md"),
        "docType": _categorize_doc_type(f"{slug}.md"),
        "summary": _extract_summary(text),
        "toc": toc,
        "renderedContent": rendered,
        "lastModified": mtime.isoformat(),
        "status": "current",
        "relatedComponents": [],
        "relatedDocuments": [],
        "glossaryTerms": [],
    }
