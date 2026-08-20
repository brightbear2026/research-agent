---
name: deep-research-work
description: Execute evidence-backed six-phase research in this repository and deliver Markdown, HTML, evidence matrices, data tables, screenshots, and disclosed research gaps. Use when the user requests a deep research report, a research plan, or an autonomous research run with regular, plan, or execution mode in ChatGPT Work or Codex.
---

# Deep Research Work

Use the repository's deterministic workflow. Do not reproduce the workflow from memory or create a parallel policy.

## Initialize

1. Read `CLAUDE.md` for research integrity and deliverable rules.
2. Parse `depth=快速|标准|深度` (default `标准`) and `mode=regular|plan|execution` (default `regular`).
3. Create a new `projects/<topic-slug>/` directory with `tools/scaffold.py`; never reuse another topic's outputs.
4. Initialize `tools/workflow_policy.py init --root <project> --mode <mode>`.
5. Check whether the current host exposes the `diagram-design` skill. If available, write the selected/saved profile to `<project>/.diagram-design` (otherwise `profile: default`). If unavailable, use Mermaid as a non-blocking fallback. Do not add a workflow checkpoint for this choice.

## Follow the state machine

Run the six phases defined in `config/workflow_modes.yaml`: kickoff, survey, outline, research, assemble, deliver.

After each phase, run `tools/workflow_policy.py advance --root <project>`.

- If it returns `needs_confirmation`, ask for content confirmation and then run `advance --confirmed`.
- If it returns `chapters_not_registered` or `chapters_incomplete` (exit 4), remain in phase four and repair chapter progress.
- If it returns `stop`, stop. Plan mode must not enter formal research after the outline.
- Execution mode contains no repository-defined confirmation point. System permissions, authentication, CAPTCHA, paywalls, and site access controls still apply.

For unavailable sources, try a credible alternative, then record the failure with `record-failure`. Respect retry budgets and disclose the resulting gap; never loop indefinitely or bypass access controls.

During the research phase, register every outline chapter with `register-chapters`. Before dispatching a chapter, mark it `in_progress`; after both the matching draft Markdown and `.meta.json` exist, mark it `completed`. On resume, call `next-chapter` and skip completed chapters. Do not advance to assembly until `next_incomplete_chapter` is null.

## Produce trustworthy metadata

Make every chapter `.meta.json` conform to `templates/chapter_meta.schema.json` v2.

- Link claims, evidence, and sources through stable IDs.
- Never copy a conclusion into its supporting evidence.
- Preserve value, unit, statistical time, region, population or scope, definition, confidence, and limitations.
- For numeric evidence, missing unit, time, and region/scope is blocking.
- Record supporting and opposing evidence explicitly.
- Give standard/deep chapter conclusions at least two independent sources. Numeric claims always require two independent sources.
- Use `diagrams` only when a structured visual materially improves comprehension. Each item must use a globally reserved `fig_id`, write `diagrams/FIG-NNN.html`, reference `images/FIG-NNN.png` near the supported claim, and link at least one `source_id` plus one `supports_claim_id`. Generated diagrams explain verified evidence; they are not source evidence or original screenshots.

Run `tools/aggregate_meta.py --dry-run` before `--force`. The force operation backs up existing CSV files before replacement. Then run `tools/diagram_assets.py <project>/data/diagram_manifest.csv --root <project> --validate-only` before editing/delivery.

## Assemble and edit

Run `tools/merge.py <project> --require-meta`. This creates the assembled report, citations, merged metadata, and `data/claim_ledger.json`.

Edit only for structure, compression, clarity, and deduplication. Preserve factual meaning, uncertainty, opposing evidence, limitations, and citation identity. Do not introduce facts or sources.

## Capture and deliver

Use `tools/screenshot.py` with a finite deadline. Keep outputs under `images/`. Do not conceal browser automation or bypass login, CAPTCHA, paywalls, or WAF controls. Record failure category, reason, and alternative source.

After source screenshots, run `tools/diagram_assets.py <project>/data/diagram_manifest.csv --root <project>` to export audited PNGs and merge them into `figures.csv`. If no diagrams were planned, the empty manifest is a safe no-op. Preserve source HTML and label generated figures as compiled from public sources.

Generate HTML and evidence outputs, then run strict QC with both the assembled baseline and claim ledger. Strict QC also blocks uncited fact paragraphs, banned promotional phrases, hand-drawn box diagrams, overlong English quotations, stub-length reports, and insufficient independent support. Delivery is complete only when required artifacts exist, strict QC passes, and the state machine reports `workflow_status=completed`.
