---
name: skill-improvement
description: >-
  Add, refactor, validate, or retire an agent skill. Use when implementation reveals a durable
  rule, when a skill is too large or stale, or when the skill catalog changes.
---

# Skill improvement

## When to use

- A change reveals a durable, non-obvious repository rule.
- A skill contains duplicated, dated, or contradictory instructions.
- A new repeatable workflow needs an agent entry point.
- A workflow or source path invalidates a skill.

## When not to use

Do not use this for session notes, issue status, completed-work lists, or a
one-off command that has no future value.

## Procedure

1. Identify the one workflow or invariant the skill should own.
2. Search `docs/skills/INDEX.md` and existing skills for an existing owner.
3. Update the existing skill instead of creating a duplicate.
4. If new, create `docs/skills/<lowercase-kebab-case>/SKILL.md`.
5. Add only this front matter:

   ```yaml
   ---
   name: <directory-name>
   description: >-
     <capability>. Use when <specific activation conditions>.
   ---
   ```

6. Start with `When to use`, `When not to use`, and an actionable `Procedure`.
7. Add `Red flags` and `Verification` when they improve safe execution.
8. Keep the entry file under 500 lines; move large references to an on-demand file.
9. Link to canonical facts instead of copying them from another document.
10. Add or update the entry in `docs/skills/INDEX.md`.
11. Remove stale text that contradicts the new rule.
12. Run the documentation checks before handoff.

## Content rules

Include specific activation language, imperative steps, required source files or
commands, repeatable failure modes, and evidence required before completion.

Exclude dated incident narratives, issue or pull-request numbers, session logs,
status percentages, duplicated repository-wide policy, and advice with no
observable action.

## Canonical ownership

- Build behavior: [`build`](../build/SKILL.md)
- Package decisions: [`packages`](../packages/SKILL.md)
- CI behavior: [`ci-cd`](../ci-cd/SKILL.md)
- Test selection: [`testing`](../testing/SKILL.md)
- Release verification: [`release`](../release/SKILL.md)
- Repository-wide contributor policy: [`CONTRIBUTING.md`](../../../CONTRIBUTING.md)
- Public release trust: [`docs/release.md`](../../release.md)

## Common rationalizations

- “This fact is obvious.” If it caused a failure or workaround, document it once.
- “I will update the skill later.” Capture durable learning in the same change.
- “A second skill is clearer.” Search for an existing canonical owner first.

## Red flags

- The skill has no specific activation conditions.
- The entry file contains a long reference catalog instead of a procedure.
- The same rule appears in multiple skills.
- The skill describes a deleted source path or unverified command.

## Verification

```bash
python3 scripts/check-skill-docs.py
pre-commit run --all-files
```

Also verify that the skill is indexed, repository-relative links resolve, and
the entry file stays within the size budget.
