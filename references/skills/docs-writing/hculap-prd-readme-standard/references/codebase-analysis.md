# Codebase Analysis for README Generation

This reference provides detailed guidance on analyzing a codebase to auto-detect the target reader and job-to-be-done for README generation.

## Analysis Sources

Analyze these sources in priority order to understand the project:

### 1. Package Manifest Files

**Primary sources:**
- `package.json` (Node.js)
- `pyproject.toml` / `setup.py` (Python)
- `Cargo.toml` (Rust)
- `go.mod` (Go)
- `pom.xml` / `build.gradle` (Java)
- `Gemfile` / `*.gemspec` (Ruby)

**Extract:**
- Project name and description
- Version
- Dependencies (indicates tech stack)
- Scripts/commands (indicates usage patterns)
- Keywords/classifiers (indicates domain)
- Author/license info

### 2. Existing README

Read existing README.md to understand:
- Current positioning and messaging
- Existing examples that work
- Gaps and missing information
- Style and tone preferences

### 3. Source Code Structure

Analyze directory structure for project type:

```
src/
├── cli.ts          → CLI tool
├── index.ts        → Library
├── server.ts       → API/Server
├── components/     → Frontend
└── commands/       → Command-based tool
```

**Indicators:**
- `bin/` or CLI entry point → CLI tool
- `src/index.*` with exports → Library
- `src/server.*` or `api/` → Backend service
- `src/components/` → Frontend application
- `src/pages/` → Web application
- `migrations/` → Database-backed application

### 4. Configuration Files

Look for:
- `.env.example` → Required environment variables
- `config/` or `*.config.*` → Configuration options
- `docker-compose.yml` → Deployment context
- `.github/workflows/` → CI/CD setup
- `Makefile` → Common commands

### 5. Test Files

Examine tests to understand:
- Primary use cases (what's tested)
- API surface (what's exported)
- Integration points (what external services)

### 6. Git History

Run these commands:
```bash
# Recent activity
git log --oneline -20

# Contributors
git shortlog -sn --all | head -10

# Most changed files (indicates core functionality)
git log --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20
```

## Deriving Step 0 Values

### Primary User

Determine from:

| Signal | Indicates |
|--------|-----------|
| CLI entry point | Developer using terminal |
| React/Vue/Angular | Frontend developer |
| Express/FastAPI | Backend developer |
| SDK naming | Platform-specific developer |
| `@types/*` deps | TypeScript developer |
| Domain keywords | Industry-specific user |

**Pattern:** "[Language/Role] developer who wants [category of tool]"

### Primary Job

Analyze the core workflow:

1. **What does installation provide?** (A CLI? A library? A service?)
2. **What's the first thing a user does after install?**
3. **What's the minimal successful outcome?**

**Pattern:** "[install step] → [configure step if needed] → [primary action]"

### Success in 5 Minutes

Define the simplest proof of working:

| Project Type | 5-Minute Success |
|--------------|------------------|
| CLI tool | Run command, see expected output |
| Library | Import, call function, get result |
| API server | Start server, hit endpoint, get response |
| Frontend | Run dev server, see UI in browser |
| Plugin | Install, activate, see effect |

## Output Format

After analysis, produce this structured output:

```
## Codebase Analysis Results

**Project Type:** [CLI / Library / API / Frontend / Plugin / Other]

**Primary User:** [e.g., "Node.js developer who wants a testing framework"]

**Primary Job:** [e.g., "install → write test file → run tests → see results"]

**Success in 5 Minutes:** [e.g., "Run a single test and see pass/fail output"]

**Key Features Detected:**
- [Feature 1]
- [Feature 2]
- [Feature 3]

**Prerequisites Detected:**
- [Runtime/version]
- [Required tools]
- [Environment variables]

**Existing Documentation:**
- README.md: [exists/missing] - [brief assessment]
- CONTRIBUTING.md: [exists/missing]
- LICENSE: [exists/missing]

**Recommended Sections:**
- [Section 1] - [why]
- [Section 2] - [why]
```

## Analysis Commands

Run these to gather information:

```bash
# Project manifest
cat package.json 2>/dev/null || cat pyproject.toml 2>/dev/null || cat Cargo.toml 2>/dev/null

# Directory structure (depth 2)
find . -maxdepth 2 -type d -not -path '*/\.*' -not -path './node_modules/*' | head -30

# Main entry points
ls -la src/ 2>/dev/null || ls -la lib/ 2>/dev/null

# Environment requirements
cat .env.example 2>/dev/null || cat .env.template 2>/dev/null

# Existing docs
ls -la *.md 2>/dev/null; ls -la docs/ 2>/dev/null

# Git info
git remote get-url origin 2>/dev/null
git describe --tags --abbrev=0 2>/dev/null || echo "No tags"
```

## Special Cases

### Monorepo

If `packages/` or `apps/` directory exists:
- Analyze root package.json for workspace config
- Identify primary package (often in `packages/core/` or first listed)
- README should describe the monorepo structure

### Framework Plugin

If project extends another framework:
- Identify parent framework from dependencies
- Primary user is "framework developer"
- Success is "install plugin, see effect in framework"

### Internal Tool

If no public package registry publishing:
- Focus on team-specific context
- Include internal links/resources
- May have different support routes
