---
description: Draft a Goal/Constraints/Acceptance plan for the task in $ARGUMENTS, then enter plan mode
---

Before writing any code, produce a plan in this exact shape:

## Goal
One sentence. The outcome, not the activity.

## Constraints
Bulleted. Include:
- Files / modules in scope (and explicitly out of scope).
- Stack/version constraints (look at CLAUDE.md, AGENTS.md, composer.json, package.json).
- Backwards-compat or migration concerns.
- Performance, security, or ergonomic budgets the user has flagged.

## Acceptance criteria
Bulleted, testable. Each one should be checkable by running a command or reading a diff. Examples:
- `composer lint:check` passes.
- `php artisan test --filter=Foo` passes with new cases X and Y.
- `/route X` returns 200 with payload shape Z.
- No new TODOs left behind.

## Approach
3–7 bullets, ordered. The smallest plan that covers the goal. Identify the *risky* step and how you'll de-risk (spike, isolated test, advisor() call).

## Open questions
Anything that would change the approach materially. If the answer is guessable from the codebase, go look — don't ask.

---

Task: $ARGUMENTS

After producing the plan, ask the user to approve or amend before any edits. If they say "go", enter plan-mode-style execution: small steps, run the verification check after each material change, and use `advisor()` once before declaring done.
