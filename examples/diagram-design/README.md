# Diagram Design example

This public example demonstrates the repository's audited Diagram Design path:

1. The editable, static source lives at `diagrams/FIG-101.html`.
2. `data/diagram_manifest.csv` records provenance and the supported claim.
3. `tools/diagram_assets.py` validates the HTML and exports `images/FIG-101.png`.
4. The exporter merges the asset into `data/figures.csv` for report captions and QC.

Regenerate the PNG from the repository root:

```bash
uv run python tools/diagram_assets.py \
  examples/diagram-design/data/diagram_manifest.csv \
  --root examples/diagram-design --force
```

The example contains no private research data and makes no external factual claim. It visualizes the repository workflow itself.
