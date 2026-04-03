---
name: documentation
description: "Apply when writing comments, docstrings, READMEs, ADRs, or any form of technical documentation. Trigger on mentions of documentation, comments, docstrings, ADRs, or explaining code. Focuses on concise, non-obvious documentation that captures business logic and decisions the code cannot express. Not for API contract documentation — use the api-design skill for that."
---

# Documentation Skill

Most documentation is wasted effort. It restates what the code already says, drifts out of sync within weeks, and creates a false sense of understanding. The developer who reads "increment counter by one" above `counter += 1` gains nothing. The developer who later changes the logic but not the comment is actively misled.

Good documentation captures what the code *cannot* say: why a decision was made, what business rule drove a validation, what constraint shaped the design, what alternatives were tried and rejected, and what will break if an assumption changes. This is the only documentation worth writing and maintaining.

The cost of documentation is not writing it — it's maintaining it. Every sentence you write is a sentence someone must keep accurate as the code evolves. Write less, write better, and keep it close to the code it describes.

---

## 1. Document What the Code Cannot Say

If a comment restates what the code does, it adds no value and will rot when the code changes. Ousterhout's rule: comments should describe things that are not obvious from the code. Martin's corollary: a comment is a failure to express intent in code — but some things genuinely cannot be expressed in code.

**Why, not what.** Document the reason behind the code, not a narration of the code. The code shows *what* happens; only a comment can explain *why* it happens this way instead of the obvious alternative.

**Business rules.** The most valuable comments explain domain logic: "Discounts cap at 30% because of supplier agreement §4.2" or "Users under 18 require parental consent per COPPA." These rules are invisible in the code's structure and critical for anyone modifying the logic.

**Constraints and edge cases.** Document non-obvious constraints: "This timeout must exceed the downstream service's P99 latency" or "Order of operations matters here because X depends on Y being initialized."

**What was rejected.** Sometimes the most important documentation explains what you did NOT do and why. "We considered caching here but rejected it because cache invalidation on price changes would be more complex than the performance gain." Without this, the next developer will waste time rediscovering the same dead end.

---

## 2. Conciseness is Respect

Every sentence in documentation must earn its place. Documentation that nobody reads is worse than no documentation — it creates a false sense of safety while consuming maintenance effort.

If a paragraph can be a sentence, make it a sentence. If a sentence can be cut entirely because the code is clear enough, cut it. Long documentation signals that either the code is too complex (fix the code) or the author is padding (fix the docs).

Ousterhout advises keeping comments close to the code they describe and as short as possible while remaining clear. Martraire calls this "just enough documentation" — the minimum documentation that prevents costly misunderstandings, and not a word more. Respect your reader's time. They are scanning, not reading.

---

## 3. Keep Documentation Alive

DRY applies to documentation. When documentation duplicates what the code says, one of them will become wrong — and it's always the documentation. Dead documentation is actively harmful: it misleads with false confidence.

**Co-locate with code.** Comments and docstrings live next to the code they describe. A design document in a wiki three clicks away will not be maintained. The closer documentation is to the code, the more likely it gets updated in the same commit.

**Generate, don't write.** API docs generated from OpenAPI specs, diagrams generated from code, changelogs generated from commits — generated documentation cannot drift from its source. Prefer generation over manual authoring wherever possible.

**Test your docs.** Executable specifications (BDD-style tests), doctests, README examples that CI runs — if the documentation is wrong, the build breaks. Martraire's insight: the best documentation is documentation that fails a test when it becomes inaccurate.

**Delete stale docs.** When you find documentation that no longer matches reality, delete it or update it immediately. Never leave it "for historical reference." Stale docs are not harmless artifacts — they are active liabilities that cause incorrect decisions.

---

## 4. The Ubiquitous Language

Evans's core insight in Domain-Driven Design: the code, the documentation, and the team's conversations should all use the same terms for the same concepts. If the business calls it a "fulfillment" and the code calls it a "shipment" and the docs call it a "delivery," there are three opportunities for miscommunication on every interaction.

Document the domain vocabulary explicitly — a living glossary that maps business terms to code constructs. When the language changes, update code, docs, and glossary together. Half-updated terminology is worse than consistently wrong terminology because it's harder to detect.

Martraire extends this: the ubiquitous language IS documentation. Code that uses domain terms correctly is self-documenting for domain concepts. A method named `fulfillOrder` with a parameter of type `ShippingAddress` tells you more than a page of prose about what the system does.

---

## 5. Architecture Decision Records

Michael Nygard's ADR format captures significant architectural decisions with their context and consequences. An ADR contains:

- **Title** — short noun phrase ("Use PostgreSQL for order storage")
- **Status** — proposed, accepted, deprecated, superseded
- **Context** — the forces at play, the problem being solved, the constraints
- **Decision** — what was decided and why
- **Consequences** — what follows from this decision, both positive and negative

ADRs are valuable because they capture the WHY at the moment the decision was made, when context is fresh. Six months later, nobody remembers why PostgreSQL was chosen over DynamoDB — the ADR does.

Keep ADRs in the repo, near the code they affect. They are the most cost-effective form of architecture documentation: small, focused, written once at decision time, and rarely needing updates. An ADR that is superseded is not deleted — it is marked as superseded with a link to its replacement, preserving the reasoning chain.

---

## 6. What to Document at Each Level

Different scopes need different documentation. Be surgical about what goes where.

**Inline comments** — only for non-obvious logic: tricky algorithms, workarounds for known bugs, business rules encoded in conditionals. Never for narration of what the code does line by line.

**Function/method docstrings** — for public API surfaces: what the function does (not how), parameter constraints, return value semantics, exceptions or errors thrown, and non-obvious preconditions. Skip docstrings for private or internal functions unless they are genuinely complex.

**Module/package docs** — the "why does this exist" level: what responsibility this module owns, what it does NOT handle, and key design decisions within the module.

**README** — orientation for newcomers: what this project or service does (one paragraph), how to run it, how to test it, where to find more detail. A README is a landing page, not a novel.

**ADRs** — significant architectural and technical decisions (see above).

**Runbooks** — operational procedures that humans follow when things break. A runbook should be specific, step-by-step, and tested against real incidents. Keep runbooks next to the alerting configuration they support.

---

## Applying This Skill

When writing or reviewing documentation, apply these defaults:
1. Never document what the code already says — document why, not what
2. Keep every comment and doc section as short as clarity allows
3. Place documentation as close to the code as possible
4. Prefer generated documentation over hand-written documentation
5. Use the domain's ubiquitous language consistently across code and docs
6. Record significant architectural decisions as ADRs in the repository
7. Delete or update stale documentation immediately upon discovery
8. Match documentation type to scope: inline for logic, docstrings for API, README for orientation, ADRs for decisions, runbooks for operations
