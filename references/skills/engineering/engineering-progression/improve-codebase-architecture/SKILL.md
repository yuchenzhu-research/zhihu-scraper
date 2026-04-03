---
name: improve-codebase-architecture
description: Analyses codebase structure to identify unclear module boundaries and suggests architectural improvements that make the code easier to test and easier for agents to navigate. Invoke with /improve-codebase-architecture. Read-only — produces a prioritised findings report, no code changes.
context: fork
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# improve-codebase-architecture

Examines the codebase for structural patterns that make it hard to test and
hard for agents to reason about — then proposes targeted improvements. Focuses
on three failure modes: concepts scattered across too many small files,
testability-driven extractions that create false abstractions, and tight
coupling between modules that should be independent.

Read-only. No code is changed. Findings can feed into `/tdd` for refactors or
into `sdlc-audit Phase 6 (Full Refactor)` for larger decompositions.

## When to use

Invoke with `/improve-codebase-architecture` when:
- Agent tasks regularly require navigating many files to understand one concept
- Tests are brittle, slow, or require excessive mocking
- Module boundaries feel arbitrary or have grown organically without a plan
- A large refactor is planned and you want a structural baseline first

## Inputs

- **Scope** (optional): A subsystem path to limit analysis to. Omit to analyse
  the full project.

## Steps

### 1. Load context

Read `.abstract.md` (L0) then `.overview.md` (L1). Build a mental model of the
project's subsystems, their responsibilities, and their declared dependencies
before reading any source files.

### 2. Examine concept-to-file ratio

Identify concepts that require navigating many small files to understand fully:

```bash
# Count source files per directory to spot over-fragmentation
find ${SCOPE:-.} -type f \( -name "*.py" -o -name "*.ts" -o -name "*.go" \
  -o -name "*.rs" -o -name "*.js" \) \
  | awk -F/ 'NF>2{print $1"/"$2} NF==2{print $1}' \
  | sort | uniq -c | sort -rn | head -20
```

For directories with high file counts, cross-reference against `.overview.md`
component entries. Ask: can a reader understand the concept by reading one or
two files, or does it require ten or more? Flag directories where the answer
is "ten or more" and the files don't map to distinct domain concepts.

### 3. Identify testability-only extractions

Look for small modules that exist only because they were extracted to make
something else testable — not because they represent a real concept:

```bash
# Find modules imported only from test files
grep -rn "^from \|^import \|^require\|^use " ${SCOPE:-.} \
  --include="*.py" --include="*.ts" --include="*.go" --include="*.rs" \
  | grep -v "_test\.\|\.test\.\|spec\." \
  | awk -F: '{print $1}' | sort | uniq -c | sort -n | head -20
```

For modules with very few non-test callers, read the module. If it contains
only one or two small functions with no clear domain name, it is likely a
testability extraction. Flag it.

### 4. Identify tightly coupled modules

Find modules with high cross-subsystem import counts:

```bash
# Python example — adapt pattern to project language
grep -rn "^from \|^import " ${SCOPE:-.} --include="*.py" \
  | awk '{print $2}' | sort | uniq -c | sort -rn | head -20
```

For the top entries, read the importer and check whether the coupling is
necessary (shared domain model, shared types) or accidental (convenience
imports, circular dependencies, or functions that logically belong elsewhere).
Flag modules where more than half the imports cross subsystem boundaries
without an architectural reason.

### 5. Produce a prioritised findings report

Write findings to `docs/.tmp/architecture-findings.md`. For each flagged
pattern:

```markdown
### Finding: <short title>

**Pattern:** concept-scatter | testability-extraction | tight-coupling
**Location:** <file or directory>
**Symptom:** <what makes this hard to navigate or test>
**Priority:** high | medium | low

**Recommendation:**
<Concrete change — e.g. "Merge X and Y into a single module Z",
"Inline the helper back into its caller and delete the module",
"Introduce an interface at the boundary between subsystem A and B">

**Benefit:**
<How this improves agent navigation, testability, or both>

**Implementation path:**
<"Use /tdd for small refactors" or "Feed into sdlc-audit Phase 6 for
large decompositions">
```

Priority guide:
- **High** — eliminates a class of test brittleness or consistent agent confusion
- **Medium** — simplifies navigation without changing test strategy
- **Low** — cosmetic or nice-to-have restructuring

### 6. Present findings and ask what to act on

Print the prioritised findings. Ask the user which (if any) to act on now.
Remind them that implementation should be delegated:
- Small, contained refactors → `/tdd`
- Large decompositions or architectural restructuring → `sdlc-audit Phase 6`

## Expected output

- `docs/.tmp/architecture-findings.md` — prioritised findings with recommendations
- A summary printed to the conversation listing finding count by priority
- No source files modified
