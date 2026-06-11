"""Web console package for the quant-system operations dashboard.

This package serves the authenticated read-only web console. It is separate
from the API models in ``quant.api`` to keep routing, templating, and static
file concerns out of the schema definitions.

Tech stack
----------
* Backend:  FastAPI (Pydantic-native, auto OpenAPI)
* Frontend: HTMX + Jinja2 templates (Python-only, no build step)
* Charts:   Chart.js (CDN)
* Markdown: marked.js (CDN)

"""
