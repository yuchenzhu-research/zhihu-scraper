---
name: defensive-programming
description: "Apply when writing code that must be hard to misuse: immutability, visibility, contracts, assertions, resource safety, and type-level invariant enforcement. Trigger on mentions of const, encapsulation, access control, defensive coding, RAII, or 'harder to misuse.' Not for security against adversarial input — use the security skill for that. Language-specific idioms are in references/."
---

# Defensive Programming Skill

Write code that is hard to misuse, hard to break accidentally, and hard to silently corrupt. In a large codebase, every mutable variable is a question ("who changes this and when?"), every public symbol is a promise ("this is part of the contract"), and every unvalidated input is a bet ("callers will always get this right").

Defensive programming minimizes these questions, promises, and bets.

**Language-specific idioms and examples are in the `references/` directory.** Read the relevant file when generating code:
- `references/cpp.md` — C++ idioms (RAII, const-correctness, smart pointers)
- `references/python.md` — Python idioms (slots, frozen dataclasses, properties, type hints)
- `references/rust.md` — Rust idioms (ownership, borrowing, enums, newtypes)
- `references/java.md` — Java idioms (final, records, sealed classes, Optional)

---

## 1. Immutability by Default

Every variable, field, and parameter should be immutable until there is a specific, demonstrated reason for mutation. Mutability is not the default — it's an exception that requires justification.

**Variables.** Declare every variable with your language's strongest immutability qualifier. Only relax to mutable when the algorithm genuinely requires reassignment. Before reaching for a mutable variable, check whether you can restructure as a transformation — a pipeline, a fold, a single expression with a ternary — that produces the value once and never reassigns.

**Fields.** Mark all fields immutable at declaration. Initialize them in the constructor and never reassign. If an object must change state over its lifetime, do so through explicit methods with names that describe the state transition — never by exposing writable fields.

**Parameters.** Treat every parameter as read-only. Never reassign a parameter to a different value inside the function body. In languages that support it, mark parameters with an immutability qualifier explicitly. Even in languages that don't enforce it, treat this as convention.

**Collections and data structures.** Prefer immutable collections. When you need to "modify" a collection, produce a new one. Reserve mutable structures for performance-critical paths where profiling has demonstrated the need — and even then, isolate them behind an interface that doesn't expose the mutability.

**The audit.** After writing any function or class, scan every variable and field. For each one, ask: does this *need* to change after initialization? If not, make it immutable. This is not a suggestion — it's the first pass of self-review.

---

## 2. Minimal Visibility

Every public symbol is a maintenance obligation. Every hidden detail is freedom to refactor. Default to the most restrictive access and promote only when a concrete consumer exists today — not speculatively.

**Fields** are always private. No exceptions. If external code needs the data, expose it through a narrow accessor that returns an immutable view or a copy. Never return a mutable reference to internal state — that's an invisible write path into your object's invariants.

**Methods** start private. Promote to protected only if a subclass calls or overrides it in current code. Promote to public only if it's part of the module's documented contract. Helper methods, implementation details, and intermediate computation steps stay private.

**Types** (inner classes, nested structs, enums that only one class uses) start at the narrowest scope. A type that only appears in one module's implementation has no business in the public API.

**Module and package boundaries.** Export only the symbols that form the module's public contract. Everything else is internal. In languages with explicit visibility modifiers, use the narrowest one. In languages without enforcement, use naming conventions and document the intent clearly.

**The test.** For every symbol you create, ask: if I renamed or deleted this tomorrow, what would break? If the answer is "nothing outside this file," the visibility is correct. If distant, unexpected code would break, the symbol is too exposed.

---

## 3. Design by Contract

Every function and every class has a contract, whether you document it or not. Defensive programming makes that contract explicit, checkable, and enforceable.

**Preconditions** state what must be true when a function is called. They are the caller's responsibility. If a function requires a non-empty list, a positive integer, or a valid handle, say so — in documentation, in the type signature where possible, and in a runtime check for cases the type system can't catch.

**Postconditions** state what the function guarantees when it returns. They are the implementor's responsibility. If a sort function promises the output is ordered, that's a postcondition. Postconditions are excellent candidates for assertions in tests and debug builds.

**Class invariants** state what must always be true about an object between method calls. For example: "balance is never negative," "the list is always sorted," "start_date is before end_date." Every public method must preserve invariants. If a method temporarily violates an invariant during computation, it must restore it before returning.

**Assertions are executable contracts.** Place assertions at function entry (preconditions), function exit (postconditions), and at key checkpoints within complex algorithms (intermediate invariants). Assertions should crash loudly in development and testing. They document assumptions in a way that comments cannot — they're verified every time the code runs.

**Distinguish contract violations from operational failures.** A null pointer passed to a function that requires non-null is a *programming error* — the caller broke the contract. A network timeout is an *operational failure* — the system encountered an expected external condition. Programming errors should trigger assertions (crash early, crash loudly). Operational failures should be handled through the language's error-handling mechanism. Conflating these leads to either silent corruption (swallowing programming errors) or unnecessary fragility (crashing on expected operational conditions).

---

## 4. Validate at Boundaries, Trust Within

Not every layer of code should be paranoid. The strategy is: validate rigorously at the boundary, then trust validated data internally.

**Define a trust boundary.** The boundary is wherever external data enters your module: public API entry points, deserialization from network or disk, user input handlers, data received from other teams' services. At these points, validate everything — types, ranges, invariants, format, encoding.

**Validate once, thoroughly.** At the boundary, convert raw external data into your internal types. From that point inward, code can trust the types. This eliminates redundant validation scattered through the codebase and centralizes the "what do we accept?" policy in one place.

**Fail fast and fail clearly.** When validation fails, reject the input immediately with a clear diagnostic: what was expected, what was received, and where. Don't attempt to fix invalid data by guessing what the caller meant — guessing creates silent corruption. McConnell calls this the "barricade" — the line between dirty external data and clean internal data.

**Internal assertions are for invariants, not validation.** Inside the trust boundary, use assertions to verify that internal state is consistent — not to re-validate what the boundary already checked. If an internal assertion fires, it means there's a bug in your code, not bad input.

This section addresses correctness validation against well-intentioned callers. For defense against adversarial input (injection, encoding attacks, canonicalization), see the security skill.

---

## 5. Minimize Attack Surface for Modification

Every line of code that *can* be changed *will* eventually be changed by someone who doesn't fully understand it. Structure code so that accidental damage is contained.

**Minimize variable scope and lifetime.** Declare variables as close to first use as possible. A variable that exists for 200 lines before it's used is 200 lines of opportunity for someone to accidentally modify or shadow it. Short scope + immutability makes a variable's entire lifecycle visible in a glance.

**Prefer local over member, member over global.** The wider a variable's scope, the more code can modify it, the harder it is to reason about its state. Global mutable state is the most dangerous construct in a large codebase — every function in the process can read and write it, and the interaction between those accesses is exponentially hard to analyze.

**Return defensive copies.** When exposing internal state through accessors, return a copy or immutable view. If a getter returns a mutable reference to internal data, any consumer can silently corrupt your object's invariants. Similarly, when storing mutable data received from outside, copy it so the caller can't mutate your internals through a retained reference.

**Seal extension points.** Classes and methods should be non-overridable by default. In a large codebase, an unsealed class accumulates unexpected subclasses over years, and refactoring the base class becomes dangerous because you can't know what overrides depend on its behavior. Open a class for extension only when extension is an explicit design goal with documented contracts.

**Make illegal states unrepresentable.** Design types so that invalid combinations of values cannot be constructed. Use enums over string constants. Use dedicated types over bare primitives — an `EmailAddress` type over a `string`, a `PositiveInt` over a plain `int`. Use constructors or factory functions that enforce constraints at creation time, not validation functions that check after the fact.

---

## 6. Resource Safety

Every resource that is acquired must be released, and the mechanism for ensuring this should not depend on programmer discipline.

**Tie resource lifetimes to scope.** Use your language's deterministic cleanup mechanism — RAII, try-with-resources, `using`, `defer`, context managers — so that resources are released automatically when the scope exits, regardless of whether the exit is normal or exceptional.

**The allocator is the deallocator.** The same component that acquires a resource should be responsible for releasing it. If function A opens a connection, function A (or an object A controls) should close it. Passing ownership of a resource to a distant component is fragile and leads to leaks or double-frees.

**Prefer managed types over raw handles.** Smart pointers over raw pointers, managed file handles over raw descriptors, connection pools over manual open/close. The managed type encodes the ownership and lifetime policy in the type system, making it visible and enforceable.

**Never leave a resource in a partially initialized state.** If construction of an object requires multiple resources and the second acquisition fails, the first must be released. Use RAII or equivalent so that partial construction is automatically cleaned up.

---

## 7. Safe Defaults and Conventions

Choose defaults that produce correct behavior even when an engineer doesn't think carefully about them.

**Initialize everything.** Never leave a variable, field, or buffer uninitialized. If the correct value isn't known yet, use an explicit sentinel — an empty optional, a null-object, a typed default constant — not undefined memory or a magic number.

**Use exhaustive matching.** When branching on an enum, discriminated union, or variant, handle every case explicitly. Don't rely on a default/else branch to silently absorb new cases — when someone adds a new enum member months from now, the compiler or linter should force them to handle it everywhere.

**Avoid boolean parameters.** A call like `process(data, true, false)` is opaque at the call site. Use named constants, enums, or option structs so the reader understands what each argument controls without consulting the signature.

**Encode invariants in types.** If a value must be positive, use an unsigned type or a wrapper that enforces positivity at construction. If a string must match a pattern, parse it into a dedicated type at the boundary. The type system is a free, always-on correctness checker — use it to carry invariant information rather than relying on comments or documentation that can go stale.

---

## 8. Concurrency Safety

Shared mutable state under concurrency is the most common source of subtle, hard-to-reproduce bugs. Defensive programming treats concurrency as a constraint on mutability and visibility.

**Minimize shared mutable state.** The safest concurrent code has no shared mutable state. Prefer message passing, channels, or actor-style isolation where each thread/task owns its data exclusively. When sharing is necessary, make the shared data immutable or protect it with synchronization.

**Synchronize at the narrowest scope.** Hold locks for the minimum duration necessary. Never perform I/O, allocations, or callbacks while holding a lock. Acquire locks in a consistent global order to prevent deadlocks.

**Prefer higher-level abstractions.** Use concurrent collections, atomic types, and lock-free structures from your language's standard library over raw mutexes when they fit the access pattern. They encapsulate the synchronization discipline and are harder to misuse.

**Make thread safety visible.** Document which types are thread-safe and which are not. In languages that support it, use type system features to enforce thread safety (Rust's Send/Sync, Java's @ThreadSafe, C++'s const-correctness as a proxy).

This section addresses concurrency as a correctness concern. For concurrency as a performance concern (Amdahl's Law, false sharing, contention), see the performance skill.

---

## Applying This Skill

When generating code, apply these defaults automatically:
1. All variables and fields immutable until mutation is justified
2. All members private until a concrete consumer exists
3. All parameters treated as read-only
4. Assertions at preconditions, postconditions, and invariants
5. Validation at trust boundaries, not scattered through internals
6. Defensive copies on ingress and egress of mutable data
7. Resource lifetimes tied to scope via RAII or equivalent
8. Types sealed/final unless designed for extension
9. Exhaustive matching on enums and variants
10. Illegal states made unrepresentable through type design

When the target language is known, read the corresponding file in `references/` for language-specific idioms and examples.
