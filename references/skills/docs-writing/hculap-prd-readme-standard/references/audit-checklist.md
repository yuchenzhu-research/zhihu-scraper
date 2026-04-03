# README Audit Checklist

Detailed procedure for auditing an existing README against the PRD-README v1 standard.

## Audit Process

### Phase 1: Quick Assessment (30 seconds)

Open the README and answer:
1. Can I tell what this project does in 10 seconds?
2. Can I tell if it's maintained in 10 seconds?
3. Is there a clear path to "try it now"?

If any answer is "no", the README needs work.

### Phase 2: Detailed Evaluation

Run each acceptance test and score pass/fail:

## Acceptance Test Details

### Test 1: What Is It? (10-second rule)

**Pass criteria:**
- Project name is visible immediately
- One-sentence value proposition exists
- Value proposition includes: what it does + for whom
- No jargon without explanation

**Common failures:**
- Starts with badges instead of description
- Description is too technical/assumes knowledge
- Description is marketing fluff without substance
- No description at all, just installation

**How to check:**
- Time yourself reading the first screen
- Can you explain the project to someone else?

**Score:** PASS / FAIL

---

### Test 2: Is It Maintained? (10-second rule)

**Pass criteria:**
- Status indicator present (active/beta/stable/deprecated/unmaintained)
- OR: Recent commits visible (within 6 months for active projects)
- OR: Clear version with date

**Common failures:**
- No status indicator
- Last update years ago with no explanation
- "Coming soon" or "WIP" without timeline
- Dead links to project resources

**How to check:**
- Look for explicit status line
- Check commit history if no status
- Verify links work

**Score:** PASS / FAIL

---

### Test 3: Quickstart Works (5-minute rule)

**Pass criteria:**
- Prerequisites listed with versions
- Install command is copy/pasteable
- Run command is copy/pasteable
- Works on clean environment

**Common failures:**
- Missing prerequisites
- Install requires undocumented dependencies
- Commands need modification before running
- Assumes existing project setup

**How to check:**
- Mentally (or actually) run through steps
- Do commands include placeholders that need replacing?
- Are all dependencies accounted for?

**Score:** PASS / FAIL

---

### Test 4: Runnable Example Exists

**Pass criteria:**
- At least one complete code example
- Example is syntactically correct
- Example can be copied and run as-is
- Example demonstrates core functionality

**Common failures:**
- Examples are pseudocode
- Examples have syntax errors
- Examples require additional setup not mentioned
- No examples, only API reference

**How to check:**
- Copy example code
- Would it run in a fresh file/project?

**Score:** PASS / FAIL

---

### Test 5: Expected Output Shown

**Pass criteria:**
- Quickstart shows what success looks like
- Output format is clear (JSON, text, UI, etc.)
- User knows when they've succeeded

**Common failures:**
- Commands shown but no output
- Vague "you should see results"
- Output shown but unclear what parts matter

**How to check:**
- After running Quickstart, would user know it worked?
- Is success unambiguous?

**Score:** PASS / FAIL

---

### Test 6: Navigation (10-second rule)

**Pass criteria:**
- Can find Installation in ≤10 seconds
- Can find Usage in ≤10 seconds
- Can find Support/Help in ≤10 seconds
- Table of contents if README is long (>500 lines)

**Common failures:**
- Flat structure with no headings
- Inconsistent heading hierarchy
- Important sections buried deep
- No table of contents for long READMEs

**How to check:**
- Scan headings only
- Use Ctrl+F for "Install", "Usage", "Support"

**Score:** PASS / FAIL

---

### Test 7: License Explicit

**Pass criteria:**
- License name stated in README
- Link to LICENSE file exists
- LICENSE file exists and matches stated license

**Common failures:**
- No license mentioned
- License mentioned but no LICENSE file
- LICENSE file exists but not mentioned in README
- Mismatched license information

**How to check:**
- Search for "License" or "MIT" or "Apache"
- Verify LICENSE file exists

**Score:** PASS / FAIL

---

### Test 8: Contribution Route Clear

**Pass criteria:**
- Contributing section exists OR
- Explicit statement that contributions not accepted
- If accepting: link to CONTRIBUTING.md or inline instructions
- If not accepting: explains how to report issues

**Common failures:**
- No mention of contributions
- "Contributions welcome!" with no guidance
- Points to non-existent CONTRIBUTING.md

**How to check:**
- Search for "Contributing" or "Contribute"
- Verify any linked files exist

**Score:** PASS / FAIL

---

### Test 9: Accessibility

**Pass criteria:**
- Headings follow hierarchy (no skipping levels)
- Images have alt text
- Links have descriptive text (not "click here")
- No walls of text (paragraphs <5 sentences)

**Common failures:**
- Jumps from # to ###
- Images with no alt text or alt="image"
- "Click here" or "this link" link text
- Long unbroken paragraphs

**How to check:**
- List all headings, verify hierarchy
- Search for `![` and check alt text
- Search for `](` and check link text

**Score:** PASS / FAIL

---

### Test 10: Appropriate Scope

**Pass criteria:**
- README focuses on getting started
- Deep details link elsewhere (docs/, wiki)
- Not trying to be comprehensive API documentation
- Length appropriate (<1000 lines for most projects)

**Common failures:**
- Full API reference in README
- Every configuration option documented
- README > 2000 lines
- No links to external documentation

**How to check:**
- Check README length
- Look for "see X for more details" links
- Is there a docs/ folder being used?

**Score:** PASS / FAIL

---

## Scoring Summary

| Test | Result | Issue | Priority |
|------|--------|-------|----------|
| 1. What is it? | | | |
| 2. Is it maintained? | | | |
| 3. Quickstart works | | | |
| 4. Runnable example | | | |
| 5. Expected output | | | |
| 6. Navigation | | | |
| 7. License explicit | | | |
| 8. Contribution route | | | |
| 9. Accessibility | | | |
| 10. Appropriate scope | | | |

**Total Score: X / 10**

## Priority Levels

**P0 - Critical (fix immediately):**
- Test 1 fail (users can't understand what it is)
- Test 3 fail (users can't try it)
- Test 7 fail (license missing = legal risk)

**P1 - High (fix soon):**
- Test 2 fail (trust issue)
- Test 4 fail (no working examples)
- Test 5 fail (success unclear)

**P2 - Medium (improve):**
- Test 6 fail (navigation)
- Test 8 fail (contribution path)

**P3 - Low (polish):**
- Test 9 fail (accessibility)
- Test 10 fail (scope)

## Audit Report Template

```markdown
# README Audit Report

**Project:** [name]
**Date:** [date]
**Score:** X / 10

## Summary

[1-2 sentence overall assessment]

## Test Results

### Passed (X tests)
- [Test name]: [brief note on what's good]

### Failed (X tests)

#### [P0] [Test name]
**Issue:** [specific problem]
**Fix:** [concrete action]

#### [P1] [Test name]
**Issue:** [specific problem]
**Fix:** [concrete action]

## Recommended Actions

1. [First priority fix]
2. [Second priority fix]
3. [Third priority fix]

## Auto-Fix Available

The following issues can be auto-fixed:
- [ ] [Issue 1]
- [ ] [Issue 2]

Would you like me to apply these fixes?
```

## Common Fix Patterns

### Missing value proposition
Add after title:
```markdown
# ProjectName

One-sentence description of what it does, for whom, and why it's different.
```

### Missing status
Add after title/description:
```markdown
Status: active | [Docs](link) | [Changelog](link) | [Issues](link)
```

### Missing prerequisites
Add before install:
```markdown
## Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0
```

### Missing expected output
Add after run command:
```markdown
You should see:
\`\`\`
Expected output here
\`\`\`
```

### Missing license section
Add near end:
```markdown
## License

MIT - see [LICENSE](LICENSE) for details.
```

### Missing contribution section
Add near end:
```markdown
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
```
Or:
```markdown
## Contributing

This project is not accepting contributions. Please file issues for bugs.
```
