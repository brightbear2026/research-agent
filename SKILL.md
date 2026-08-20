---
name: deep-research
description: "Use when user requests systematic deep research on a topic. Six-phase pipeline (survey → evidence → outline → chapter research → assembly+editing → delivery) producing Markdown+HTML dual-format reports with evidence matrices. Enforces no-fabrication red lines, source tiering, claim-ledger audits, workflow modes, and real screenshots. Ported from Claude Code research-agent v2."
version: 2.1.0
author: Hermes Agent (ported from brightbear2026/research-agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, deep-research, report, evidence, multi-agent]
    related_skills: []
---

# Deep Research Agent v2 (Hermes Port)

> **Platform note**: This `SKILL.md` is a Hermes-platform port of the research-agent project.
> The canonical Claude Code + Codex entry points are `.claude/commands/deep-research.md` and `.claude/skills/deep-research/SKILL.md`.
> This file adapts the workflow for Hermes-specific tooling (`delegate_task`, `hermes chat -t file`, `clarify`).
> If this port diverges from the canonical workflow, the canonical files take precedence.

Six-phase deep research pipeline that produces Markdown + HTML dual-format reports with evidence matrices, claim-ledger audits, and workflow state machine. Domain: tech/industry. Enforces strict no-fabrication red lines, source tiering (A/B/C/D), cross-verification, claim-ledger drift detection, and real Playwright screenshots.

## When to Use

- User requests systematic, broad, deep, verifiable research on a topic
- User wants a structured report (not a quick answer)
- Research requires source citation, evidence matrices, cross-verification

Don't use for: quick factual lookups, single-question answers, or research that doesn't need formal citation.

## Prerequisites

This skill's tools require `uv`. Before first use, verify:

```bash
cd <skill_dir> && uv sync && uv run playwright install chromium
```

Check environment with:
```bash
cd <skill_dir> && uv run python tools/check_env.py
```

## Red Lines (absolute — read `CLAUDE.md` for the canonical, complete rules)

1. **NO FABRICATION**: papers, authors, quotes, data, URLs, screenshots, dates — never invent. If unconfirmable, write「暂未找到可靠公开来源」.
2. **Source tiering**: A (primary) / B (authoritative) / C (media) / D (low). Key conclusions need ≥2 independent sources, not relying solely on C/D.
3. **Facts vs Opinions**: use inline tags 【事实】【观点·姓名·机构·YYYY-MM-DD】【机构观点·机构·日期】【争议】【研究判断】【推测】.
4. **Real screenshots only**: Playwright captures via `tools/screenshot.py`. Failed captures get placeholder + index. No AI-generated/fabricated images.
5. **Tool-level isolation for editor**: report-editor runs in a file-only Hermes process (`-t file`) — physically incapable of web access.
6. **Claim-ledger drift detection**: editor cannot introduce new numbers/dates/entities/certainty-upgrades beyond the assembled report. QC `--claim-ledger` blocks violations.

## What's New in v2.1 (vs v2.0)

1. **Enhanced QC quality gates**: fact citation locality check (each 【事实】 must have same-paragraph [n] citation), banned phrase detection, ASCII box-drawing detection, English quote length limits, source independence verification via `source_identity.py`.
2. **Source identity module** (`tools/source_identity.py`): URL canonicalization (strips tracking params, normalizes www/DOI/arXiv versions) and source independence grouping (by org/domain, not just URL).
3. **Chapter progress tracking** (`workflow_policy.py register-chapters`): register chapters in Phase 4, track per-chapter status (pending/in_progress/completed/failed), resume from next incomplete chapter after interruption.
4. **Minimum body character thresholds**: 快速≥4000, 标准≥10000, 深度≥18000 non-whitespace characters — blocks placeholder drafts.
5. **Scaffold path safety**: projects must be inside `projects/` directory, prevents path traversal.
6. **check_env.py**: verifies Python version, Playwright package, and Chromium binary consistency.
7. **Evidence independence**: chapter conclusions need ≥2 independent sources (by organization/domain), not just ≥2 source_ids that may be from the same org.
8. **Report depth parameter fixed**: merge.py now correctly propagates the depth parameter from the user-specified value.

## Workflow Modes (mode parameter)

| Mode | Param | In-flow confirmations | Execution scope | Use case |
|------|-------|----------------------|-----------------|----------|
| Regular | mode=regular | 3: kickoff, survey, outline | Complete all 6 phases | Want to calibrate scope, coverage, outline step by step |
| Plan | mode=plan | 1: after outline | Stops after outline, no report | Only need research plan, question tree, source strategy |
| Execution | mode=execution | 0 | Runs all 6 phases continuously | Goals and scope clear, minimize flow waits |

## Pipeline Overview

| Phase | Name | Checkpoint (mode-dependent) |
|-------|------|-----------------------------|
| 0 | Parse & init | No |
| 1 | Research kickoff | Yes (regular only) |
| 2 | Broad survey | Yes (regular) |
| 3 | Argument map & outline | Yes (regular/plan) |
| 4 | Chapter deep research | No |
| 5 | Deterministic assembly + editing | No |
| 6 | Delivery (screenshots, HTML, QC) | No |

## Phase 0: Parse & Initialize

1. **Each topic starts fresh** — do NOT read other topics under `projects/` as background input unless user explicitly requests.
2. Parse `depth` (default: 标准/standard) and `mode` (default: regular) from user args.
3. Project dir = `projects/<topic-slug>` (kebab-case). One slug per topic, never reuse.
4. Scaffold: `cd <skill_dir> && uv run python tools/scaffold.py projects/<slug>`
5. Initialize workflow state machine: `uv run python tools/workflow_policy.py init --root projects/<slug> --mode <mode>`
6. Check whether this harness exposes the `diagram-design` skill. If available, write the selected/saved profile to `projects/<slug>/.diagram-design` (otherwise `profile: default`). If unavailable, record a Mermaid fallback and continue without a new checkpoint.
7. Create todo list with phases 1-6, mark phase 1 in_progress.

## Phase 1: Research Kickoff

Write output to `sources/stage1_kickoff.md`:
1. Topic definition & boundaries.
2. **Concept decomposition & disambiguation (critical, cannot skip)**.
3. **Glossary** `data/glossary.md`: all core terms. Every researcher subagent reads this first.
4. **≥15 research questions**, categorized.
5. Chinese+English keyword matrix.
6. Search strategy, expected source types, research risks.

→ Call `uv run python tools/workflow_policy.py advance --root projects/<slug>`. If returns `needs_confirmation` (exit 3), use `clarify` tool. After user confirms, `advance --confirmed`.

## Phase 2: Broad Survey

Read the Phase 2 source dimensions from the canonical `.claude/commands/deep-research.md` before running the survey, then write the resulting lists to `sources/stage2_survey.md`. Do not maintain a separate fixed dimension list here; this keeps Hermes aligned when the canonical workflow adds source types such as broker/investment-bank research.

→ Call `advance`. Confirm if `needs_confirmation`.

## Phase 3: Argument Map & Formal Outline

1. Produce `sources/stage3_argument_map.yaml`.
2. Produce `sources/stage3_outline.md` (three-level outline).
3. Each chapter lists: reader question, one-line conclusion, role, dependencies, target word count, evidence needed.
4. Plan Diagram Design only when a relationship, architecture, flow, timeline, quadrant, or competitive landscape is materially clearer than prose/table. Usually cap at two per chapter and record `fig_id`, visual type, size, detail, profile, source IDs, and supported claim IDs.

→ Call `advance`. If returns `stop` (plan mode), stop here.

## Phase 4: Chapter Deep Research (delegate researcher subagents)

1. Register chapters: `uv run python tools/workflow_policy.py register-chapters --root projects/<slug> --chapter ch01 --chapter ch02 ...`
2. For each chapter, write a research card (based on `templates/research_card.md`).
   Reserve all screenshot and generated-diagram `fig_id` values globally before parallel dispatch.
3. **Dispatch researcher subagent via `delegate_task`**. Load the canonical `.claude/agents/researcher.md` as context; `references/researcher_brief.md` is only a pointer and must not be used as the prompt by itself.
4. Before dispatch: `workflow_policy.py chapter --root projects/<slug> --chapter <chNN> --status in_progress`
5. After completion: `workflow_policy.py chapter --root projects/<slug> --chapter <chNN> --status completed`
6. If interrupted: `workflow_policy.py next-chapter --root projects/<slug>` resumes from first incomplete chapter.
7. Independent chapters can run in parallel (`delegate_task(tasks=[...])`).
8. Each researcher outputs `report/_draft_<chNN>_<slug>.md` + `.meta.json` (schema v2).

**IMPORTANT — subagent timeout mitigation**: `delegate_task` has a ~600s timeout. For web-heavy research, split large chapters or have the orchestrator write chapters directly when sufficient Phase 2 data exists. Monitor batch completion and re-dispatch or self-complete timed-out chapters.

→ Call `advance`.

## Phase 5: Deterministic Assembly + Editor

### Step 1: Merge (generates claim ledger)
```bash
cd <skill_dir> && uv run python tools/merge.py projects/<slug> --require-meta --title "报告标题"
```
This deduplicates source tags, assigns global `[n]` citations, generates `data/citations.csv`, `data/chapter_meta.json`, `data/claim_ledger.json`, and `report/_assembled_report.md`.

### Step 2: Aggregate metadata (schema v2)
```bash
cd <skill_dir> && uv run python tools/aggregate_meta.py --root projects/<slug> --dry-run  # validate first
cd <skill_dir> && uv run python tools/aggregate_meta.py --root projects/<slug> --force    # then aggregate
cd <skill_dir> && uv run python tools/diagram_assets.py projects/<slug>/data/diagram_manifest.csv --root projects/<slug> --validate-only
```

### Step 3: Editor (TOOL-LEVEL ISOLATED — critical red line)
```bash
hermes chat -q "<contents of .claude/agents/report-editor.md plus the project path>" -t file --yolo
```

`references/report_editor_brief.md` is only a pointer. Passing its six-line contents as the editor prompt is not sufficient.

### Step 4: Post-edit QC (with claim-ledger audit)
```bash
cd <skill_dir> && uv run python tools/qc.py --root projects/<slug> \
  --report projects/<slug>/report/research_report.md \
  --citation-baseline projects/<slug>/report/_assembled_report.md \
  --claim-ledger projects/<slug>/data/claim_ledger.json \
  --skip-links --depth <depth>
```

→ Call `advance`.

## Phase 6: Delivery

1. **Screenshots** (with deadline control):
   ```bash
   cd <skill_dir> && uv run python tools/screenshot.py projects/<slug>/data/screenshot_manifest.csv --root projects/<slug> --deadline-seconds 600
   ```
2. **Diagram Design assets**: `uv run python tools/diagram_assets.py projects/<slug>/data/diagram_manifest.csv --root projects/<slug>`. These are explanatory assets compiled from verified public sources, never original evidence screenshots. An empty manifest is a safe no-op.
3. **Render HTML**: `uv run python tools/render_html.py projects/<slug>/report/research_report.md --root projects/<slug>`
4. **Evidence matrix**: `uv run python tools/evidence.py --root projects/<slug>`
5. **Final QC** (must pass with `--strict`):
   ```bash
   cd <skill_dir> && uv run python tools/qc.py --root projects/<slug> \
     --citation-baseline projects/<slug>/report/_assembled_report.md \
     --claim-ledger projects/<slug>/data/claim_ledger.json \
     --depth <depth> --strict
   ```
6. **Record advisory QC debt**: `uv run python tools/workflow_policy.py record-debt --root projects/<slug>`.
7. Write `projects/<slug>/README.md`, including the core QC result and advisory debt summary.
8. **Deliver to user**: copy all outputs to delivery folder (see Delivery section).
9. Report to user: paths to MD + HTML + evidence matrix + screenshots/generated diagrams + QC results.

→ Call `advance`. Must get `workflow_status=completed`.

## Delivery Path

Reports are delivered as a standalone folder. By default, deliver to the user's preferred documents directory (or as specified by the user); otherwise use the project directory:

```
<delivery-dir>/<报告名>/
├── <报告名>.html          (self-contained HTML report)
├── <报告名>.md            (Markdown source)
├── README.md             (overview & chapter index)
├── glossary.md           (terminology)
├── citations.csv         (numbered citations)
├── chapter_meta.json     (structured metadata)
├── claim_ledger.json     (claim drift audit baseline)
├── images/               (screenshots and figures, if any)
├── diagrams/             (auditable Diagram Design HTML sources, if any)
└── evidence/
    ├── summary.md
    ├── evidence_matrix.csv
    ├── controversy_matrix.csv
    └── research_gaps.md
```

## Inline Tags (Markdown and HTML shared)

- `【事实】` objective fact (needs source)
- `【观点·姓名·机构·YYYY-MM-DD】` person's opinion
- `【机构观点·机构·日期】` institutional position
- `【争议】` disagreement exists
- `【研究判断】` evidence-based comprehensive judgment
- `【推测】` hypothesis without sufficient evidence

## Source Tag Format (used in drafts, resolved by merge.py)

```
[[SRC|<type>|<author/org>|<title>|<publication/site>|<publish-date>|<url>|<access-date>|<tier A/B/C/D>]]
```

## Depth Settings

- **快速(quick)**: 3-5 chapters, ~10-20k chars, ≥1 A/B source for key conclusions, screenshots as needed.
- **标准(standard)**: 5-8 chapters, ~20-40k chars, ≥2 independent sources with A/B tier, mandatory screenshots for key pages.
- **深度(deep)**: 6-10 chapters, up to 60k chars, standard + multi-round counter-verification per chapter + full screenshots.

Minimum body character thresholds (non-whitespace): 快速 ≥ 4,000 / 标准 ≥ 10,000 / 深度 ≥ 18,000.

## Always Follow

- Never fabricate; if unconfirmable write「暂未找到可靠公开来源」.
- Every important fact has a source, every data point has a methodology note, every person's opinion has a primary source.
- Actively search for counter-arguments.
- Screenshots, links, citation closure, claim-ledger all verified by `qc.py` all-green.
- All "currently/as of/latest" must have explicit dates.
- No evidence-free platitudes. Banned phrases: 众所周知/毫无疑问/必将/彻底改变/颠覆一切/市场前景无限/具有重大意义.
- Prefer Diagram Design for useful structured explanatory visuals when its skill is available; otherwise use Mermaid. Never use ASCII box-drawing.
- Images inline at supporting arguments, not in appendix.

## Common Pitfalls

1. **Skipping concept disambiguation** — multi-concept topics need each concept defined independently + relationship analysis.

2. **Editor with web access** — the report-editor MUST run with `-t file` toolset.

3. **Concentrating screenshots at chapter end** — screenshots must be inline at the argument they support.

4. **Using ASCII box diagrams** — use Diagram Design when available and worthwhile, otherwise Mermaid.

5. **Reusing old project dirs** — each topic gets its own slug directory.

6. **Reading other topics as background** — each research run starts fresh.

7. **Researcher subagent meta.json format mismatch** — `aggregate_meta.py` expects schema v2 objects. If aggregate fails, run `tools/migrate_chapter_meta.py`.

8. **Researcher subagent timeout** — split large chapters or self-complete when Phase 2 data is sufficient.

9. **Playwright chromium version mismatch** — run `check_env.py` before starting. If it fails, run `uv run playwright install chromium`.

10. **Workflow state machine** — always call `workflow_policy.py advance` after each phase. Use `register-chapters` in Phase 4. Exit code 3 = needs_confirmation; return `stop` = must halt.

11. **Claim-ledger drift** — after editing, QC `--claim-ledger` blocks delivery if editor introduced new facts.

12. **Depth not propagated** (v2.1 fixed) — ensure the `depth` parameter from user input is correctly reflected in frontmatter and QC. If merge.py outputs depth as "标准" when user specified "深度", manually fix frontmatter before rendering.

13. **Never bypass strict QC** — if Markdown tables or Mermaid blocks trigger readability errors, fix the detector or report structure and rerun `qc.py --strict`. A non-strict pass is diagnostic only and is never the final delivery gate.

## Verification Checklist

- [ ] Confirmation points match the state machine: regular confirms kickoff/survey/outline; plan confirms outline only; execution has no repository-defined confirmation.
- [ ] Phase 4: chapters registered via `register-chapters`, all drafts collected with `.md` + `.meta.json` pairs (schema v2)
- [ ] Phase 5: merge.py ran, aggregate_meta passed, editor ran with `-t file`, post-edit QC + claim-ledger audit passed
- [ ] Phase 6: screenshots captured, Diagram Design assets exported (or manifest empty), HTML rendered, evidence.py ran, `qc.py --strict --claim-ledger` passed, and `record-debt` completed.
- [ ] No `[[SRC` tags remain in final report
- [ ] No production-process text in reader text
- [ ] All inline images near supporting arguments
- [ ] Every generated diagram has source HTML, PNG, `figures.csv` entry, source IDs, supported claim IDs, and a nearby body reference; Mermaid is used only as fallback
- [ ] Workflow state machine reached `workflow_status=completed`
- [ ] Report delivered to `<delivery-dir>/<报告名>/`
