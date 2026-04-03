---
name: refactoring
description: "Apply when restructuring existing code without changing its behavior: extracting methods or classes, moving responsibilities, simplifying conditionals, improving names, or breaking dependencies in legacy code. Trigger on mentions of refactoring, code smells, extract method, legacy code, or technical debt. Language-specific idioms are in references/."
---

# Refactoring Skill

Refactoring is the disciplined technique of restructuring existing code without changing its external behavior. Every refactoring is a small, behavior-preserving transformation. Applied in sequence, these transformations can dramatically improve code structure while keeping the system working at every step. The key word is "disciplined" -- refactoring is not hacking at code until it looks better. Each transformation has a name, a defined set of mechanics, and a clear before-and-after.

The goal is never to rewrite from scratch. The goal is to make the code easier to understand and cheaper to modify, one safe step at a time. Refactoring is not something you schedule as a separate task -- it is part of the daily work of writing software. As Fowler puts it: refactoring is not an activity you set aside time for; it is something you do in the course of doing other things.

**Language-specific idioms and examples are in the `references/` directory.** Read the relevant file when generating refactored code:
- `references/cpp.md` -- move semantics, RAII considerations, template-based refactoring
- `references/python.md` -- Pythonic idioms, dataclasses, protocol classes
- `references/rust.md` -- ownership-aware refactoring, trait extraction, module reorganization
- `references/java.md` -- interface extraction, records, stream-based refactoring

---

## 1. When to Refactor

Refactoring is not a phase. It is a continuous practice woven into feature development, bug fixing, and code review.

**The Rule of Three.** Fowler's heuristic: the first time you do something, you just do it. The second time, you wince at the duplication but do it anyway. The third time, you refactor. Three strikes and you clean up. This prevents both premature abstraction (extracting a pattern after seeing it once, before you know the real shape of the variation) and unbounded duplication (letting copies multiply until they're impossible to reconcile).

**Refactor when adding a feature.** Before building the new capability, look at the existing code and ask: is this structure going to make the change easy? If not, first refactor the code to make the change easy, then make the easy change. Two separate steps, each verifiable independently. Fowler calls this preparatory refactoring -- it is the most common and most valuable time to refactor, because the payoff is immediate.

**Refactor during code review.** Code review is one of the best times to spot refactoring opportunities. A reviewer sees the code with fresh eyes and can identify naming problems, overlong methods, and misplaced responsibilities that the author has become blind to. When a reviewer suggests a refactoring, ideally the author performs it immediately rather than filing it as future work -- small refactorings deferred tend to never happen.

**Refactor to understand.** When you encounter unfamiliar code, refactor it as a way of building understanding. Rename variables to what you think they mean, extract functions to isolate behavior, rearrange logic to expose structure. If your guesses are wrong, the tests will tell you. This is active reading -- far more effective than passive scanning. Fowler calls this comprehension refactoring: you clean up the code as you learn what it does, so the next person does not have to repeat your effort.

**Code smells as triggers.** Martin identifies specific smells as signals that refactoring is needed. Each smell points to one or more specific refactorings that address it. Don't refactor on a vague feeling; identify the smell, then apply the appropriate transformation:

- **Long Method** -- extract functions until each one does one thing
- **Large Class** -- extract class to split responsibilities
- **Feature Envy** -- move the method to the class whose data it uses
- **Data Clumps** -- groups of data that travel together belong in their own object
- **Primitive Obsession** -- replace primitives that carry domain meaning with value objects
- **Divergent Change** -- one class changed for multiple unrelated reasons needs splitting
- **Shotgun Surgery** -- one change requires edits across many classes; consolidate the scattered logic

**Tactical vs. strategic programming.** Ousterhout draws a sharp line between tactical programming -- getting something working as fast as possible, accumulating complexity with every shortcut -- and strategic programming, where you invest a small amount of extra time to produce clean structure. Tactical programming feels fast but makes every subsequent change slower. The complexity it leaves behind is not free -- it compounds, and the cost of each future change grows. Refactoring is the primary tool for correcting the course when tactical debt accumulates. Even a small, consistent investment in strategic cleanup -- ten to twenty percent of development time -- prevents the codebase from degrading into a state where every change is painful.

---

## 2. Safe Refactoring Mechanics

Refactoring without a safety net is just editing and hoping. The discipline of safe refactoring is what separates structured improvement from risky code churn.

**Small steps, each preserving behavior.** Every individual refactoring should be tiny -- rename a variable, extract a function, move a field. After each step, the code should compile and all tests should pass. If you're making a change so large that you can't verify it immediately, break it into smaller steps.

**Run tests after every step.** This is non-negotiable. The entire point of small steps is that you can verify each one. If you extract a function and the tests pass, you know the extraction preserved behavior. If you wait until you've made ten changes before running tests, you don't know which change broke things.

**Commit after each successful step.** Each green test run is a save point. If the next step goes wrong, you can revert to a known-good state. This is far cheaper than debugging forward through a tangle of interleaved changes.

**Revert rather than debug forward.** When a refactoring step breaks something and the cause isn't immediately obvious, revert to the last commit rather than spending time debugging. You've lost at most a few minutes of work. Then try the step again, more carefully, or choose a different approach. The discipline of small steps makes reversion cheap.

**Characterization tests for legacy code.** When refactoring code that has no tests, you need a safety net before you start. Feathers prescribes characterization tests -- tests that capture the code's current behavior, whether correct or not. Call the code, observe what it does, write assertions matching that behavior. Now you have a baseline that will alert you if your refactoring changes something unintentionally.

**Separate refactoring commits from behavior changes.** Never mix refactoring with feature work in the same commit. A commit that both restructures code and adds new behavior is impossible to verify -- if a test breaks, you cannot tell whether the refactoring introduced a bug or the new feature has a defect. Keep the two activities in separate commits so that each can be reviewed and reverted independently.

**When not to refactor.** Refactoring has clear boundaries. Don't refactor when a rewrite is genuinely needed -- if the code doesn't work and can't be incrementally improved, replacement may be the right call. Don't refactor code you don't need to change -- refactoring for its own sake, in code that is stable and untouched, adds risk without benefit. And don't refactor when you're close to a deadline and the code works -- ship first, refactor after. The key judgment is whether the refactoring will pay for itself in the current work, not in some hypothetical future.

---

## 3. Extract and Inline

These are the most frequently used refactorings -- the ones you will apply multiple times in a single coding session. They are the bread and butter of daily code improvement, and mastering them is the single most effective investment in refactoring skill.

**Extract Function.** When a code fragment needs a comment to explain what it does, extract it into its own function and name the function after the intent -- the "what," not the "how." The original location now reads as a descriptive function call, and the detail is one click away. The trigger is a separation between what the code does and how it does it, not a minimum line count. Even a single line is worth extracting if it clarifies intent. Fowler considers this the most important refactoring in the catalog -- the foundation on which most other refactorings build.

**Extract Variable.** When an expression is complex or its purpose is unclear, introduce a named variable that captures the meaning. This is the inverse of a clarifying comment -- the name documents the intent and the compiler verifies it exists. Extract Variable is especially useful inside conditionals, where a well-named boolean variable can replace an opaque logical expression.

**Extract Class.** When a class does two things -- when it has two clusters of data and methods that change for different reasons -- split it into two classes, each with a single responsibility. This often surfaces when you notice a subset of fields that are always used together and separately from the rest.

**Inline Function.** When a function's body is as clear as its name, inline it. Indirection is only valuable when it aids understanding. A one-line function called `isEligible` that contains `return age >= 18` earns its keep. A function called `getRating` that just delegates to another function without adding clarity does not.

**Inline Variable.** When a variable name says nothing more than the expression it holds, remove the variable and use the expression directly. This is the reverse of Extract Variable -- apply whichever makes the code clearer.

**The relationship between Extract and Inline.** These refactorings are inverses of each other. Neither is universally better. Extract when indirection improves clarity; inline when it obscures it. The skill is in judging which direction aids the reader at each particular point in the code.

**Extract Class** often pairs with **Move Function** and **Move Field**. Once you identify that a class has two responsibilities, you extract a new class and then move the relevant methods and fields into it. The original class delegates to the extracted class. This is one of the most impactful compound refactorings for reducing class size and improving cohesion.

---

## 4. Move and Reorganize

Code often ends up in the wrong place. Functions accumulate in the class where they were first needed rather than the class where they belong. Fields drift away from the behavior that uses them. These refactorings put things where they belong.

**Move Function.** A function belongs with the data it uses most. If a function on class A spends most of its time accessing data from class B, move it to B. This reduces coupling, eliminates feature envy, and makes the code easier to understand because related things are together. When deciding where a function belongs, look at its references to other elements -- the module where it has the most references is usually the right home.

**Move Field.** When a field is used more by another class than by the class that owns it, move it. This often follows naturally after you notice feature envy -- the method reaches into another object for data that should live closer to the behavior that uses it.

Move Function and Move Field are often applied together. When you move a function, check whether the data it accesses should move with it. When you move a field, check whether the methods that use it most should follow.

**Split Phase.** When code does two distinct things in sequence -- for example, parsing input and then computing a result from the parsed data -- separate the two activities into distinct phases connected by an intermediate data structure. Each phase becomes independently understandable and testable. The data structure between them makes the interface between the phases explicit. This refactoring is particularly valuable in data processing pipelines, compilers, and any workflow where distinct stages can be identified.

**Replace Conditional with Polymorphism.** When a conditional (switch or if-else chain) selects different behavior based on type, replace it with polymorphism. Create a class for each case, move the case-specific logic into the appropriate class, and let the type system handle dispatch. This eliminates the need to find and update every switch statement when a new type is added. The key signal is multiple conditionals switching on the same type code scattered across the codebase -- polymorphism consolidates that logic into one place per type.

---

## 5. Simplify Conditionals

Complex conditional logic is one of the hardest things to read and one of the most common sources of bugs. Conditionals are where most defects hide, because each branch doubles the number of paths through the code. These refactorings flatten and clarify conditional structures.

**Decompose Conditional.** Extract the condition and each branch into named functions. Instead of reading a complex boolean expression and two blocks of code, the reader sees three intention-revealing names: one for the condition, one for the then-path, one for the else-path. This works even when the branches are short -- the names add information that the raw code does not. The resulting code reads almost like prose: "if summer, use summer rate, otherwise use winter rate."

**Consolidate Conditional Expression.** When multiple guards produce the same result, combine them into a single conditional with a descriptive name. If three separate if-statements all return 0, that's a single concept ("is ineligible") that should be expressed once. Extract the consolidated condition into its own function to give it a name that explains the business rule rather than the mechanical check.

**Replace Nested Conditionals with Guard Clauses.** When a function has deep nesting from a chain of conditions, flatten it by checking each special case at the top and returning early. The main logic then occupies the body of the function at a single indentation level. Flat is better than nested -- guard clauses make the structure of the function visible at a glance.

Guard clauses communicate that the guarded condition is unusual or exceptional. The main body communicates the normal path. This distinction -- what is the exception versus what is the rule -- is lost in deeply nested if-else structures where every path looks equally important.

**Introduce Special Case / Null Object.** When you find repeated null checks or special-case handling scattered throughout the codebase, encapsulate the special case in its own class. A `NullCustomer` that responds to all customer methods with safe defaults eliminates dozens of null checks at every call site. The consuming code no longer needs to know that the special case exists. Fowler generalizes the Null Object pattern into Special Case -- any value that triggers widespread conditional handling is a candidate for encapsulation into its own type.

---

## 6. Refactoring Data

How data is represented shapes every piece of code that touches it. Poor data representations force defensive code at every access point, while well-designed data structures make consuming code simple and safe. These refactorings improve data structures to reduce coupling and express domain meaning.

**Encapsulate Record.** Replace raw dictionaries, structs, or other untyped records with classes that control access to their fields. A class can enforce invariants, evolve its internal representation without affecting callers, and make its interface explicit. Bare key-value structures invite typos, missing-field bugs, and uncontrolled mutation. The refactoring is especially important for records that cross module boundaries -- once external code depends on raw field access, changing the structure becomes a breaking change.

**Encapsulate Collection.** Never expose a raw mutable collection from an object. Callers who receive a mutable list can add, remove, or reorder elements without the owning object's knowledge, breaking invariants silently. Return a copy, an immutable view, or provide add/remove methods that let the owner maintain control. The getter for a collection should make it impossible for callers to modify the collection without going through the owning object.

**Replace Primitive with Object.** When a primitive value carries domain meaning -- a phone number stored as a string, a currency amount as a float, a status as an integer -- wrap it in a domain type. A `Money` type can enforce currency rules, prevent unit confusion, and provide arithmetic that respects rounding. A raw float can only be wrong in ways you won't notice until production. This refactoring addresses the primitive obsession smell -- it is one of the highest-leverage improvements you can make, because the domain type centralizes validation and behavior that would otherwise be scattered across every call site.

**Split Variable.** When a variable is assigned more than once and each assignment serves a different purpose, it is serving double duty. Introduce a separate variable for each purpose, each with a name that explains its role. This eliminates the mental overhead of tracking what the variable "currently means" at any point in the function. Loop variables and collecting variables (accumulators) are the exceptions -- they are assigned repeatedly by design. Every other case of multiple assignment is a candidate for splitting.

---

## 7. Dealing with Inheritance

Inheritance hierarchies tend to grow in ways that increase coupling and reduce clarity. Subclasses become tightly bound to parent implementation details, and deep hierarchies force readers to jump between multiple files to understand a single behavior. These refactorings restructure inheritance to keep it useful or replace it with something better.

**Replace Subclass with Delegate.** When inheritance is used for code reuse rather than expressing a genuine type relationship, replace it with delegation (composition). A subclass that overrides one method and inherits twenty others is tightly coupled to a parent it barely resembles. A delegate that implements the varying behavior behind an interface is loosely coupled and independently testable. Fowler notes this is one of the most important refactorings -- the old adage "favor composition over inheritance" is enacted through this specific transformation.

**Extract Superclass.** When two classes share significant behavior, extract the common parts into a superclass. This is the reverse of Replace Subclass with Delegate -- here, inheritance is the right tool because the classes genuinely share an "is-a" relationship and the shared behavior is stable. The key test: will the shared behavior evolve together, or might the two classes eventually need to diverge? If they might diverge, prefer delegation.

**Collapse Hierarchy.** When a subclass adds no meaningful behavior or distinction from its parent, merge them. An inheritance level that exists only for historical reasons adds indirection without value. Remove it and let the remaining class stand on its own. This refactoring often becomes necessary after other refactorings have moved behavior around -- what was once a meaningful distinction between parent and child has evaporated, and the hierarchy is now just noise.

**Replace Type Code with Subclasses.** When behavior varies based on a type field and you find switch statements or if-else chains keyed on that field, replace the type code with subclasses. Each subclass encapsulates the behavior for its type, and dispatch happens through polymorphism rather than conditional logic. This refactoring is a prerequisite for Replace Conditional with Polymorphism -- you first create the subclasses, then move the conditional branches into overriding methods.

**Deep modules over shallow hierarchies.** Ousterhout argues that the best modules are deep -- they offer a simple interface that hides significant complexity. Shallow inheritance hierarchies, where each class adds a thin layer of behavior and exposes almost as much complexity as it hides, are the opposite of deep. When refactoring inheritance, aim for fewer, deeper classes rather than many shallow layers.

---

## 8. Breaking Dependencies in Legacy Code

Legacy code -- code without tests -- requires specialized techniques to become testable. You cannot refactor safely without tests, but you often cannot write tests without some refactoring. Feathers provides a systematic approach to breaking this circular dependency.

**The Legacy Code Change Algorithm.** Five steps, in order:

1. **Identify change points** -- where do you need to make the change?
2. **Find test points** -- where can you observe the behavior you need to preserve?
3. **Break dependencies** -- make the code testable without changing its behavior.
4. **Write characterization tests** -- document what the code currently does, not what it should do. If the code returns 42 for some input, assert 42 -- even if 42 might be wrong. The point is to detect unintended changes.
5. **Make changes and refactor** under the safety net of those tests.

The order matters. Skipping to step 5 without the preceding steps is how legacy code stays legacy.

**Extract and Override.** Create a seam by extracting the dependency interaction into a method, then making that method virtual or overridable. In a test subclass, override the method to replace the dependency with a test double. This is minimally invasive -- it doesn't require changing the production constructor or any callers. It creates a controlled point where test code can intercept production behavior. Feathers considers this one of the safest dependency-breaking techniques because it requires only two mechanical steps: extract and make overridable.

**Parameterize Constructor.** Add the dependency as a constructor parameter, providing a default value that preserves the current behavior. Production code continues to use the no-argument constructor and behaves identically. Tests pass in a test double through the new parameter. This is cleaner than Extract and Override when you can modify the constructor, and it makes the dependency explicit in the class's interface. Over time, parameterized constructors naturally evolve toward proper dependency injection.

**Wrap Method.** When you need to add behavior that should happen alongside an existing method, create a new method that calls the original and adds the new behavior. Rename the original to a private helper. The public interface stays the same, the new behavior is isolated and testable, and the original logic is untouched. This avoids the temptation to modify a working method and risk breaking it. Wrap Method is particularly useful for cross-cutting concerns like logging, timing, or auditing that need to happen around existing operations.

**Sprout Method / Sprout Class.** When you need to add new functionality to existing code that you can't get under test, write the new code in a fresh method or class using TDD. Then call it from the existing code. The new code is fully tested. The existing code has one small addition -- the call to the sprouted code -- which is simple enough to verify by inspection. Over time, more and more of the system lives in tested, sprouted code. Sprout Class is preferred when the new functionality has its own clear responsibility -- it deserves its own class rather than being bolted onto a class that is already too large.

**Work incrementally.** Don't try to get an entire legacy class under test in one pass. Find the narrowest dependency you can break, write one characterization test, make one change. Expand coverage outward from that foothold. Each cycle leaves the code slightly better and slightly more testable than before. The goal is not to achieve perfect test coverage overnight -- it is to ensure that every time you touch legacy code, you leave it more testable than you found it.

---

## Applying This Skill

When refactoring existing code:

1. Identify the smell or structural problem -- name it specifically
2. Choose the refactoring that addresses it
3. Write characterization tests if coverage is insufficient
4. Apply the refactoring in small, behavior-preserving steps
5. Run tests after each step; commit after each green run
6. If a step breaks tests and the cause is not immediately clear, revert

When adding features to existing code:

1. Assess whether the current structure supports the change
2. If not, refactor first to make the change easy
3. Then make the easy change as a separate step
4. Keep refactoring commits separate from feature commits

When working with legacy code:

1. Follow the Legacy Code Change Algorithm -- do not skip steps
2. Find the narrowest seam to break the dependency
3. Write characterization tests before touching behavior
4. Use Sprout Method/Class for new logic so it starts life under test
5. Expand the test boundary incrementally over time

When the target language is known, read the corresponding file in `references/` for language-specific refactoring patterns and idioms.
