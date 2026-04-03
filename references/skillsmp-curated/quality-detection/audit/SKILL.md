---
name: audit
description: Deep, multi-agent codebase quality audit. Spawns one focused agent per quality dimension in parallel, each going deep with evidence-based analysis, then synthesizes into a scored report. Use when you want a thorough assessment of a codebase's strengths, weaknesses, and risks. Also supports --checkpoint mode for layer coherence audits during orchestration.
---

# Codebase Audit

You are running a thorough, evidence-based codebase quality audit. Unlike a single-pass review, this audit spawns one focused agent per quality dimension — each agent goes deep on its area, then a synthesis agent produces the final report.

## Arguments

- **No args** — audit the current working directory
- **`--dimensions <list>`** — override auto-detection with a comma-separated list (e.g., `--dimensions security,dry-code-reuse,test-quality`)
- **`--checkpoint <sha>`** — Layer coherence mode. Scopes the audit to changes since the given commit SHA while cross-referencing the full codebase. Produces a `COHERENCE-REPORT` instead of a scored audit report. Used by the orchestrator at layer boundaries to catch cross-session quality issues.

## Step 1: Detect Project Structure

Before spawning agents, understand what you're auditing:

1. Read `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, or equivalent to identify languages and frameworks
2. List the top-level directory structure
3. Check for: frontend code (src/components, src/app, pages/), database layer (schema, migrations, models/), API routes (routes/, api/), CI config (.github/, .gitlab-ci.yml), test files
4. Summarize: tech stack, key directories, approximate codebase size

## Step 2: Select Dimensions

Quality dimensions are defined in the autoboard plugin's `standards/dimensions/` directory. Read each dimension file to get its name and checklist.

**Available dimensions:**
- `security` — Input validation, auth, secrets, injection prevention
- `error-handling` — Error types, recovery, logging, failure paths
- `type-safety` — Type coverage, boundary validation, schema contracts
- `dry-code-reuse` — Duplication, shared abstractions, single source of truth
- `test-quality` — Coverage, test types, critical path testing, TDD patterns
- `config-management` — Environment config, feature flags, secrets separation
- `frontend-quality` — Component reuse, state management, accessibility, responsiveness
- `data-modeling` — Schema design, indexes, migrations, query patterns
- `api-design` — Endpoint consistency, validation, versioning, error responses
- `observability` — Logging, metrics, tracing, alerting
- `performance` — Bottlenecks, N+1 queries, unbounded operations, caching
- `code-organization` — File structure, module boundaries, dead code, file sizes
- `developer-infrastructure` — CI/CD, lint enforcement, build reliability, local dev setup

**Skip conditions for full audit** (unless overridden by `--dimensions`):
- No frontend/UI code → skip `frontend-quality`
- No database/persistence layer → skip `data-modeling`
- No API routes → skip `api-design`
- All other dimensions included by default

**Skip conditions for checkpoint mode** (unless overridden by `--dimensions`):
- **Always include:** `dry-code-reuse`, `code-organization`, `security`, `error-handling`, `test-quality`
- **Include if layer touched that area** (use judgment based on `git diff {CHECKPOINT}..HEAD --stat` — glob patterns below are guidance, not programmatic filters; when in doubt, include the dimension):
  - `api-design` — diff contains files in `**/api/**`, `**/routes/**`, `**/handlers/**`
  - `frontend-quality` — diff contains `*.tsx`, `*.jsx`, files in `**/components/**`, `**/pages/**`
  - `type-safety` — diff contains files in `**/types/**`, `**/schema/**`, `**/models/**`
  - `data-modeling` — diff contains files in `**/migrations/**`, `**/schema/**`, `**/prisma/**`, `**/drizzle/**`
  - `performance` — diff contains files in `**/api/**`, `**/routes/**`, `**/queries/**`, `**/db/**`
  - `observability` — diff contains files in `**/api/**`, `**/routes/**`, `**/handlers/**`, `**/middleware/**`
  - `config-management` — diff contains files in `**/.env*`, `**/config/**`, `**/settings/**`
- **Never in checkpoint mode:** `developer-infrastructure` (deferred to completion-only full-spectrum audit)

Tell the user which dimensions will be audited and which were skipped (and why). Proceed without waiting for confirmation — the user can re-run with `--dimensions` to override.

## Step 3: Spawn Dimension Agents

Spawn ALL dimension agents in parallel using the Agent tool. Each agent is independent and read-only.

**For each selected dimension**, read the full content of its `standards/dimensions/{name}.md` file and include it in the agent prompt.

**Dimension agent prompt template:**

```
You are auditing a codebase for {DIMENSION_NAME} quality.
You are a specialist — focus ONLY on your dimension. Be thorough, be specific, be evidence-based.

## Your Checklist

{PASTE FULL CONTENT OF standards/dimensions/{name}.md}

## Project Context

- Tech stack: {detected stack from Step 1}
- Key directories: {detected structure from Step 1}
- Working directory: {cwd}

## How to Audit

You must be THOROUGH. Do not sample a few files — systematically review the codebase:

1. Use Glob to find ALL files relevant to your dimension (e.g., for security: all route handlers, middleware, auth files; for test-quality: all test files and the code they test)
2. Read each relevant file — not just the first few. For large codebases, prioritize high-risk areas but still scan broadly.
3. For each criterion in your checklist, use Grep to search for violations across the entire codebase. Count occurrences.
4. Quantify your findings: "found 15 instances across 6 files" is better than "some duplication exists"
5. Cite exact file paths and line numbers for every finding

## What to Report

For each finding:
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Description:** What's wrong, specifically
- **Evidence:** Exact file paths and line numbers. Quote the offending code if it's short.
- **Scope:** Systemic (appears across N files — specify N) or Localized (one file/area)
- **Fix:** Concrete remediation approach

Also report:
- **Strengths:** What's done well in this dimension, with evidence (files, patterns)
- **Risk at scale:** What breaks when this codebase serves millions of users
- **Patterns:** Recurring systemic issues (not one-offs)

## Anti-Bias Rules

- Do not inflate or deflate scores. Use the full 1-10 range.
- Do not manufacture criticism — if something is genuinely well-done, say so.
- Do not give generic advice. Every recommendation must reference specific code.
- If you cannot verify something, say so explicitly — do not guess.
- Distinguish between observed facts, inferences, and unknowns.

## Output Format

Use this EXACT format:

## {DIMENSION_NAME}: {SCORE}/10

### Findings
- **{SEVERITY}:** {description} — `{file}:{line}` — {evidence}. Scope: {systemic across N files | localized}.

### Systemic Patterns
- {Pattern observed across N files — describe the pattern and list affected files}

### Strengths
- {What's done well, with file paths and evidence}

### Risk at Scale
- {What breaks at 10M users, with reasoning grounded in what you observed}

### Score Justification
{Why this score. Calibration: 5-6 = acceptable mid-level, 7 = solid senior quality, 8 = strong, 9 = exceptional. Use the full range.}
```

Use `model: haiku` for dimension agents in full audit mode — they're doing focused reads and greps, not complex reasoning.

### Test Scenarios Injection (Checkpoint Mode)

When `test-quality` is in the selected dimensions for a checkpoint audit, read the project manifest (`docs/autoboard/{slug}/manifest.md`) and extract all `Key test scenarios` fields from task records. Inject these into the test-quality dimension agent's prompt as an additional section between the checklist and project context:

```
## Project Test Scenarios

The following test scenarios were specified in the manifest as important to cover:

{For each task with Key test scenarios:}
### {Task title}
{Key test scenarios content verbatim}

When auditing test quality, prioritize coverage of these scenarios. Flag as BLOCKING if tests
exist but don't cover the specified scenarios (happy-path-only when error paths were specified).
```

If the manifest has no `Key test scenarios` fields, omit this section from the prompt.

### Checkpoint Mode: Dimension Agent Prompt Template

When `--checkpoint` is provided, use this prompt instead of the full audit prompt above. Use `model: sonnet` — cross-referencing the full codebase against a diff requires stronger reasoning.

```
You are checking a codebase for {DIMENSION_NAME} coherence issues introduced by recent changes.

Multiple independent coding sessions just merged their work. Your job: find quality issues
that arise from these sessions working in parallel — problems no individual session could catch.

## Your Checklist

{PASTE FULL CONTENT OF standards/dimensions/{name}.md}

{IF dimension is test-quality AND manifest has Key test scenarios:
## Project Test Scenarios
(See "Test Scenarios Injection" section above for content and format)
}

## Project Context

- Tech stack: {detected stack from Step 1}
- Key directories: {detected structure from Step 1}
- Working directory: {cwd}
- Checkpoint: {CHECKPOINT SHA}

## How to Audit

1. Run `git diff {CHECKPOINT}..HEAD --stat` to see what files this layer changed. These changes
   are your starting point.
2. Read the changed files to understand what was added or modified.
3. Cross-reference against the FULL CODEBASE — not just the diff:
   - For each new function, utility, or component in the diff, grep the ENTIRE codebase for
     similar implementations. If `lib/utils/formatDate.ts` already exists and a session created
     `helpers/date.ts`, that's a BLOCKING DRY violation.
   - For conventions (naming, error handling, file organization, import patterns), examine the
     EXISTING codebase patterns first. New code should match what's already established, not
     just be internally consistent among sessions.
   - For security, check existing routes/endpoints for auth patterns. New routes should have
     the same protections as existing similar routes.
4. Quantify findings: "found in 3 files" is better than "some duplication exists."
5. Cite exact file paths and line numbers for every finding.

## Blocking Threshold

Mark BLOCKING for issues that meet any of these criteria:
- **Build-breaking:** won't compile, creates import errors, breaks existing tests
- **Agent-degrading:** will confuse, mislead, or slow down future AI sessions (dead code, naming inconsistencies, duplicated patterns, convention drift, unclear module boundaries, competing implementations)
- **User-impacting:** will hurt end-user experience in production (performance issues, missing error handling on user-facing paths, security gaps, bad data modeling)

The test: "if nobody ever looks at this, will it cause a problem for either the next AI session or the end user?" If yes, BLOCKING.

Mark INFO only for truly cosmetic issues — stylistic preferences, minor formatting, things that don't affect agent navigation, code correctness, or end-user experience.

## WIP Context — What NOT to Flag

This is work-in-progress code being built incrementally. Do NOT flag:
- Missing infrastructure (CI/CD, monitoring, observability)
- Incomplete features planned for future layers
- Pre-existing issues that were NOT caused or worsened by changes since the checkpoint
- Aspirational improvements ("would be nice to have...")
- Style preferences that don't affect cross-session coherence

## Anti-Bias Rules

- Do not manufacture criticism — if the new code integrates well, say so.
- Do not give generic advice. Every finding must reference specific code.
- If you cannot verify something, say so explicitly — do not guess.

## Output Format

## {DIMENSION_NAME}

### Findings
- **{BLOCKING|INFO}:** {description} — `{file}:{line}` {vs `{other_file}:{line}` if comparing}.
  Scope: {systemic across N files | localized}. Fix: {specific action}.

### Strengths
- {What's done well in this dimension, with evidence}

**Summary: {N} BLOCKING, {M} INFO**
```

## Step 4: Collect Reports

Wait for all dimension agents to complete. Concatenate their reports.

If any agent fails or returns an empty/malformed report, note it in the final output as "Dimension {name}: AUDIT FAILED — {reason}". Do not block the synthesis on one failed agent.

## Step 5: Synthesis

Spawn a synthesis agent with all dimension reports. This agent produces the final audit report.

**Synthesis agent prompt:**

```
You are synthesizing a multi-dimensional codebase audit. {N} specialized agents each went deep on one quality dimension. Their reports follow.

## Dimension Reports

{PASTE ALL DIMENSION AGENT OUTPUTS}

## Your Job

Produce the final audit report using the EXACT format below. Be rigorous, fair, and specific. Do not compress all scores into the 6-8 range — use the full scale.

# Codebase Audit Report

## Executive Summary

{1 paragraph: overall assessment of the codebase quality, key themes across dimensions}

**Overall Score: {X}/10**
**Engineering Level: {Junior | Mid-level | Senior | Senior II | Staff}**

## Scorecard

| Dimension | Score | Confidence | Key Finding |
|-----------|-------|------------|-------------|
| {name} | {N}/10 | {High/Med/Low} | {one-sentence summary} |

## Top Strengths

{Top 5 strengths across all dimensions, with evidence from the dimension reports. Reference specific files and patterns.}

## Top Weaknesses

{Top 10 weaknesses ordered by severity, with evidence. For each:}
- **{Severity}: {Title}** — {description}. Evidence: {from dimension report}. Scope: {systemic/localized}. Dimension: {which dimension flagged it}.

## Hidden Risks

{Cross-cutting risks that no single dimension fully captured. What breaks at scale? What are the compounding effects of multiple weaknesses? What would worry a staff engineer inheriting this codebase?}

## Top 10 Improvements by ROI

{Ordered by engineering leverage — impact relative to effort.}

| # | Improvement | Impact | Effort | Affected Areas |
|---|------------|--------|--------|----------------|
| 1 | {title} | {HIGH/MED/LOW} | {HIGH/MED/LOW} | {files/modules} |

For each improvement, include a 2-3 sentence description of the approach.

## Engineering Level Justification

{Why this level, not the one above or below. Be specific.}

Calibration:
- Junior: Gets things working, weak structure and safeguards
- Mid-level: Competent, some good patterns, inconsistent long-term thinking
- Senior: Strong ownership, solid abstractions, generally trustworthy
- Senior II: Consistently excellent judgment across architecture, correctness, scaling
- Staff: Unusually strong system design, clarity, leverage, maintainability

## Scoring Notes

The overall score is NOT an average of dimension scores. It reflects the holistic quality of the engineering system. A codebase with 9/10 security but 3/10 test quality is not a 6 — the weak dimension drags down overall trustworthiness. Weight by impact on: can you ship confidently? can a new engineer contribute safely? will this break under load?
```

### Checkpoint Mode: Synthesis

When `--checkpoint` is provided, skip the scored synthesis above. Instead, collect all dimension agent outputs and produce a `COHERENCE-REPORT` directly (no synthesis agent needed — just concatenate and summarize):

```
~~~COHERENCE-REPORT
## Layer Coherence Audit

**Dimensions checked:** {list}
**Changes scoped to:** {CHECKPOINT_SHA}..HEAD ({N} files changed)

### BLOCKING Issues
{For each, from all dimension agents:}
- **{Dimension} — {Category}:** {description} — `{file}:{line}` vs `{file}:{line}`. Fix: {specific action}.

{If none: "No blocking issues found."}

### INFO
{For each, from all dimension agents:}
- **{Dimension} — {Category}:** {description} — `{file}:{line}`.

{If none: "No informational findings."}

### Strengths
{Notable strengths from dimension agents — good integration patterns, consistent conventions, effective reuse of existing utilities.}

**Summary:** {N} BLOCKING, {M} INFO
~~~
```

Output the COHERENCE-REPORT directly to the conversation. The orchestrator will parse it.

## Rules

- **Read-only audit.** Do not create files, modify code, run builds, or install packages. The audit observes only.
- **Evidence over opinion.** Every finding must cite a file path. Every score must be justified. "Seems fine" is not evidence.
- **Dimension agents are independent.** Do not pass context between them. Each starts fresh and discovers its own findings.
- **Do not run tests or builds.** The audit is a static analysis. Running commands risks side effects in the user's environment. If the user wants runtime verification, they should use `/autoboard:verification`.
- **Output directly to conversation.** Do not write files unless the user explicitly asks for file output.
